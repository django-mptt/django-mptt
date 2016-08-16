from __future__ import unicode_literals

from functools import reduce, wraps
import operator
import warnings

import django
from django.db import models
from django.db.models import F, Q
from django.db.models.base import ModelBase
from django.db.models.query_utils import DeferredAttribute
from django.utils import six

from mptt.fields import TreeForeignKey, TreeOneToOneField, TreeManyToManyField
from mptt.managers import TreeManager
from mptt.signals import node_moved


__all__ = (
    'TreeForeignKey', 'TreeOneToOneField', 'TreeManyToManyField',
    'TreeManager', 'MPTTOptions', 'MPTTModelBase', 'MPTTModel',
)


class MPTTOptions(object):
    """
    Options class for MPTT models. Use this as an inner class called ``MPTTMeta``::

        class MyModel(MPTTModel):
            class MPTTMeta:
                order_insertion_by = ['name']
    """

    order_insertion_by = []

    @property
    def parent_attr(self):
        warnings.warn('Use "parent(_id)" directly.', DeprecationWarning, stacklevel=2)
        return 'parent'

    @property
    def left_attr(self):
        warnings.warn('Use "lft" directly.', DeprecationWarning, stacklevel=2)
        return 'lft'

    @property
    def right_attr(self):
        warnings.warn('Use "rght" directly.', DeprecationWarning, stacklevel=2)
        return 'rght'

    @property
    def tree_id_attr(self):
        warnings.warn('Use "tree_id" directly.', DeprecationWarning, stacklevel=2)
        return 'tree_id'

    @property
    def level_attr(self):
        warnings.warn('Use "level" directly.', DeprecationWarning, stacklevel=2)
        return 'level'

    def __init__(self, opts=None, **kwargs):
        # Override defaults with options provided
        if opts:
            opts = list(opts.__dict__.items())
        else:
            opts = []
        opts.extend(list(kwargs.items()))

        if 'tree_manager_attr' in [opt[0] for opt in opts]:
            raise ValueError(
                "`tree_manager_attr` has been removed; you should instantiate"
                " a TreeManager as a normal manager on your model instead.")

        for key, value in opts:
            if key[:2] == '__':
                continue
            setattr(self, key, value)

        # Normalize order_insertion_by to a list
        if isinstance(self.order_insertion_by, six.string_types):
            self.order_insertion_by = [self.order_insertion_by]
        elif isinstance(self.order_insertion_by, tuple):
            self.order_insertion_by = list(self.order_insertion_by)
        elif self.order_insertion_by is None:
            self.order_insertion_by = []

    def __iter__(self):
        return ((k, v) for k, v in self.__dict__.items() if k[0] != '_')

    # Helper methods for accessing tree attributes on models.
    def get_raw_field_value(self, instance, field_name):
        """
        Gets the value of the given fieldname for the instance.
        This is not the same as getattr().
        This function will return IDs for foreignkeys etc, rather than doing
        a database query.
        """
        field = instance._meta.get_field(field_name)
        return field.value_from_object(instance)

    def set_raw_field_value(self, instance, field_name, value):
        """
        Sets the value of the given fieldname for the instance.
        This is not the same as setattr().
        This function requires an ID for a foreignkey (etc) rather than an instance.
        """
        field = instance._meta.get_field(field_name)
        setattr(instance, field.attname, value)

    def update_mptt_cached_fields(self, instance):
        """
        Caches (in an instance._mptt_cached_fields dict) the original values of:
         - parent pk
         - fields specified in order_insertion_by

        These are used in save() to determine if the relevant fields have changed,
        so that the MPTT fields need to be updated.
        """
        instance._mptt_cached_fields = {}
        field_names = set(('parent',))
        if self.order_insertion_by:
            for f in self.order_insertion_by:
                if f[0] == '-':
                    f = f[1:]
                field_names.add(f)
        deferred_fields = instance.get_deferred_fields()
        for field_name in field_names:
            if deferred_fields:
                field = instance._meta.get_field(field_name)
                if field.attname in deferred_fields \
                        and field.attname not in instance.__dict__:
                    # deferred attribute (i.e. via .only() or .defer())
                    # It'd be silly to cache this (that'd do a database query)
                    # Instead, we mark it as a deferred attribute here, then
                    # assume it hasn't changed during save(), unless it's no
                    # longer deferred.
                    instance._mptt_cached_fields[field_name] = DeferredAttribute
                    continue
            instance._mptt_cached_fields[field_name] = self.get_raw_field_value(
                instance, field_name)

    def insertion_target_filters(self, instance, order_insertion_by):
        """
        Creates a filter which matches suitable right siblings for ``node``,
        where insertion should maintain ordering according to the list of
        fields in ``order_insertion_by``.

        For example, given an ``order_insertion_by`` of
        ``['field1', 'field2', 'field3']``, the resulting filter should
        correspond to the following SQL::

           field1 > %s
           OR (field1 = %s AND field2 > %s)
           OR (field1 = %s AND field2 = %s AND field3 > %s)

        """
        fields = []
        filters = []
        fields__append = fields.append
        filters__append = filters.append
        and_ = operator.and_
        or_ = operator.or_
        for field_name in order_insertion_by:
            if field_name[0] == '-':
                field_name = field_name[1:]
                filter_suffix = '__lt'
            else:
                filter_suffix = '__gt'
            value = getattr(instance, field_name)
            if value is None:
                # node isn't saved yet. get the insertion value from pre_save.
                field = instance._meta.get_field(field_name)
                value = field.pre_save(instance, True)

            q = Q(**{field_name + filter_suffix: value})

            filters__append(reduce(and_, [Q(**{f: v}) for f, v in fields] + [q]))
            fields__append((field_name, value))
        return reduce(or_, filters)

    def get_ordered_insertion_target(self, node, parent):
        """
        Attempts to retrieve a suitable right sibling for ``node``
        underneath ``parent`` (which may be ``None`` in the case of root
        nodes) so that ordering by the fields specified by the node's class'
        ``order_insertion_by`` option is maintained.

        Returns ``None`` if no suitable sibling can be found.
        """
        right_sibling = None
        # Optimisation - if the parent doesn't have descendants,
        # the node will always be its last child.
        if parent is None or parent.get_descendant_count() > 0:
            opts = node._mptt_meta
            order_by = opts.order_insertion_by[:]
            filters = self.insertion_target_filters(node, order_by)
            if parent:
                filters = filters & Q(parent=parent)
                # Fall back on tree ordering if multiple child nodes have
                # the same values.
                order_by.append('lft')
            else:
                filters = filters & Q(parent=None)
                # Fall back on tree id ordering if multiple root nodes have
                # the same values.
                order_by.append('tree_id')
            queryset = node._tree_manager.db_manager(
                node._state.db).filter(filters).order_by(*order_by)
            if node.pk:
                queryset = queryset.exclude(pk=node.pk)
            try:
                right_sibling = queryset[:1][0]
            except IndexError:
                # No suitable right sibling could be found
                pass
        return right_sibling


