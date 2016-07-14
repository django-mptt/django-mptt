"""
A custom manager for working with trees of objects.
"""
from __future__ import unicode_literals

import contextlib
from itertools import groupby
import warnings

from django.db import models, connections, router
from django.db.models import F, ManyToManyField, Max, Q
from django.utils.translation import ugettext as _

from mptt.exceptions import InvalidMove
from mptt.querysets import TreeQuerySet
from mptt.utils import _get_tree_model
from mptt.signals import node_moved


__all__ = ('TreeManager',)


COUNT_SUBQUERY = """(
    SELECT COUNT(*)
    FROM %(rel_table)s
    WHERE %(mptt_fk)s = %(mptt_table)s.%(mptt_rel_to)s
)"""

CUMULATIVE_COUNT_SUBQUERY = """(
    SELECT COUNT(*)
    FROM %(rel_table)s
    WHERE %(mptt_fk)s IN
    (
        SELECT m2.%(mptt_rel_to)s
        FROM %(mptt_table)s m2
        WHERE m2.tree_id = %(mptt_table)s.tree_id
          AND m2.lft BETWEEN %(mptt_table)s.lft
                              AND %(mptt_table)s.rght
    )
)"""

COUNT_SUBQUERY_M2M = """(
    SELECT COUNT(*)
    FROM %(rel_table)s j
    INNER JOIN %(rel_m2m_table)s k ON j.%(rel_pk)s = k.%(rel_m2m_column)s
    WHERE k.%(mptt_fk)s = %(mptt_table)s.%(mptt_pk)s
)"""

CUMULATIVE_COUNT_SUBQUERY_M2M = """(
    SELECT COUNT(*)
    FROM %(rel_table)s j
    INNER JOIN %(rel_m2m_table)s k ON j.%(rel_pk)s = k.%(rel_m2m_column)s
    WHERE k.%(mptt_fk)s IN
    (
        SELECT m2.%(mptt_pk)s
        FROM %(mptt_table)s m2
        WHERE m2.tree_id = %(mptt_table)s.tree_id
          AND m2.lft BETWEEN %(mptt_table)s.lft
                              AND %(mptt_table)s.rght
    )
)"""


