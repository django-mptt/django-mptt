"""
Functions dealing with Modified Preorder Tree Traversal related setup
and creation of instance methods for a model, given the names of its
tree attributes.

``treeify`` should be the only function a user of this application need
use directly to set their model up for Modified Preorder Tree Traversal.
"""
from django.db import models
from django.db.models import signals
from django.dispatch import dispatcher

from mptt.signals import pre_delete, pre_save
from mptt.managers import TreeManager

__all__ = ['treeify']

def treeify(cls, parent_attr='parent', left_attr='lft', right_attr='rght',
            tree_id_attr='tree_id', level_attr='level',
            tree_manager_attr='tree'):
    """
    Sets the given model class up for Modified Preorder Tree Traversal,
    which involves:

    1. Adding tree options to the ``Options`` for the model class, which
       are stored in ``_meta``.
    2. If any of the specified tree fields -- ``left_attr``,
       ``right_attr``, ``tree_id_attr`` and ``level_attr`` -- do not
       exist, adding them to the model class dynamically.
    3. Adding tree related instance methods to the model class.
    4. Adding a custom tree ``Manager`` to the model class.
    5. Registering ``pre_save`` and ``pre_delete`` signal receiving
       functions to manage tree field contents.
    """
    opts = cls._meta
    setattr(opts, 'parent_attr', parent_attr)
    setattr(opts, 'right_attr', right_attr)
    setattr(opts, 'left_attr', left_attr)
    setattr(opts, 'tree_id_attr', tree_id_attr)
    setattr(opts, 'level_attr', level_attr)
    setattr(opts, 'tree_manager_attr', tree_manager_attr)

    # Add tree fields if they do not exist
    for attr in [left_attr, right_attr, tree_id_attr, level_attr]:
        try:
            opts.get_field(attr)
        except models.FieldDoesNotExist:
            models.PositiveIntegerField(
                db_index=True, editable=False).contribute_to_class(cls, attr)

    setattr(cls, 'get_ancestors', get_ancestors)
    setattr(cls, 'get_children', get_children)
    setattr(cls, 'get_descendants', get_descendants)
    setattr(cls, 'get_descendant_count', get_descendant_count)
    setattr(cls, 'get_next_sibling', get_next_sibling)
    setattr(cls, 'get_previous_sibling', get_previous_sibling)
    setattr(cls, 'get_root', get_root)
    setattr(cls, 'get_siblings', get_siblings)
    setattr(cls, 'is_child_node', is_child_node)
    setattr(cls, 'is_leaf_node', is_leaf_node)
    setattr(cls, 'is_root_node', is_root_node)
    setattr(cls, 'move_to', move_to)

    TreeManager(parent_attr, left_attr, right_attr, tree_id_attr,
                level_attr).contribute_to_class(cls, tree_manager_attr)
    setattr(cls, '_tree_manager', getattr(cls, tree_manager_attr))

    dispatcher.connect(pre_save, signal=signals.pre_save, sender=cls)
    dispatcher.connect(pre_delete, signal=signals.pre_delete, sender=cls)

def get_ancestors(self, ascending=False):
    """
    Creates a ``QuerySet`` containing the ancestors of this model
    instance.

    This defaults to being in descending order (root ancestor first,
    immediate parent last); passing ``True`` for the ``ascending``
    argument will reverse the ordering (immediate parent first, root
    ancestor last).
    """
    if self.is_root_node():
        return self._tree_manager.none()

    opts = self._meta
    return self._default_manager.filter(**{
        '%s__lt' % opts.left_attr: getattr(self, opts.left_attr),
        '%s__gt' % opts.right_attr: getattr(self, opts.right_attr),
        opts.tree_id_attr: getattr(self, opts.tree_id_attr),
    }).order_by('%s%s' % ({True: '-', False: ''}[ascending], opts.left_attr))

def get_children(self):
    """
    Creates a ``QuerySet`` containing the immediate children of this
    model instance, in tree order.

    The benefit of using this method over the reverse relation
    provided by the ORM to the instance's children is that a
    database query can be avoided in the case where the instance is
    a leaf node (it has no children).
    """
    if self.is_leaf_node():
        return self._tree_manager.none()

    return self._tree_manager.filter(**{
        self._meta.parent_attr: self,
    })