class MPTTModelBase(ModelBase):
    """
    Metaclass for MPTT models
    """

    def __new__(meta, class_name, bases, class_dict):
        """
        Create subclasses of MPTTModel. This:
         - adds the MPTT fields to the class
         - adds a TreeManager to the model
        """
        if class_name == 'NewBase' and class_dict == {}:
            return super(MPTTModelBase, meta).__new__(meta, class_name, bases, class_dict)
        is_MPTTModel = False
        try:
            MPTTModel
        except NameError:
            is_MPTTModel = True

        MPTTMeta = class_dict.pop('MPTTMeta', None)
        if not MPTTMeta:
            class MPTTMeta:
                pass

        initial_options = frozenset(dir(MPTTMeta))

        # extend MPTTMeta from base classes
        for base in bases:
            if hasattr(base, '_mptt_meta'):
                for name, value in base._mptt_meta:
                    if name == 'tree_manager_attr':
                        continue
                    if name not in initial_options:
                        setattr(MPTTMeta, name, value)

        class_dict['_mptt_meta'] = MPTTOptions(MPTTMeta)
        super_new = super(MPTTModelBase, meta).__new__
        cls = super_new(meta, class_name, bases, class_dict)

        if not is_MPTTModel:
            # Add a tree manager, if there isn't one already
            # NOTE: Django 1.10 lets models inherit managers without handholding.
            if django.VERSION < (1, 10) and not cls._meta.abstract:
                manager = getattr(cls, 'objects', None)
                if manager is None:
                    manager = cls._default_manager._copy_to_model(cls)
                    manager.contribute_to_class(cls, 'objects')
                elif manager.model != cls:
                    # manager was inherited
                    manager = manager._copy_to_model(cls)
                    manager.contribute_to_class(cls, 'objects')

                # make sure we have a tree manager somewhere
                tree_manager = None
                if hasattr(cls._meta, 'concrete_managers'):  # Django < 1.10
                    cls_managers = cls._meta.concrete_managers + cls._meta.abstract_managers
                    cls_managers = [r[2] for r in cls_managers]
                else:
                    cls_managers = cls._meta.managers

                for cls_manager in cls_managers:
                    if isinstance(cls_manager, TreeManager):
                        # prefer any locally defined manager (i.e. keep going if not local)
                        if cls_manager.model is cls:
                            tree_manager = cls_manager
                            break

                if tree_manager and tree_manager.model is not cls:
                    tree_manager = tree_manager._copy_to_model(cls)
                elif tree_manager is None:
                    tree_manager = TreeManager()
                tree_manager.contribute_to_class(cls, '_default_manager')

        return cls