class TreeManager(models.Manager.from_queryset(TreeQuerySet)):

    """
    A manager for working with trees of objects.
    """

    @contextlib.contextmanager
    def disable_mptt_updates(self):
        # Preserve API
        yield

    @contextlib.contextmanager
    def delay_mptt_updates(self):
        # Preserve API
        yield

    @property
    def tree_model(self):
        return _get_tree_model(self.model)

    def get_queryset(self, *args, **kwargs):
        """
        Ensures that this manager always returns nodes in tree order.
        """
        return super(TreeManager, self).get_queryset(
            *args, **kwargs
        ).order_by('tree_id', 'lft')

    def _get_queryset_relatives(self, queryset, direction, include_self):
        """
        Returns a queryset containing either the descendants
        ``direction == desc`` or the ancestors ``direction == asc`` of a given
        queryset.

        This function is not meant to be called directly, although there is no
        harm in doing so.

        Instead, it should be used via ``get_queryset_descendants()`` and/or
        ``get_queryset_ancestors()``.

        This function works by grouping contiguous siblings and using them to create
        a range that selects all nodes between the range, instead of querying for each
        node individually. Three variables are required when querying for ancestors or
        descendants: tree_id, lft, rght. If we weren't using ranges
        and our queryset contained 100 results, the resulting SQL query would contain
        300 variables. However, when using ranges, if the same queryset contained 10
        sets of contiguous siblings, then the resulting SQL query should only contain
        30 variables.

        The attributes used to create the range are completely
        dependent upon whether you are ascending or descending the tree.

        * Ascending (ancestor nodes): select all nodes whose right_attr is greater
          than (or equal to, if include_self = True) the smallest right_attr within
          the set of contiguous siblings, and whose lft is less than (or equal
          to) the largest lft within the set of contiguous siblings.

        * Descending (descendant nodes): select all nodes whose lft is greater
          than (or equal to, if include_self = True) the smallest lft within
          the set of contiguous siblings, and whose right_attr is less than (or equal
          to) the largest right_attr within the set of contiguous siblings.

        The result is the more contiguous siblings in the original queryset, the fewer
        SQL variables will be required to execute the query.
        """
        assert self.model is queryset.model

        opts = queryset.model._mptt_meta

        filters = Q()

        e = 'e' if include_self else ''
        max_op = 'lt' + e
        min_op = 'gt' + e
        if direction == 'asc':
            max_attr = 'lft'
            min_attr = 'rght'
        elif direction == 'desc':
            max_attr = 'rght'
            min_attr = 'lft'

        min_key = '%s__%s' % (min_attr, min_op)
        max_key = '%s__%s' % (max_attr, max_op)

        q = queryset.order_by('tree_id', 'parent', 'lft').only(
            'tree_id',
            'lft',
            'rght',
            min_attr,
            max_attr,
            'parent',
            # These fields are used by MPTTModel.update_mptt_cached_fields()
            *opts.order_insertion_by
        )

        if not q:
            return self.none()

        for group in groupby(
                q,
                key=lambda n: (
                    n.tree_id,
                    n.parent_id,
                )):
            next_lft = None
            for node in list(group[1]):
                tree, lft, rght, min_val, max_val = (
                    node.tree_id,
                    node.lft,
                    node.rght,
                    getattr(node, min_attr),
                    getattr(node, max_attr),
                )
                if next_lft is None:
                    next_lft = rght + 1
                    min_max = {'min': min_val, 'max': max_val}
                elif lft == next_lft:
                    if min_val < min_max['min']:
                        min_max['min'] = min_val
                    if max_val > min_max['max']:
                        min_max['max'] = max_val
                    next_lft = rght + 1
                elif lft != next_lft:
                    filters |= Q(**{
                        'tree_id': tree,
                        min_key: min_max['min'],
                        max_key: min_max['max'],
                    })
                    min_max = {'min': min_val, 'max': max_val}
                    next_lft = rght + 1
            filters |= Q(**{
                'tree_id': tree,
                min_key: min_max['min'],
                max_key: min_max['max'],
            })

        return self.filter(filters)

    def get_queryset_descendants(self, queryset, include_self=False):
        """
        Returns a queryset containing the descendants of all nodes in the
        given queryset.

        If ``include_self=True``, nodes in ``queryset`` will also
        be included in the result.
        """
        return self._get_queryset_relatives(queryset, 'desc', include_self)

    def get_queryset_ancestors(self, queryset, include_self=False):
        """
        Returns a queryset containing the ancestors
        of all nodes in the given queryset.

        If ``include_self=True``, nodes in ``queryset`` will also
        be included in the result.
        """
        return self._get_queryset_relatives(queryset, 'asc', include_self)

    def _translate_lookups(self, **lookups):
        new_lookups = {}
        join_parts = '__'.join
        for k, v in lookups.items():
            parts = k.split('__')
            new_parts = []
            new_parts__append = new_parts.append
            for part in parts:
                new_parts__append(getattr(self, part + '_attr', part))
            new_lookups[join_parts(new_parts)] = v
        return new_lookups

    def _mptt_filter(self, qs=None, **filters):
        """
        Like ``self.filter()``, but translates name-agnostic filters for MPTT
        fields.
        """
        if qs is None:
            qs = self
        return qs.filter(**self._translate_lookups(**filters))

    def _mptt_update(self, qs=None, **items):
        """
        Like ``self.update()``, but translates name-agnostic MPTT fields.
        """
        if qs is None:
            qs = self
        return qs.update(**self._translate_lookups(**items))

    def _get_connection(self, **hints):
        return connections[router.db_for_write(self.model, **hints)]

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
        connection = self._get_connection()
        qn = connection.ops.quote_name

        meta = self.model._meta
        mptt_field = rel_model._meta.get_field(rel_field)

        if isinstance(mptt_field, ManyToManyField):
            if cumulative:
                subquery = CUMULATIVE_COUNT_SUBQUERY_M2M % {
                    'rel_table': qn(rel_model._meta.db_table),
                    'rel_pk': qn(rel_model._meta.pk.column),
                    'rel_m2m_table': qn(mptt_field.m2m_db_table()),
                    'rel_m2m_column': qn(mptt_field.m2m_column_name()),
                    'mptt_fk': qn(mptt_field.m2m_reverse_name()),
                    'mptt_table': qn(self.tree_model._meta.db_table),
                    'mptt_pk': qn(meta.pk.column),
                }
            else:
                subquery = COUNT_SUBQUERY_M2M % {
                    'rel_table': qn(rel_model._meta.db_table),
                    'rel_pk': qn(rel_model._meta.pk.column),
                    'rel_m2m_table': qn(mptt_field.m2m_db_table()),
                    'rel_m2m_column': qn(mptt_field.m2m_column_name()),
                    'mptt_fk': qn(mptt_field.m2m_reverse_name()),
                    'mptt_table': qn(self.tree_model._meta.db_table),
                    'mptt_pk': qn(meta.pk.column),
                }
        else:
            if cumulative:
                subquery = CUMULATIVE_COUNT_SUBQUERY % {
                    'rel_table': qn(rel_model._meta.db_table),
                    'mptt_fk': qn(rel_model._meta.get_field(rel_field).column),
                    'mptt_table': qn(self.tree_model._meta.db_table),
                    'mptt_rel_to': qn(mptt_field.remote_field.field_name),
                }
            else:
                subquery = COUNT_SUBQUERY % {
                    'rel_table': qn(rel_model._meta.db_table),
                    'mptt_fk': qn(rel_model._meta.get_field(rel_field).column),
                    'mptt_table': qn(self.tree_model._meta.db_table),
                    'mptt_rel_to': qn(mptt_field.remote_field.field_name),
                }
        return queryset.extra(select={count_attr: subquery})

    def insert_node(self, node, target, position='last-child', save=False,
                    allow_existing_pk=False, refresh_target=True):
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

        NOTE: This is a low-level method; it does NOT respect
        ``MPTTMeta.order_insertion_by``.  In most cases you should just
        set the node's parent and let mptt call this during save.
        """

        if node.pk and not allow_existing_pk and self.filter(pk=node.pk).exists():
            raise ValueError(_('Cannot insert a node which has already been saved.'))

        if target is None:
            tree_id = self._get_next_tree_id()
            node.lft = 1
            node.rght = 2
            node.level = 0
            node.tree_id = tree_id
            node.parent = None
        elif target.is_root_node() and position in ['left', 'right']:
            if refresh_target:
                # Ensure mptt values on target are not stale.
                target.refresh_from_db(fields=(
                    'lft', 'rght', 'level', 'tree_id'))

            target_tree_id = target.tree_id
            if position == 'left':
                tree_id = target_tree_id
                space_target = target_tree_id - 1
            else:
                tree_id = target_tree_id + 1
                space_target = target_tree_id
            self._create_tree_space(space_target)

            node.lft = 1
            node.rght = 2
            node.level = 0
            node.tree_id = tree_id
            node.parent = None
        else:
            node.lft = 0
            node.level = 0

            if refresh_target:
                # Ensure mptt values on target are not stale.
                target.refresh_from_db(fields=(
                    'lft', 'rght', 'level', 'tree_id'))


            space_target, level, left, parent, right_shift = \
                self._calculate_inter_tree_move_values(node, target, position)

            self._manage_space(2, space_target, target.tree_id)

            node.lft = -left
            node.rght = -left + 1
            node.level = -level
            node.tree_id = target.tree_id
            node.parent = parent

            if parent:
                parent._mptt_refresh()

        if save:
            node.save()
        return node

    def _move_node(self, node, target, position='last-child', save=True, refresh_target=True):
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

        NOTE: This is a low-level method; it does NOT respect
        ``MPTTMeta.order_insertion_by``.  In most cases you should just
        move the node yourself by setting node.parent.
        """
        self._move_node(node, target, position=position)
        node_moved.send(sender=node.__class__, instance=node,
                        target=target, position=position)

    def root_node(self, tree_id):
        """
        Returns the root node of the tree with the given id.
        """
        return self._mptt_filter(tree_id=tree_id, parent=None).get()

    def root_nodes(self):
        """
        Creates a ``QuerySet`` containing root nodes.
        """
        return self._mptt_filter(parent=None)

    def rebuild(self):
        """
        Rebuilds all trees in the database table using `parent` link.
        """
        opts = self.model._mptt_meta

        qs = self._mptt_filter(parent=None)
        if opts.order_insertion_by:
            qs = qs.order_by(*opts.order_insertion_by)
        pks = qs.values_list('pk', flat=True)

        rebuild_helper = self._rebuild_helper
        idx = 0
        for pk in pks:
            idx += 1
            rebuild_helper(pk, 1, idx)
    rebuild.alters_data = True

    def partial_rebuild(self, tree_id):
        """
        Partially rebuilds a tree i.e. It rebuilds only the tree with given
        ``tree_id`` in database table using ``parent`` link.
        """
        opts = self.model._mptt_meta

        qs = self._mptt_filter(parent=None, tree_id=tree_id)
        if opts.order_insertion_by:
            qs = qs.order_by(*opts.order_insertion_by)
        pks = qs.values_list('pk', flat=True)
        if not pks:
            return
        if len(pks) > 1:
            raise RuntimeError(
                "More than one root node with tree_id %d. That's invalid,"
                " do a full rebuild." % tree_id)

        self._rebuild_helper(pks[0], 1, tree_id)

    def _rebuild_helper(self, pk, left, tree_id, level=0):
        opts = self.model._mptt_meta
        right = left + 1

        qs = self._mptt_filter(parent__pk=pk)
        if opts.order_insertion_by:
            qs = qs.order_by(*opts.order_insertion_by)
        child_ids = qs.values_list('pk', flat=True)

        rebuild_helper = self._rebuild_helper
        for child_id in child_ids:
            right = rebuild_helper(child_id, right, tree_id, level + 1)

        qs = self.model._default_manager.filter(pk=pk)
        self._mptt_update(
            qs,
            lft=left,
            rght=right,
            level=level,
            tree_id=tree_id
        )

        return right + 1

    def _calculate_inter_tree_move_values(self, node, target, position):
        """
        Calculates values required when moving ``node`` relative to
        ``target`` as specified by ``position``.
        """
        left = node.lft
        level = node.level
        target_left = target.lft
        target_right = target.rght
        target_level = target.level

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
            parent = target.parent
        else:
            raise ValueError(_('An invalid position was given: %s.') % position)

        left_right_change = left - space_target - 1

        right_shift = 0
        if parent:
            right_shift = 2 * (node.get_descendant_count() + 1)

        return space_target, level_change, left_right_change, parent, right_shift

    def _create_tree_space(self, target_tree_id, num_trees=1):
        """
        Creates space for a new tree by incrementing all tree ids
        greater than ``target_tree_id``.
        """
        qs = self._mptt_filter(tree_id__gt=target_tree_id)
        self._mptt_update(qs, tree_id=F('tree_id') + num_trees)

    def _get_next_tree_id(self):
        """
        Determines the next largest unused tree id for the tree managed
        by this manager.
        """
        return 1 + (self.aggregate(m=Max('tree_id'))['m'] or 0)

    def _inter_tree_move_and_close_gap(
            self, node, level_change,
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
        connection = self._get_connection(instance=node)
        qn = connection.ops.quote_name

        opts = self.model._meta
        inter_tree_move_query = """
        UPDATE %(table)s
        SET level = CASE
                WHEN lft >= %%s AND lft <= %%s
                    THEN level - %%s
                ELSE level END,
            tree_id = CASE
                WHEN lft >= %%s AND lft <= %%s
                    THEN %%s
                ELSE tree_id END,
            lft = CASE
                WHEN lft >= %%s AND lft <= %%s
                    THEN lft - %%s
                WHEN lft > %%s
                    THEN lft - %%s
                ELSE lft END,
            rght = CASE
                WHEN rght >= %%s AND rght <= %%s
                    THEN rght - %%s
                WHEN rght > %%s
                    THEN rght - %%s
                ELSE rght END,
            %(parent)s = CASE
                WHEN %(pk)s = %%s
                    THEN %(new_parent)s
                ELSE %(parent)s END
        WHERE tree_id = %%s""" % {
            'table': qn(self.tree_model._meta.db_table),
            'parent': qn(opts.get_field('parent').column),
            'pk': qn(opts.pk.column),
            'new_parent': parent_pk is None and 'NULL' or '%s',
        }

        left = node.lft
        right = node.rght
        gap_size = right - left + 1
        gap_target_left = left - 1
        params = [
            left, right, level_change,
            left, right, new_tree_id,
            left, right, left_right_change,
            gap_target_left, gap_size,
            left, right, left_right_change,
            gap_target_left, gap_size,
            node._meta.pk.get_db_prep_value(node.pk, connection),
            node.tree_id,
        ]
        if parent_pk is not None:
            params.insert(-1, parent_pk)

        cursor = connection.cursor()
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
        left = node.lft
        right = node.rght
        level = node.level
        if not new_tree_id:
            new_tree_id = self._get_next_tree_id()
        left_right_change = left - 1

        self._inter_tree_move_and_close_gap(node, level, left_right_change, new_tree_id)

        # Update the node to be consistent with the updated
        # tree in the database.
        node.lft = left - left_right_change
        node.rght = right - left_right_change
        node.level = 0
        node.tree_id = new_tree_id
        node.parent = None
        node._mptt_cached_fields['parent'] = None

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
        tree_id = node.tree_id
        target_tree_id = target.tree_id

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
                node.tree_id = tree_id + 1
            self._make_child_root_node(node, new_tree_id)
        else:
            if position == 'left':
                if target_tree_id > tree_id:
                    left_sibling = target.get_previous_sibling()
                    if node == left_sibling:
                        return
                    new_tree_id = left_sibling.tree_id
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
                    new_tree_id = right_sibling.tree_id
                    lower_bound, upper_bound = new_tree_id, tree_id
                    shift = 1
            else:
                raise ValueError(_('An invalid position was given: %s.') % position)

            connection = self._get_connection(instance=node)
            qn = connection.ops.quote_name

            root_sibling_query = """
            UPDATE %(table)s
            SET tree_id = CASE
                WHEN tree_id = %%s
                    THEN %%s
                ELSE tree_id + %%s END
            WHERE tree_id >= %%s AND tree_id <= %%s""" % {
                'table': qn(self.tree_model._meta.db_table),
            }

            cursor = connection.cursor()
            cursor.execute(root_sibling_query, [tree_id, new_tree_id, shift,
                                                lower_bound, upper_bound])
            node.tree_id = new_tree_id

    def _manage_space(self, width, right_of, tree_id):
        """
        Manages spaces in the tree identified by ``tree_id`` by changing
        the values of the left and right columns by ``width`` after the
        given ``right_of`` point.
        """
        connection = self._get_connection()
        qn = connection.ops.quote_name

        opts = self.model._meta
        space_query = """
        UPDATE %(table)s
        SET lft = CASE
                WHEN lft > %%s
                    THEN lft + %%s
                ELSE lft END,
            rght = CASE
                WHEN rght > %%s
                    THEN rght + %%s
                ELSE rght END
        WHERE tree_id = %%s
          AND (lft > %%s OR rght > %%s)""" % {
            'table': qn(self.tree_model._meta.db_table),
        }
        cursor = connection.cursor()
        cursor.execute(space_query, [
            right_of, width, right_of, width, tree_id, right_of, right_of
        ])

    def _move_child_node(self, node, target, position):
        """
        Calls the appropriate method to move child node ``node``
        relative to the given ``target`` node as specified by
        ``position``.
        """
        tree_id = node.tree_id
        target_tree_id = target.tree_id

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
        left = node.lft
        right = node.rght
        level = node.level
        new_tree_id = target.tree_id

        space_target, level_change, left_right_change, parent, new_parent_right = \
            self._calculate_inter_tree_move_values(node, target, position)

        tree_width = right - left + 1

        # Make space for the subtree which will be moved
        self._manage_space(tree_width, space_target, new_tree_id)
        # Move the subtree
        connection = self._get_connection(instance=node)
        self._inter_tree_move_and_close_gap(
            node, level_change, left_right_change, new_tree_id,
            parent._meta.pk.get_db_prep_value(parent.pk, connection))

        # Update the node to be consistent with the updated
        # tree in the database.
        node._mptt_refresh()
        node.parent = parent
        node._mptt_cached_fields['parent'] = parent.pk

    def _move_child_within_tree(self, node, target, position):
        """
        Moves child node ``node`` within its current tree relative to
        the given ``target`` node as specified by ``position``.

        ``node`` will be modified to reflect its new tree state in the
        database.
        """
        left = node.lft
        right = node.rght
        level = node.level
        width = right - left + 1
        tree_id = node.tree_id
        target_left = target.lft
        target_right = target.rght
        target_level = target.level

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
            parent = target.parent
        else:
            raise ValueError(_('An invalid position was given: %s.') % position)

        left_boundary = min(left, new_left)
        right_boundary = max(right, new_right)
        left_right_change = new_left - left
        gap_size = width
        if left_right_change > 0:
            gap_size = -gap_size

        connection = self._get_connection(instance=node)
        qn = connection.ops.quote_name

        opts = self.model._meta
        # The level update must come before the left update to keep
        # MySQL happy - left seems to refer to the updated value
        # immediately after its update has been specified in the query
        # with MySQL, but not with SQLite or Postgres.
        move_subtree_query = """
        UPDATE %(table)s
        SET level = CASE
                WHEN lft >= %%s AND lft <= %%s
                  THEN level - %%s
                ELSE level END,
            lft = CASE
                WHEN lft >= %%s AND lft <= %%s
                  THEN lft + %%s
                WHEN lft >= %%s AND lft <= %%s
                  THEN lft + %%s
                ELSE lft END,
            rght = CASE
                WHEN rght >= %%s AND rght <= %%s
                  THEN rght + %%s
                WHEN rght >= %%s AND rght <= %%s
                  THEN rght + %%s
                ELSE rght END,
            %(parent)s = CASE
                WHEN %(pk)s = %%s
                  THEN %%s
                ELSE %(parent)s END
        WHERE tree_id = %%s""" % {
            'table': qn(self.tree_model._meta.db_table),
            'parent': qn(opts.get_field('parent').column),
            'pk': qn(opts.pk.column),
        }

        cursor = connection.cursor()
        cursor.execute(move_subtree_query, [
            left, right, level_change,
            left, right, left_right_change,
            left_boundary, right_boundary, gap_size,
            left, right, left_right_change,
            left_boundary, right_boundary, gap_size,
            node._meta.get_field(node._meta.pk.name).get_db_prep_value(node.pk, connection),
            parent._meta.get_field(parent._meta.pk.name).get_db_prep_value(parent.pk, connection),
            tree_id])

        # Update the node to be consistent with the updated
        # tree in the database.
        node._mptt_refresh()
        node.parent = parent
        node._mptt_cached_fields['parent'] = parent.pk

    def _move_root_node(self, node, target, position):
        """
        Moves root node``node`` to a different tree, inserting it
        relative to the given ``target`` node as specified by
        ``position``.

        ``node`` will be modified to reflect its new tree state in the
        database.
        """
        left = node.lft
        right = node.rght
        level = node.level
        tree_id = node.tree_id
        new_tree_id = target.tree_id
        width = right - left + 1

        if node == target:
            raise InvalidMove(_('A node may not be made a child of itself.'))
        elif tree_id == new_tree_id:
            raise InvalidMove(_('A node may not be made a child of any of its descendants.'))

        space_target, level_change, left_right_change, parent, right_shift = \
            self._calculate_inter_tree_move_values(node, target, position)

        # Create space for the tree which will be inserted
        self._manage_space(width, space_target, new_tree_id)

        # Move the root node, making it a child node
        connection = self._get_connection(instance=node)
        qn = connection.ops.quote_name

        opts = self.model._meta
        move_tree_query = """
        UPDATE %(table)s
        SET level = level - %%s,
            lft = lft - %%s,
            rght = rght - %%s,
            tree_id = %%s,
            %(parent)s = CASE
                WHEN %(pk)s = %%s
                    THEN %%s
                ELSE %(parent)s END
        WHERE lft >= %%s AND lft <= %%s
          AND tree_id = %%s""" % {
            'table': qn(self.tree_model._meta.db_table),
            'parent': qn(opts.get_field('parent').column),
            'pk': qn(opts.pk.column),
        }

        cursor = connection.cursor()
        cursor.execute(move_tree_query, [
            level_change, left_right_change, left_right_change,
            new_tree_id,
            node._meta.pk.get_db_prep_value(node.pk, connection),
            parent._meta.pk.get_db_prep_value(parent.pk, connection),
            left, right, tree_id])

        self._create_tree_space(tree_id, -1)

        # Update the former root node to be consistent with the updated
        # tree in the database.
        node._mptt_refresh()
        node.parent = parent
        node._mptt_cached_fields['parent'] = parent.pk
