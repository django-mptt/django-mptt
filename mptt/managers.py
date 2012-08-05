"""
A custom manager for working with trees of objects.
"""
# for python 2.5
from __future__ import with_statement

import contextlib

from django.db import connection, models, transaction
from django.db.models import F, Max
from django.utils.translation import ugettext as _

from django.db import connections, router

from mptt.exceptions import CantDisableUpdates, InvalidMove

__all__ = ('TreeManager',)

qn = connection.ops.quote_name

COUNT_SUBQUERY = """(
    SELECT COUNT(*)
    FROM %(rel_table)s
    WHERE %(mptt_fk)s = %(mptt_table)s.%(mptt_pk)s
)"""

CUMULATIVE_COUNT_SUBQUERY = """(
    SELECT COUNT(*)
    FROM %(rel_table)s
    WHERE %(mptt_fk)s IN
    (
        SELECT m2.%(mptt_pk)s
        FROM %(mptt_table)s m2
        WHERE m2.%(tree_id)s = %(mptt_table)s.%(tree_id)s
          AND m2.%(left)s BETWEEN %(mptt_table)s.%(left)s
                              AND %(mptt_table)s.%(right)s
    )
)"""


class TreeManager(models.Manager):
    """
    A manager for working with trees of objects.
    """

    def init_from_model(self, model):
        """
        Sets things up. This would normally be done in contribute_to_class(),
        but Django calls that before we've created our extra tree fields on the
        model (which we need). So it's done here instead, after field setup.
        """

        # Avoid calling "get_field_by_name()", which populates the related
        # models cache and can cause circular imports in complex projects.
        # Instead, find the tree_id field using "get_fields_with_model()".
        [tree_field] = [fld for fld in model._meta.get_fields_with_model() if fld[0].name == self.tree_id_attr]
        if tree_field[1]:
            # tree_model is the model that contains the tree fields.
            # this is usually just the same as model, but not for derived models.
            self.tree_model = tree_field[1]
        else:
            self.tree_model = model

        self._base_manager = None
        if self.tree_model is not model:
            # _base_manager is the treemanager on tree_model
            self._base_manager = self.tree_model._tree_manager

    @contextlib.contextmanager
    def disable_mptt_updates(self):
        """
        Context manager. Disables mptt updates.

        NOTE that this context manager causes inconsistencies! MPTT model methods are
        not guaranteed to return the correct results.

        When to use this method:
            If used correctly, this method can be used to speed up bulk updates.

            This doesn't do anything clever. It *will* mess up your tree.
            You should follow this method with a call to TreeManager.rebuild() to ensure your
            tree stays sane, and you should wrap both calls in a transaction.

            This is best for updates that span a large part of the table.
            If you are doing localised changes (1 tree, or a few trees) consider
            using delay_mptt_updates.
            If you are making only minor changes to your tree, just let the updates happen.

        Transactions:
            This doesn't enforce any transactional behavior.
            You should wrap this in a transaction to ensure database consistency.

        If updates are already disabled on the model, this is a noop.

        Usage:
            with transaction.commit_on_success():
                with MyNode.objects.disable_mptt_updates():
                    # bulk updates.
                MyNode.objects.rebuild()
        """
        # Error cases:
        if self.model._meta.abstract:
            #  * an abstract model. Design decision needed - do we disable updates for
            #    all concrete models that derive from this model?
            #    I vote no - that's a bit implicit and it's a weird use-case anyway.
            #    Open to further discussion :)
            raise CantDisableUpdates(
                "You can't disable/delay mptt updates on %s, it's an abstract model" % self.model.__name__
            )
        elif self.model._meta.proxy:
            #  * a proxy model. disabling updates would implicitly affect other models
            #    using the db table. Caller should call this on the manager for the concrete
            #    model instead, to make the behavior explicit.
            raise CantDisableUpdates(
                "You can't disable/delay mptt updates on %s, it's a proxy model. Call the concrete model instead."
                % self.model.__name__
            )
        elif self.tree_model is not self.model:
            #  * a multiple-inheritance child of an MPTTModel.
            #    Disabling updates may affect instances of other models in the tree.
            raise CantDisableUpdates(
                "You can't disable/delay mptt updates on %s, it doesn't contain the mptt fields."
                % self.model.__name__
            )

        if not self.model._mptt_updates_enabled:
            # already disabled, noop.
            yield
        else:
            self.model._mptt_updates_enabled = False
            try:
                yield
            finally:
                self.model._mptt_updates_enabled = True

    @contextlib.contextmanager
    def delay_mptt_updates(self):
        """
        Context manager. Delays mptt updates until the end of a block of bulk processing.

        NOTE that this context manager causes inconsistencies! MPTT model methods are
        not guaranteed to return the correct results until the end of the context block.

        When to use this method:
            If used correctly, this method can be used to speed up bulk updates.
            This is best for updates in a localised area of the db table, especially if all
            the updates happen in a single tree and the rest of the forest is left untouched.
            No subsequent rebuild is necessary.

            delay_mptt_updates does a partial rebuild of the modified trees (not the whole table).
            If used indiscriminately, this can actually be much slower than just letting the updates
            occur when they're required.

            The worst case occurs when every tree in the table is modified just once.
            That results in a full rebuild of the table, which can be *very* slow.

            If your updates will modify most of the trees in the table (not a small number of trees),
            you should consider using TreeManager.disable_mptt_updates, as it does much fewer
            queries.

        Transactions:
            This doesn't enforce any transactional behavior.
            You should wrap this in a transaction to ensure database consistency.

        Exceptions:
            If an exception occurs before the processing of the block, delayed updates
            will not be applied.

        Usage:
            with transaction.commit_on_success():
                with MyNode.objects.delay_mptt_updates():
                    # bulk updates.
        """
        with self.disable_mptt_updates():
            if self.model._mptt_is_tracking:
                # already tracking, noop.
                yield
            else:
                self.model._mptt_start_tracking()
                try:
                    yield
                except Exception:
                    # stop tracking, but discard results
                    self.model._mptt_stop_tracking()
                    raise
                results = self.model._mptt_stop_tracking()
                for tree_id in results:
                    self.partial_rebuild(tree_id)

    @property
    def parent_attr(self):
        return self.model._mptt_meta.parent_attr

    @property
    def left_attr(self):
        return self.model._mptt_meta.left_attr

    @property
    def right_attr(self):
        return self.model._mptt_meta.right_attr

    @property
    def tree_id_attr(self):
        return self.model._mptt_meta.tree_id_attr

    @property
    def level_attr(self):
        return self.model._mptt_meta.level_attr

    def _translate_lookups(self, **lookups):
        new_lookups = {}
        for k, v in lookups.items():
            parts = k.split('__')
            new_parts = []
            for part in parts:
                new_parts.append(getattr(self, '%s_attr' % part, part))
            new_lookups['__'.join(new_parts)] = v
        return new_lookups

    def _mptt_filter(self, qs=None, **filters):
        """
        Like self.filter(), but translates name-agnostic filters for MPTT fields.
        """
        if self._base_manager:
            return self._base_manager._mptt_filter(qs=qs, **filters)

        if qs is None:
            qs = self.get_query_set()
        return qs.filter(**self._translate_lookups(**filters))

    def _mptt_update(self, qs=None, **items):
        """
        Like self.update(), but translates name-agnostic MPTT fields.
        """
        if self._base_manager:
            return self._base_manager._mptt_update(qs=qs, **items)

        if qs is None:
            qs = self.get_query_set()
        return qs.update(**self._translate_lookups(**items))

    def _get_connection(self, node):
        return connections[router.db_for_write(node)]

    def add_related_count(self, queryset, rel_model, rel_field, count_attr,
                          cumulative=False):
        """
        Adds a related item count to a given ``QuerySet`` using its
        ``extra`` method, for a ``Model`` class which has a relation to
        this ``Manager``'s ``Model`` class.

        Arguments:

        ``rel_model``
           A ``Model`` class which has a relation to this `Manager``'s
           ``Model`` class.

        ``rel_field``
           The name of the field in ``rel_model`` which holds the
           relation.

        ``count_attr``
           The name of an attribute which should be added to each item in
           this ``QuerySet``, containing a count of how many instances
           of ``rel_model`` are related to it through ``rel_field``.

        ``cumulative``
           If ``True``, the count will be for each item and all of its
           descendants, otherwise it will be for each item itself.
        """
        meta = self.model._meta
        if cumulative:
            subquery = CUMULATIVE_COUNT_SUBQUERY % {
                'rel_table': qn(rel_model._meta.db_table),
                'mptt_fk': qn(rel_model._meta.get_field(rel_field).column),
                'mptt_table': qn(self.tree_model._meta.db_table),
                'mptt_pk': qn(meta.pk.column),
                'tree_id': qn(meta.get_field(self.tree_id_attr).column),
                'left': qn(meta.get_field(self.left_attr).column),
                'right': qn(meta.get_field(self.right_attr).column),
            }
        else:
            subquery = COUNT_SUBQUERY % {
                'rel_table': qn(rel_model._meta.db_table),
                'mptt_fk': qn(rel_model._meta.get_field(rel_field).column),
                'mptt_table': qn(self.tree_model._meta.db_table),
                'mptt_pk': qn(meta.pk.column),
            }
        return queryset.extra(select={count_attr: subquery})

    def get_query_set(self):
        """
        Returns a ``QuerySet`` which contains all tree items, ordered in
        such a way that that root nodes appear in tree id order and
        their subtrees appear in depth-first order.
        """
        return super(TreeManager, self).get_query_set().order_by(
            self.tree_id_attr, self.left_attr)

    def insert_node(self, node, target, position='last-child', save=False, allow_existing_pk=False):
        """
        Sets up the tree state for ``node`` (which has not yet been
        inserted into in the database) so it will be positioned relative
        to a given ``target`` node as specified by ``position`` (when
        appropriate) it is inserted, with any neccessary space already
        having been made for it.

        A ``target`` of ``None`` indicates that ``node`` should be
        the last root node.

        If ``save`` is ``True``, ``node``'s ``save()`` method will be
        called before it is returned.

        NOTE: This is a low-level method; it does NOT respect ``MPTTMeta.order_insertion_by``.
        In most cases you should just set the node's parent and let mptt call this during save.
        """

        if self._base_manager:
            return self._base_manager.insert_node(node, target, position=position, save=save)

        if node.pk and not allow_existing_pk and self.filter(pk=node.pk).exists():
            raise ValueError(_('Cannot insert a node which has already been saved.'))

        if target is None:
            tree_id = self._get_next_tree_id()
            setattr(node, self.left_attr, 1)
            setattr(node, self.right_attr, 2)
            setattr(node, self.level_attr, 0)
            setattr(node, self.tree_id_attr, tree_id)
            setattr(node, self.parent_attr, None)
        elif target.is_root_node() and position in ['left', 'right']:
            target_tree_id = getattr(target, self.tree_id_attr)
            if position == 'left':
                tree_id = target_tree_id
                space_target = target_tree_id - 1
            else:
                tree_id = target_tree_id + 1
                space_target = target_tree_id
            self._create_tree_space(space_target)

            setattr(node, self.left_attr, 1)
            setattr(node, self.right_attr, 2)
            setattr(node, self.level_attr, 0)
            setattr(node, self.tree_id_attr, tree_id)
            setattr(node, self.parent_attr, None)
        else:
            setattr(node, self.left_attr, 0)
            setattr(node, self.level_attr, 0)

            space_target, level, left, parent, right_shift = \
                self._calculate_inter_tree_move_values(node, target, position)
            tree_id = getattr(parent, self.tree_id_attr)

            self._create_space(2, space_target, tree_id)

            setattr(node, self.left_attr, -left)
            setattr(node, self.right_attr, -left + 1)
            setattr(node, self.level_attr, -level)
            setattr(node, self.tree_id_attr, tree_id)
            setattr(node, self.parent_attr, parent)

            if parent:
                self._post_insert_update_cached_parent_right(parent, right_shift)

        if save:
            node.save()
        return node

    def _move_node(self, node, target, position='last-child', save=True):
        if self._base_manager:
            return self._base_manager.move_node(node, target, position=position)

        if self.tree_model._mptt_is_tracking:
            # delegate to insert_node and clean up the gaps later.
            return self.insert_node(node, target, position=position, save=save, allow_existing_pk=True)
        else:
            if target is None:
                if node.is_child_node():
                    self._make_child_root_node(node)
            elif target.is_root_node() and position in ('left', 'right'):
                self._make_sibling_of_root_node(node, target, position)
            else:
                if node.is_root_node():
                    self._move_root_node(node, target, position)
                else:
                    self._move_child_node(node, target, position)
            transaction.commit_unless_managed()

    def move_node(self, node, target, position='last-child'):
        """
        Moves ``node`` relative to a given ``target`` node as specified
        by ``position`` (when appropriate), by examining both nodes and
        calling the appropriate method to perform the move.

        A ``target`` of ``None`` indicates that ``node`` should be
        turned into a root node.

        Valid values for ``position`` are ``'first-child'``,
        ``'last-child'``, ``'left'`` or ``'right'``.

        ``node`` will be modified to reflect its new tree state in the
        database.

        This method explicitly checks for ``node`` being made a sibling
        of a root node, as this is a special case due to our use of tree
        ids to order root nodes.

        NOTE: This is a low-level method; it does NOT respect ``MPTTMeta.order_insertion_by``.
        In most cases you should just move the node yourself by setting node.parent.
        """
        self._move_node(node, target, position=position)

    def root_node(self, tree_id):
        """
        Returns the root node of the tree with the given id.
        """
        if self._base_manager:
            return self._base_manager.root_node(tree_id)

        return self._mptt_filter(tree_id=tree_id, parent=None).get()

    def root_nodes(self):
        """
        Creates a ``QuerySet`` containing root nodes.
        """
        if self._base_manager:
            return self._base_manager.root_nodes()

        return self._mptt_filter(parent=None)

    def rebuild(self):
        """
        Rebuilds whole tree in database using `parent` link.
        """

        if self._base_manager:
            return self._base_manager.rebuild()

        opts = self.model._mptt_meta

        qs = self._mptt_filter(parent=None)
        if opts.order_insertion_by:
            qs = qs.order_by(*opts.order_insertion_by)
        pks = qs.values_list('pk', flat=True)

        idx = 0
        for pk in pks:
            idx += 1
            self._rebuild_helper(pk, 1, idx)

    def partial_rebuild(self, tree_id):
        if self._base_manager:
            return self._base_manager.partial_rebuild(tree_id)
        opts = self.model._mptt_meta

        qs = self._mptt_filter(parent__isnull=True, tree_id=tree_id)
        if opts.order_insertion_by:
            qs = qs.order_by(*opts.order_insertion_by)
        pks = qs.values_list('pk', flat=True)
        if not pks:
            return
        if len(pks) > 1:
            raise RuntimeError("More than one root node with tree_id %d. That's invalid, do a full rebuild." % tree_id)

        self._rebuild_helper(pks[0], 1, tree_id)

    def _rebuild_helper(self, pk, left, tree_id, level=0):
        opts = self.model._mptt_meta
        right = left + 1

        qs = self._mptt_filter(parent__pk=pk)
        if opts.order_insertion_by:
            qs = qs.order_by(*opts.order_insertion_by)
        child_ids = qs.values_list('pk', flat=True)

        for child_id in child_ids:
            right = self._rebuild_helper(child_id, right, tree_id, level + 1)

        qs = self.model._default_manager.filter(pk=pk)
        self._mptt_update(qs,
            left=left,
            right=right,
            level=level,
            tree_id=tree_id
        )

        return right + 1

    def _post_insert_update_cached_parent_right(self, instance, right_shift, seen=None):
        setattr(instance, self.right_attr, getattr(instance, self.right_attr) + right_shift)
        attr = '_%s_cache' % self.parent_attr
        if hasattr(instance, attr):
            parent = getattr(instance, attr)
            if parent:
                if not seen:
                    seen = set()
                seen.add(instance)
                if parent in seen:
                    # detect infinite recursion and throw an error
                    raise InvalidMove
                self._post_insert_update_cached_parent_right(parent, right_shift, seen=seen)

    def _calculate_inter_tree_move_values(self, node, target, position):
        """
        Calculates values required when moving ``node`` relative to
        ``target`` as specified by ``position``.
        """
        left = getattr(node, self.left_attr)
        level = getattr(node, self.level_attr)
        target_left = getattr(target, self.left_attr)
        target_right = getattr(target, self.right_attr)
        target_level = getattr(target, self.level_attr)

        if position == 'last-child' or position == 'first-child':
            if position == 'last-child':
                space_target = target_right - 1
            else:
                space_target = target_left
            level_change = level - target_level - 1
            parent = target
        elif position == 'left' or position == 'right':
            if position == 'left':
                space_target = target_left - 1
            else:
                space_target = target_right
            level_change = level - target_level
            parent = getattr(target, self.parent_attr)
        else:
            raise ValueError(_('An invalid position was given: %s.') % position)

        left_right_change = left - space_target - 1

        right_shift = 0
        if parent:
            right_shift = 2 * (node.get_descendant_count() + 1)

        return space_target, level_change, left_right_change, parent, right_shift

    def _close_gap(self, size, target, tree_id):
        """
        Closes a gap of a certain ``size`` after the given ``target``
        point in the tree identified by ``tree_id``.
        """
        self._manage_space(-size, target, tree_id)

    def _create_space(self, size, target, tree_id):
        """
        Creates a space of a certain ``size`` after the given ``target``
        point in the tree identified by ``tree_id``.
        """
        self._manage_space(size, target, tree_id)

    def _create_tree_space(self, target_tree_id, num_trees=1):
        """
        Creates space for a new tree by incrementing all tree ids
        greater than ``target_tree_id``.
        """
        qs = self._mptt_filter(tree_id__gt=target_tree_id)
        self._mptt_update(qs, tree_id=F(self.tree_id_attr) + num_trees)
        self.tree_model._mptt_track_tree_insertions(target_tree_id + 1, num_trees)

    def _get_next_tree_id(self):
        """
        Determines the next largest unused tree id for the tree managed
        by this manager.
        """
        qs = self.get_query_set()
        max_tree_id = qs.aggregate(Max(self.tree_id_attr)).values()[0]

        max_tree_id = max_tree_id or 0
        return max_tree_id + 1

    def _inter_tree_move_and_close_gap(self, node, level_change,
            left_right_change, new_tree_id, parent_pk=None):
        """
        Removes ``node`` from its current tree, with the given set of
        changes being applied to ``node`` and its descendants, closing
        the gap left by moving ``node`` as it does so.

        If ``parent_pk`` is ``None``, this indicates that ``node`` is
        being moved to a brand new tree as its root node, and will thus
        have its parent field set to ``NULL``. Otherwise, ``node`` will
        have ``parent_pk`` set for its parent field.
        """
        opts = self.model._meta
        inter_tree_move_query = """
        UPDATE %(table)s
        SET %(level)s = CASE
                WHEN %(left)s >= %%s AND %(left)s <= %%s
                    THEN %(level)s - %%s
                ELSE %(level)s END,
            %(tree_id)s = CASE
                WHEN %(left)s >= %%s AND %(left)s <= %%s
                    THEN %%s
                ELSE %(tree_id)s END,
            %(left)s = CASE
                WHEN %(left)s >= %%s AND %(left)s <= %%s
                    THEN %(left)s - %%s
                WHEN %(left)s > %%s
                    THEN %(left)s - %%s
                ELSE %(left)s END,
            %(right)s = CASE
                WHEN %(right)s >= %%s AND %(right)s <= %%s
                    THEN %(right)s - %%s
                WHEN %(right)s > %%s
                    THEN %(right)s - %%s
                ELSE %(right)s END,
            %(parent)s = CASE
                WHEN %(pk)s = %%s
                    THEN %(new_parent)s
                ELSE %(parent)s END
        WHERE %(tree_id)s = %%s""" % {
            'table': qn(self.tree_model._meta.db_table),
            'level': qn(opts.get_field(self.level_attr).column),
            'left': qn(opts.get_field(self.left_attr).column),
            'tree_id': qn(opts.get_field(self.tree_id_attr).column),
            'right': qn(opts.get_field(self.right_attr).column),
            'parent': qn(opts.get_field(self.parent_attr).column),
            'pk': qn(opts.pk.column),
            'new_parent': parent_pk is None and 'NULL' or '%s',
        }

        left = getattr(node, self.left_attr)
        right = getattr(node, self.right_attr)
        gap_size = right - left + 1
        gap_target_left = left - 1
        params = [
            left, right, level_change,
            left, right, new_tree_id,
            left, right, left_right_change,
            gap_target_left, gap_size,
            left, right, left_right_change,
            gap_target_left, gap_size,
            node.pk,
            getattr(node, self.tree_id_attr)
        ]
        if parent_pk is not None:
            params.insert(-1, parent_pk)

        cursor = self._get_connection(node).cursor()

        cursor.execute(inter_tree_move_query, params)

    def _make_child_root_node(self, node, new_tree_id=None):
        """
        Removes ``node`` from its tree, making it the root node of a new
        tree.

        If ``new_tree_id`` is not specified a new tree id will be
        generated.

        ``node`` will be modified to reflect its new tree state in the
        database.
        """
        left = getattr(node, self.left_attr)
        right = getattr(node, self.right_attr)
        level = getattr(node, self.level_attr)
        if not new_tree_id:
            new_tree_id = self._get_next_tree_id()
        left_right_change = left - 1

        self._inter_tree_move_and_close_gap(node, level, left_right_change, new_tree_id)

        # Update the node to be consistent with the updated
        # tree in the database.
        setattr(node, self.left_attr, left - left_right_change)
        setattr(node, self.right_attr, right - left_right_change)
        setattr(node, self.level_attr, 0)
        setattr(node, self.tree_id_attr, new_tree_id)
        setattr(node, self.parent_attr, None)
        node._mptt_cached_fields[self.parent_attr] = None

    def _make_sibling_of_root_node(self, node, target, position):
        """
        Moves ``node``, making it a sibling of the given ``target`` root
        node as specified by ``position``.

        ``node`` will be modified to reflect its new tree state in the
        database.

        Since we use tree ids to reduce the number of rows affected by
        tree mangement during insertion and deletion, root nodes are not
        true siblings; thus, making an item a sibling of a root node is
        a special case which involves shuffling tree ids around.
        """
        if node == target:
            raise InvalidMove(_('A node may not be made a sibling of itself.'))

        opts = self.model._meta
        tree_id = getattr(node, self.tree_id_attr)
        target_tree_id = getattr(target, self.tree_id_attr)

        if node.is_child_node():
            if position == 'left':
                space_target = target_tree_id - 1
                new_tree_id = target_tree_id
            elif position == 'right':
                space_target = target_tree_id
                new_tree_id = target_tree_id + 1
            else:
                raise ValueError(_('An invalid position was given: %s.') % position)

            self._create_tree_space(space_target)
            if tree_id > space_target:
                # The node's tree id has been incremented in the
                # database - this change must be reflected in the node
                # object for the method call below to operate on the
                # correct tree.
                setattr(node, self.tree_id_attr, tree_id + 1)
            self._make_child_root_node(node, new_tree_id)
        else:
            if position == 'left':
                if target_tree_id > tree_id:
                    left_sibling = target.get_previous_sibling()
                    if node == left_sibling:
                        return
                    new_tree_id = getattr(left_sibling, self.tree_id_attr)
                    lower_bound, upper_bound = tree_id, new_tree_id
                    shift = -1
                else:
                    new_tree_id = target_tree_id
                    lower_bound, upper_bound = new_tree_id, tree_id
                    shift = 1
            elif position == 'right':
                if target_tree_id > tree_id:
                    new_tree_id = target_tree_id
                    lower_bound, upper_bound = tree_id, target_tree_id
                    shift = -1
                else:
                    right_sibling = target.get_next_sibling()
                    if node == right_sibling:
                        return
                    new_tree_id = getattr(right_sibling, self.tree_id_attr)
                    lower_bound, upper_bound = new_tree_id, tree_id
                    shift = 1
            else:
                raise ValueError(_('An invalid position was given: %s.') % position)

            root_sibling_query = """
            UPDATE %(table)s
            SET %(tree_id)s = CASE
                WHEN %(tree_id)s = %%s
                    THEN %%s
                ELSE %(tree_id)s + %%s END
            WHERE %(tree_id)s >= %%s AND %(tree_id)s <= %%s""" % {
                'table': qn(self.tree_model._meta.db_table),
                'tree_id': qn(opts.get_field(self.tree_id_attr).column),
            }

            cursor = self._get_connection(node).cursor()
            cursor.execute(root_sibling_query, [tree_id, new_tree_id, shift,
                                                lower_bound, upper_bound])
            setattr(node, self.tree_id_attr, new_tree_id)

    def _manage_space(self, size, target, tree_id):
        """
        Manages spaces in the tree identified by ``tree_id`` by changing
        the values of the left and right columns by ``size`` after the
        given ``target`` point.
        """
        if self.tree_model._mptt_is_tracking:
            self.tree_model._mptt_track_tree_modified(tree_id)
        else:
            opts = self.model._meta
            space_query = """
            UPDATE %(table)s
            SET %(left)s = CASE
                    WHEN %(left)s > %%s
                        THEN %(left)s + %%s
                    ELSE %(left)s END,
                %(right)s = CASE
                    WHEN %(right)s > %%s
                        THEN %(right)s + %%s
                    ELSE %(right)s END
            WHERE %(tree_id)s = %%s
              AND (%(left)s > %%s OR %(right)s > %%s)""" % {
                'table': qn(self.tree_model._meta.db_table),
                'left': qn(opts.get_field(self.left_attr).column),
                'right': qn(opts.get_field(self.right_attr).column),
                'tree_id': qn(opts.get_field(self.tree_id_attr).column),
            }
            cursor = self._get_connection(self.model).cursor()
            cursor.execute(space_query, [target, size, target, size, tree_id,
                                         target, target])

    def _move_child_node(self, node, target, position):
        """
        Calls the appropriate method to move child node ``node``
        relative to the given ``target`` node as specified by
        ``position``.
        """
        tree_id = getattr(node, self.tree_id_attr)
        target_tree_id = getattr(target, self.tree_id_attr)

        if tree_id == target_tree_id:
            self._move_child_within_tree(node, target, position)
        else:
            self._move_child_to_new_tree(node, target, position)

    def _move_child_to_new_tree(self, node, target, position):
        """
        Moves child node ``node`` to a different tree, inserting it
        relative to the given ``target`` node in the new tree as
        specified by ``position``.

        ``node`` will be modified to reflect its new tree state in the
        database.
        """
        left = getattr(node, self.left_attr)
        right = getattr(node, self.right_attr)
        level = getattr(node, self.level_attr)
        new_tree_id = getattr(target, self.tree_id_attr)

        space_target, level_change, left_right_change, parent, new_parent_right = \
            self._calculate_inter_tree_move_values(node, target, position)

        tree_width = right - left + 1

        # Make space for the subtree which will be moved
        self._create_space(tree_width, space_target, new_tree_id)
        # Move the subtree
        self._inter_tree_move_and_close_gap(node, level_change,
            left_right_change, new_tree_id, parent.pk)

        # Update the node to be consistent with the updated
        # tree in the database.
        setattr(node, self.left_attr, left - left_right_change)
        setattr(node, self.right_attr, right - left_right_change)
        setattr(node, self.level_attr, level - level_change)
        setattr(node, self.tree_id_attr, new_tree_id)
        setattr(node, self.parent_attr, parent)

        node._mptt_cached_fields[self.parent_attr] = parent.pk

    def _move_child_within_tree(self, node, target, position):
        """
        Moves child node ``node`` within its current tree relative to
        the given ``target`` node as specified by ``position``.

        ``node`` will be modified to reflect its new tree state in the
        database.
        """
        left = getattr(node, self.left_attr)
        right = getattr(node, self.right_attr)
        level = getattr(node, self.level_attr)
        width = right - left + 1
        tree_id = getattr(node, self.tree_id_attr)
        target_left = getattr(target, self.left_attr)
        target_right = getattr(target, self.right_attr)
        target_level = getattr(target, self.level_attr)

        if position == 'last-child' or position == 'first-child':
            if node == target:
                raise InvalidMove(_('A node may not be made a child of itself.'))
            elif left < target_left < right:
                raise InvalidMove(_('A node may not be made a child of any of its descendants.'))
            if position == 'last-child':
                if target_right > right:
                    new_left = target_right - width
                    new_right = target_right - 1
                else:
                    new_left = target_right
                    new_right = target_right + width - 1
            else:
                if target_left > left:
                    new_left = target_left - width + 1
                    new_right = target_left
                else:
                    new_left = target_left + 1
                    new_right = target_left + width
            level_change = level - target_level - 1
            parent = target
        elif position == 'left' or position == 'right':
            if node == target:
                raise InvalidMove(_('A node may not be made a sibling of itself.'))
            elif left < target_left < right:
                raise InvalidMove(_('A node may not be made a sibling of any of its descendants.'))
            if position == 'left':
                if target_left > left:
                    new_left = target_left - width
                    new_right = target_left - 1
                else:
                    new_left = target_left
                    new_right = target_left + width - 1
            else:
                if target_right > right:
                    new_left = target_right - width + 1
                    new_right = target_right
                else:
                    new_left = target_right + 1
                    new_right = target_right + width
            level_change = level - target_level
            parent = getattr(target, self.parent_attr)
        else:
            raise ValueError(_('An invalid position was given: %s.') % position)

        left_boundary = min(left, new_left)
        right_boundary = max(right, new_right)
        left_right_change = new_left - left
        gap_size = width
        if left_right_change > 0:
            gap_size = -gap_size

        opts = self.model._meta
        # The level update must come before the left update to keep
        # MySQL happy - left seems to refer to the updated value
        # immediately after its update has been specified in the query
        # with MySQL, but not with SQLite or Postgres.
        move_subtree_query = """
        UPDATE %(table)s
        SET %(level)s = CASE
                WHEN %(left)s >= %%s AND %(left)s <= %%s
                  THEN %(level)s - %%s
                ELSE %(level)s END,
            %(left)s = CASE
                WHEN %(left)s >= %%s AND %(left)s <= %%s
                  THEN %(left)s + %%s
                WHEN %(left)s >= %%s AND %(left)s <= %%s
                  THEN %(left)s + %%s
                ELSE %(left)s END,
            %(right)s = CASE
                WHEN %(right)s >= %%s AND %(right)s <= %%s
                  THEN %(right)s + %%s
                WHEN %(right)s >= %%s AND %(right)s <= %%s
                  THEN %(right)s + %%s
                ELSE %(right)s END,
            %(parent)s = CASE
                WHEN %(pk)s = %%s
                  THEN %%s
                ELSE %(parent)s END
        WHERE %(tree_id)s = %%s""" % {
            'table': qn(self.tree_model._meta.db_table),
            'level': qn(opts.get_field(self.level_attr).column),
            'left': qn(opts.get_field(self.left_attr).column),
            'right': qn(opts.get_field(self.right_attr).column),
            'parent': qn(opts.get_field(self.parent_attr).column),
            'pk': qn(opts.pk.column),
            'tree_id': qn(opts.get_field(self.tree_id_attr).column),
        }

        cursor = self._get_connection(node).cursor()
        cursor.execute(move_subtree_query, [
            left, right, level_change,
            left, right, left_right_change,
            left_boundary, right_boundary, gap_size,
            left, right, left_right_change,
            left_boundary, right_boundary, gap_size,
            node.pk, parent.pk,
            tree_id])

        # Update the node to be consistent with the updated
        # tree in the database.
        setattr(node, self.left_attr, new_left)
        setattr(node, self.right_attr, new_right)
        setattr(node, self.level_attr, level - level_change)
        setattr(node, self.parent_attr, parent)
        node._mptt_cached_fields[self.parent_attr] = parent.pk

    def _move_root_node(self, node, target, position):
        """
        Moves root node``node`` to a different tree, inserting it
        relative to the given ``target`` node as specified by
        ``position``.

        ``node`` will be modified to reflect its new tree state in the
        database.
        """
        left = getattr(node, self.left_attr)
        right = getattr(node, self.right_attr)
        level = getattr(node, self.level_attr)
        tree_id = getattr(node, self.tree_id_attr)
        new_tree_id = getattr(target, self.tree_id_attr)
        width = right - left + 1

        if node == target:
            raise InvalidMove(_('A node may not be made a child of itself.'))
        elif tree_id == new_tree_id:
            raise InvalidMove(_('A node may not be made a child of any of its descendants.'))

        space_target, level_change, left_right_change, parent, right_shift = \
            self._calculate_inter_tree_move_values(node, target, position)

        # Create space for the tree which will be inserted
        self._create_space(width, space_target, new_tree_id)

        # Move the root node, making it a child node
        opts = self.model._meta
        move_tree_query = """
        UPDATE %(table)s
        SET %(level)s = %(level)s - %%s,
            %(left)s = %(left)s - %%s,
            %(right)s = %(right)s - %%s,
            %(tree_id)s = %%s,
            %(parent)s = CASE
                WHEN %(pk)s = %%s
                    THEN %%s
                ELSE %(parent)s END
        WHERE %(left)s >= %%s AND %(left)s <= %%s
          AND %(tree_id)s = %%s""" % {
            'table': qn(self.tree_model._meta.db_table),
            'level': qn(opts.get_field(self.level_attr).column),
            'left': qn(opts.get_field(self.left_attr).column),
            'right': qn(opts.get_field(self.right_attr).column),
            'tree_id': qn(opts.get_field(self.tree_id_attr).column),
            'parent': qn(opts.get_field(self.parent_attr).column),
            'pk': qn(opts.pk.column),
        }

        cursor = self._get_connection(node).cursor()
        cursor.execute(move_tree_query, [level_change, left_right_change,
            left_right_change, new_tree_id, node.pk, parent.pk, left, right,
            tree_id])

        # Update the former root node to be consistent with the updated
        # tree in the database.
        setattr(node, self.left_attr, left - left_right_change)
        setattr(node, self.right_attr, right - left_right_change)
        setattr(node, self.level_attr, level - level_change)
        setattr(node, self.tree_id_attr, new_tree_id)
        setattr(node, self.parent_attr, parent)
        node._mptt_cached_fields[self.parent_attr] = parent.pk