def raise_if_unsaved(func):
    @wraps(func)
    def _fn(self, *args, **kwargs):
        if not self.pk:
            raise ValueError(
                'Cannot call %(function)s on unsaved %(class)s instances'
                % {'function': func.__name__, 'class': self.__class__.__name__}
            )
        return func(self, *args, **kwargs)
    return _fn


class MPTTModel(six.with_metaclass(MPTTModelBase, models.Model)):
    """
    Base class for tree models.
    """

    lft = models.PositiveIntegerField(db_index=True, editable=False)
    rght = models.PositiveIntegerField(db_index=True, editable=False)
    tree_id = models.PositiveIntegerField(db_index=True, editable=False)
    level = models.PositiveIntegerField(db_index=True, editable=False)

    objects = TreeManager()

    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs):
        super(MPTTModel, self).__init__(*args, **kwargs)
        self._mptt_meta.update_mptt_cached_fields(self)

    @property
    def _tree_manager(self):
        """
        Returns the default manager for the model whose table contains the MPTT
        bookkeeping attributes.
        """
        return self.__class__._default_manager.tree_model._default_manager

    @raise_if_unsaved
    def get_ancestors(self, ascending=False, include_self=False):
        """
        Creates a ``QuerySet`` containing the ancestors of this model
        instance.

        This defaults to being in descending order (root ancestor first,
        immediate parent last); passing ``True`` for the ``ascending``
        argument will reverse the ordering (immediate parent first, root
        ancestor last).

        If ``include_self`` is ``True``, the ``QuerySet`` will also
        include this model instance.
        """
        if self.is_root_node():
            if not include_self:
                return self._tree_manager.none()
            else:
                # Filter on pk for efficiency.
                qs = self._tree_manager.filter(pk=self.pk)
        else:
            order_by = 'lft'
            if ascending:
                order_by = '-' + order_by

            left = self.lft
            right = self.rght

            if not include_self:
                left -= 1
                right += 1

            qs = self._tree_manager.filter(
                lft__lte=left,
                rght__gte=right,
                tree_id=self.tree_id,
            )

            qs = qs.order_by(order_by)

        if hasattr(self, '_mptt_use_cached_ancestors'):
            # Called during or after a `recursetree` tag.
            # There should be cached parents up to level 0.
            # So we can use them to avoid doing a query at all.
            ancestors = []
            p = self
            if not include_self:
                p = p.parent

            while p is not None:
                ancestors.append(p)
                p = p.parent

            ancestors.reverse()
            qs._result_cache = ancestors

        return qs

    @raise_if_unsaved
    def get_family(self):
        """
        Returns a ``QuerySet`` containing the ancestors, the model itself
        and the descendants, in tree order.
        """
        ancestors = Q(
            lft__lte=self.lft,
            rght__gte=self.rght,
            tree_id=self.tree_id,
        )

        descendants = Q(
            lft__gte=self.lft,
            rght__lte=self.rght,
            tree_id=self.tree_id,
        )

        return self._tree_manager.filter(ancestors | descendants)

    @raise_if_unsaved
    def get_children(self):
        """
        Returns a ``QuerySet`` containing the immediate children of this
        model instance, in tree order.

        The benefit of using this method over the reverse relation
        provided by the ORM to the instance's children is that a
        database query can be avoided in the case where the instance is
        a leaf node (it has no children).

        If called from a template where the tree has been walked by the
        ``cache_tree_children`` filter, no database query is required.
        """
        if hasattr(self, '_cached_children'):
            qs = self._tree_manager.filter(pk__in=[n.pk for n in self._cached_children])
            qs._result_cache = self._cached_children
            return qs
        else:
            if self.is_leaf_node():
                return self._tree_manager.none()

            return self._tree_manager.filter(parent=self)

    @raise_if_unsaved
    def get_descendants(self, include_self=False):
        """
        Creates a ``QuerySet`` containing descendants of this model
        instance, in tree order.

        If ``include_self`` is ``True``, the ``QuerySet`` will also
        include this model instance.
        """
        if self.is_leaf_node():
            if not include_self:
                return self._tree_manager.none()
            else:
                return self._tree_manager.filter(pk=self.pk)

        return self._tree_manager.filter(
            tree_id=self.tree_id,
            lft__range=[self.lft + (0 if include_self else 1), self.rght],
        )

    def get_descendant_count(self):
        """
        Returns the number of descendants this model instance has.

        Returns 0 if node is not saved yet.
        """
        return 0 if self.rght is None else (self.rght - self.lft - 1) // 2

    @raise_if_unsaved
    def get_leafnodes(self, include_self=False):
        """
        Creates a ``QuerySet`` containing leafnodes of this model
        instance, in tree order.

        If ``include_self`` is ``True``, the ``QuerySet`` will also
        include this model instance (if it is a leaf node)
        """
        descendants = self.get_descendants(include_self=include_self)

        return descendants.filter(
            lft=F('rght') - 1,
        )

    @raise_if_unsaved
    def get_next_sibling(self, *filter_args, **filter_kwargs):
        """
        Returns this model instance's next sibling in the tree, or
        ``None`` if it doesn't have a next sibling.
        """
        qs = self._tree_manager.filter(*filter_args, **filter_kwargs)
        if self.is_root_node():
            qs = qs.filter(
                parent=None,
                tree_id__gt=self.tree_id,
            )
        else:
            qs = qs.filter(
                parent__pk=self.parent_id,
                lft__gt=self.rght,
            )

        siblings = qs[:1]
        return siblings and siblings[0] or None

    @raise_if_unsaved
    def get_previous_sibling(self, *filter_args, **filter_kwargs):
        """
        Returns this model instance's previous sibling in the tree, or
        ``None`` if it doesn't have a previous sibling.
        """
        qs = self._tree_manager.filter(*filter_args, **filter_kwargs)
        if self.is_root_node():
            qs = qs.filter(
                parent=None,
                tree_id__lt=self.tree_id,
            )
            qs = qs.order_by('-tree_id')
        else:
            qs = qs.filter(
                parent__pk=self.parent_id,
                rght__lt=self.lft,
            )
            qs = qs.order_by('-rght')

        siblings = qs[:1]
        return siblings and siblings[0] or None

    @raise_if_unsaved
    def get_root(self):
        """
        Returns the root node of this model instance's tree.
        """
        if self.is_root_node() and type(self) == self._tree_manager.tree_model:
            return self

        return self._tree_manager.filter(
            tree_id=self.tree_id,
            parent=None,
        ).get()

    @raise_if_unsaved
    def get_siblings(self, include_self=False):
        """
        Creates a ``QuerySet`` containing siblings of this model
        instance. Root nodes are considered to be siblings of other root
        nodes.

        If ``include_self`` is ``True``, the ``QuerySet`` will also
        include this model instance.
        """
        if self.is_root_node():
            queryset = self._tree_manager.filter(parent=None)
        else:
            queryset = self._tree_manager.filter(parent__pk=self.parent_id)
        if not include_self:
            queryset = queryset.exclude(pk=self.pk)
        return queryset

    def get_level(self):
        """
        Returns the level of this node (distance from root)
        """
        return self.level

    def is_child_node(self):
        """
        Returns ``True`` if this model instance is a child node, ``False``
        otherwise.
        """
        return self.parent_id is not None

    def is_leaf_node(self):
        """
        Returns ``True`` if this model instance is a leaf node (it has no
        children), ``False`` otherwise.
        """
        return not self.get_descendant_count()

    def is_root_node(self):
        """
        Returns ``True`` if this model instance is a root node,
        ``False`` otherwise.
        """
        return self.parent_id is None

    @raise_if_unsaved
    def is_descendant_of(self, other, include_self=False):
        """
        Returns ``True`` if this model is a descendant of the given node,
        ``False`` otherwise.
        If include_self is True, also returns True if the two nodes are the same node.
        """
        if include_self and other.pk == self.pk:
            return True

        if self.tree_id != other.tree_id:
            return False

        return self.lft > other.lft and self.rght < other.rght

    @raise_if_unsaved
    def is_ancestor_of(self, other, include_self=False):
        """
        Returns ``True`` if this model is an ancestor of the given node,
        ``False`` otherwise.
        If include_self is True, also returns True if the two nodes are the same node.
        """
        if include_self and other.pk == self.pk:
            return True
        return other.is_descendant_of(self)

    def insert_at(self, target, position='first-child', save=False,
                  allow_existing_pk=False, refresh_target=True):
        """
        Convenience method for calling ``TreeManager.insert_node`` with this
        model instance.
        """
        self._tree_manager.insert_node(
            self, target, position, save, allow_existing_pk=allow_existing_pk,
            refresh_target=refresh_target)

    def move_to(self, target, position='first-child'):
        """
        Convenience method for calling ``TreeManager.move_node`` with this
        model instance.

        NOTE: This is a low-level method; it does NOT respect ``MPTTMeta.order_insertion_by``.
        In most cases you should just move the node yourself by setting node.parent.
        """
        self._tree_manager.move_node(self, target, position)

    def _is_saved(self, using=None):
        if not self.pk or self.tree_id is None:
            return False
        opts = self._meta
        if opts.pk.remote_field is None:
            return True
        else:
            if not hasattr(self, '_mptt_saved'):
                manager = self.__class__._base_manager
                manager = manager.using(using)
                self._mptt_saved = manager.filter(pk=self.pk).exists()
            return self._mptt_saved

    def _get_user_field_names(self):
        """ Returns the list of user defined (i.e. non-mptt internal) field names. """
        from django.db.models import AutoField

        field_names = []
        internal_fields = ('lft', 'rght', 'tree_id', 'level')
        for field in self._meta.fields:
            if (field.name not in internal_fields) and (not isinstance(field, AutoField)) and (not field.primary_key):  # noqa
                field_names.append(field.name)
        return field_names

    def save(self, **kwargs):
        """
        If this is a new node, sets tree fields up before it is inserted
        into the database, making room in the tree structure as neccessary,
        defaulting to making the new node the last child of its parent.

        It the node's left and right edge indicators already been set, we
        take this as indication that the node has already been set up for
        insertion, so its tree fields are left untouched.

        If this is an existing node and its parent has been changed,
        performs reparenting in the tree structure, defaulting to making the
        node the last child of its new parent.

        In either case, if the node's class has its ``order_insertion_by``
        tree option set, the node will be inserted or moved to the
        appropriate position to maintain ordering by the specified field.
        """

        opts = self._mptt_meta
        parent_id = opts.get_raw_field_value(self, 'parent')

        # determine whether this instance is already in the db
        force_update = kwargs.get('force_update', False)
        force_insert = kwargs.get('force_insert', False)
        deferred_fields = self.get_deferred_fields()
        if force_update or (not force_insert and self._is_saved(using=kwargs.get('using'))):
            # it already exists, so do a move
            old_parent_id = self._mptt_cached_fields['parent']
            if old_parent_id is DeferredAttribute:
                same_order = True
            else:
                same_order = old_parent_id == parent_id

            if same_order and len(self._mptt_cached_fields) > 1:
                for field_name, old_value in self._mptt_cached_fields.items():
                    if old_value is DeferredAttribute and field_name not in deferred_fields:
                        same_order = False
                        break
                    if old_value != opts.get_raw_field_value(self, field_name):
                        same_order = False
                        break
            if not same_order:
                opts.set_raw_field_value(self, 'parent', old_parent_id)
                try:
                    if parent_id is not None:
                        parent = self.parent
                        # If we aren't already a descendant of the new parent,
                        # we need to update the parent.rght so things like
                        # get_children and get_descendant_count work correctly.
                        #
                        # parent might be None if parent_id was assigned
                        # directly -- then we certainly do not have to update
                        # the cached parent.
                        update_cached_parent = parent and (
                            self.tree_id != parent.tree_id or
                            self.lft < parent.lft or
                            self.rght > parent.rght)

                    if opts.order_insertion_by:
                        right_sibling = opts.get_ordered_insertion_target(
                            self, self.parent)

                        # Default position is last.
                        position = 'last-child'
                        target = None if parent_id is None else parent

                        if right_sibling:
                            position = 'left'
                            target = right_sibling

                        if right_sibling is None and self.is_root_node() and not parent_id:
                            # Our tree should be the last of all.
                            position = 'right'

                        self._tree_manager._move_node(
                            self,
                            target,
                            position,
                            save=False,
                            refresh_target=False)

                    else:
                        # Default movement
                        if parent_id is None:
                            self._tree_manager._move_node(
                                self, None, 'right', save=False,
                                refresh_target=False)
                        else:
                            self._tree_manager._move_node(
                                self, parent, 'last-child', save=False)

                    if parent_id is not None and update_cached_parent:
                        parent._mptt_refresh()
                finally:
                    # Make sure the new parent is always
                    # restored on the way out in case of errors.
                    opts.set_raw_field_value(self, 'parent', parent_id)

                # If there were no exceptions raised then send a moved signal
                node_moved.send(sender=self.__class__, instance=self,
                                target=self.parent)

            # populate update_fields with user defined model fields.
            # This helps preserve tree integrity when saving model on top
            # of a modified tree.
            if not kwargs.get("update_fields", None):
                kwargs["update_fields"] = self._get_user_field_names()

        else:
            # new node, do an insert
            if self.lft and self.rght:
                # This node has already been set up for insertion.
                pass
            else:
                parent = self.parent

                right_sibling = None
                if opts.order_insertion_by:
                    right_sibling = opts.get_ordered_insertion_target(self, parent)

                if right_sibling:
                    self.insert_at(right_sibling, 'left', allow_existing_pk=True,
                                   refresh_target=False)

                    if parent:
                        # since we didn't insert into parent, we have to update parent.rght
                        # here instead of in TreeManager.insert_node()
                        parent._mptt_refresh()
                else:
                    # Default insertion
                    self.insert_at(parent, position='last-child', allow_existing_pk=True)

        super(MPTTModel, self).save(**kwargs)

        self._mptt_saved = True
        self._mptt_refresh()
        opts.update_mptt_cached_fields(self)
    save.alters_data = True

    def delete(self, *args, **kwargs):
        """Calling ``delete`` on a node will delete it as well as its full
        subtree, as opposed to reattaching all the subnodes to its parent node.

        There are no argument specific to a MPTT model, all the arguments will
        be passed directly to the django's ``Model.delete``.

        ``delete`` will not return anything. """

        # Reduce all lft and rght values to the right by this node's width:
        self._mptt_refresh()
        self._tree_manager._manage_space(
            -(self.rght - self.lft + 1),
            self.rght,
            self.tree_id,
        )

        parent = getattr(self, '_parent_cache', None)
        if parent:
            parent._mptt_refresh()

        super(MPTTModel, self).delete(*args, **kwargs)

        if self.is_root_node():
            # Close gap.
            self._tree_manager._create_tree_space(
                self.tree_id,
                -1,
            )
    delete.alters_data = True

    def _mptt_refresh(self):
        """Reload MPTT bookkeeping attributes (tree_id, lft, rght and level)
        from the database."""

        try:
            self.refresh_from_db(fields=('tree_id', 'lft', 'rght', 'level'))
        except self.DoesNotExist:
            # Already deleted. Ignore.
            pass