def get_descendants(self, include_self=False):
    """
    Creates a ``QuerySet`` containing descendants of this model
    instance, in tree order.

    If ``include_self`` is ``True``, the ``QuerySet`` will also
    include this model instance.
    """
    if not include_self and self.is_leaf_node():
        return self._tree_manager.none()

    opts = self._meta
    filters = {opts.tree_id_attr: getattr(self, opts.tree_id_attr)}
    if include_self:
        filters['%s__range' % opts.left_attr] = (getattr(self, opts.left_attr),
                                                 getattr(self, opts.right_attr))
    else:
        filters['%s__gt' % opts.left_attr] = getattr(self, opts.left_attr)
        filters['%s__lt' % opts.left_attr] = getattr(self, opts.right_attr)
    return self._tree_manager.filter(**filters)

def get_descendant_count(self):
    """
    Returns the number of descendants this model instance has.
    """
    return (getattr(self, self._meta.right_attr) -
            getattr(self, self._meta.left_attr) - 1) / 2

def get_next_sibling(self):
    """
    Returns this model instance's next sibling in the tree, or
    ``None`` if it doesn't have a next sibling.
    """
    opts = self._meta
    if self.is_root_node():
        filters = {
            '%s__isnull' % opts.parent_attr: True,
            '%s__gt' % opts.tree_id_attr: getattr(self, opts.tree_id_attr),
        }
    else:
        filters = {
             opts.parent_attr: getattr(self, '%s_id' % opts.parent_attr),
            '%s__gt' % opts.left_attr: getattr(self, opts.right_attr),
        }

    sibling = None
    try:
        sibling = self._tree_manager.filter(**filters)[0]
    except IndexError:
        pass
    return sibling

def get_previous_sibling(self):
    """
    Returns this model instance's previous sibling in the tree, or
    ``None`` if it doesn't have a previous sibling.
    """
    opts = self._meta
    if self.is_root_node():
        filters = {
            '%s__isnull' % opts.parent_attr: True,
            '%s__lt' % opts.tree_id_attr: getattr(self, opts.tree_id_attr),
        }
        order_by = '-%s' % opts.tree_id_attr
    else:
        filters = {
             opts.parent_attr: getattr(self, '%s_id' % opts.parent_attr),
            '%s__lt' % opts.right_attr: getattr(self, opts.left_attr),
        }
        order_by = '-%s' % opts.right_attr

    sibling = None
    try:
        sibling = self._tree_manager.filter(**filters).order_by(order_by)[0]
    except IndexError:
        pass
    return sibling

def get_root(self):
    """
    Returns the root node of this model instance's tree.
    """
    if self.is_root_node():
        return self

    opts = self._meta
    return self._default_manager.filter(**{
        opts.tree_id_attr: getattr(self, opts.tree_id_attr),
        '%s__isnull' % opts.parent_attr: True,
    })[0]

def get_siblings(self, include_self=False):
    """
    Creates a ``QuerySet`` containing siblings of this model
    instance. Root nodes are considered to be siblings of other root
    nodes.

    If ``include_self`` is ``True``, the ``QuerySet`` will also
    include this model instance.
    """
    opts = self._meta
    if self.is_root_node():
        filters = {'%s__isnull' % opts.parent_attr: True}
    else:
        filters = {opts.parent_attr: getattr(self, '%s_id' % opts.parent_attr)}
    queryset = self._tree_manager.filter(**filters)
    if not include_self:
        queryset = queryset.exclude(pk=self.pk)
    return queryset

def is_child_node(self):
    """
    Returns ``True`` if this model instance is a child node, ``False``
    otherwise.
    """
    return not self.is_root_node()

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
    return getattr(self, '%s_id' % self._meta.parent_attr) is None

def move_to(self, target, position='first-child'):
    """
    Convenience method for calling ``TreeManager.move_to`` with this
    model instance.
    """
    self._tree_manager.move_node(self, target, position)
