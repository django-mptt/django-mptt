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

    1. If any of the specified tree fields -- ``left_attr``,
       ``right_attr``, ``tree_id_attr`` and ``level_attr`` -- do not
       exist, adding them to the model class dynamically.
    2. Creating pre_save and pre_delete signal receiving functions to
       manage tree field contents.
    3. Adding tree related instance methods to the model class.
    4. Adding a custom tree ``Manager`` to the model class.
    """
    # Add tree fields if they do not exist
    for attr in [left_attr, right_attr, tree_id_attr, level_attr]:
        try:
            cls._meta.get_field(attr)
        except models.FieldDoesNotExist:
            models.PositiveIntegerField(
                db_index=True, editable=False).contribute_to_class(cls, attr)
    # Specifying weak=False is required in this case as the dispatcher
    # will be the only place a reference is held to the signal receiving
    # functions we're creating.
    dispatcher.connect(
        pre_save(parent_attr, left_attr, right_attr, tree_id_attr, level_attr),
        signal=signals.pre_save, sender=cls, weak=False)
    dispatcher.connect(pre_delete(left_attr, right_attr, tree_id_attr),
                       signal=signals.pre_delete, sender=cls, weak=False)
    setattr(cls, 'get_ancestors',
            get_ancestors(parent_attr, left_attr, right_attr, tree_id_attr))
    setattr(cls, 'get_descendants',
            get_descendants(left_attr, right_attr, tree_id_attr))
    setattr(cls, 'get_descendant_count',
            get_descendant_count(left_attr, right_attr))
    setattr(cls, 'get_next_sibling',
            get_next_sibling(parent_attr, left_attr, right_attr, tree_id_attr))
    setattr(cls, 'get_previous_sibling',
            get_previous_sibling(parent_attr, left_attr, right_attr,
                                 tree_id_attr))
    setattr(cls, 'get_siblings',
            get_siblings(parent_attr, left_attr, tree_id_attr))
    setattr(cls, 'is_child_node', is_child_node)
    setattr(cls, 'is_root_node', is_root_node(parent_attr))
    setattr(cls, 'move_to', move_to)
    if not hasattr(cls, tree_manager_attr):
        TreeManager(parent_attr, left_attr, right_attr, tree_id_attr,
                    level_attr).contribute_to_class(cls, tree_manager_attr)
    setattr(cls, '_tree_manager', getattr(cls, tree_manager_attr))

def get_ancestors(parent_attr, left_attr, right_attr, tree_id_attr):
    """
    Creates a function which retrieves the ancestors of a model instance
    which has the given tree attributes.
    """
    def _get_ancestors(instance, ascending=False):
        """
        Creates a ``QuerySet`` containing all the ancestors of this
        model instance.

        This defaults to being in descending order (root ancestor first,
        immediate parent last); passing ``True`` for the ``ascending``
        argument will reverse the ordering (immediate parent first, root
        ancestor last).
        """
        if getattr(instance, parent_attr) is None:
            return instance._default_manager.none()
        else:
            return instance._default_manager.filter(**{
                '%s__lt' % left_attr: getattr(instance, left_attr),
                '%s__gt' % right_attr: getattr(instance, right_attr),
                tree_id_attr: getattr(instance, tree_id_attr),
            }).order_by('%s%s' % ({True: '-', False: ''}[ascending], left_attr))
    return _get_ancestors

def get_descendants(left_attr, right_attr, tree_id_attr):
    """
    Creates a function which retrieves descendants of a model
    instance which has the given tree attributes.
    """
    def _get_descendants(instance, include_self=False):
        """
        Creates a ``QuerySet`` containing descendants of this model
        instance.

        If ``include_self`` is ``True``, the ``QuerySet`` will also
        include this model instance.
        """
        filters = {tree_id_attr: getattr(instance, tree_id_attr)}
        if include_self:
            filters['%s__range' % left_attr] = (getattr(instance, left_attr),
                                                getattr(instance, right_attr))
        else:
            filters['%s__gt' % left_attr] = getattr(instance, left_attr)
            filters['%s__lt' % left_attr] = getattr(instance, right_attr)
        return instance._default_manager.filter(**filters).order_by(left_attr)
    return _get_descendants

def get_descendant_count(left_attr, right_attr):
    """
    Creates a function which determines the number of descendants of a
    model instance which has the given tree attributes.
    """
    def _get_descendant_count(instance):
        """
        Returns the number of descendants this model instance has.
        """
        return (getattr(instance, right_attr) - getattr(instance, left_attr) - 1) / 2
    return _get_descendant_count

def get_previous_sibling(parent_attr, left_attr, right_attr, tree_id_attr):
    """
    Creates a function which retrieves the previous sibling of a model
    instance which has the given tree attributes.
    """
    def _get_previous_sibling(instance):
        """
        Returns this model instance's previous sibling in the tree, or
        ``None`` if it doesn't have a previous sibling.
        """
        if instance.is_root_node():
            filters = {
                '%s__isnull' % parent_attr: True,
                '%s__lt' % tree_id_attr: getattr(instance, tree_id_attr),
            }
            order_by = '-%s' % tree_id_attr
        else:
            filters = {
                 parent_attr: getattr(instance, '%s_id' % parent_attr),
                '%s__lt' % right_attr: getattr(instance, left_attr),
            }
            order_by = '-%s' % right_attr

        sibling = None
        try:
            sibling = instance._default_manager.filter(**filters).order_by(order_by)[0]
        except IndexError:
            pass
        return sibling
    return _get_previous_sibling

def get_next_sibling(parent_attr, left_attr, right_attr, tree_id_attr):
    """
    Creates a function which retrieves the next sibling of a model
    instance which has the given tree attributes.
    """
    def _get_next_sibling(instance):
        """
        Returns this model instance's next sibling in the tree, or
        ``None`` if it doesn't have a next sibling.
        """
        if instance.is_root_node():
            filters = {
                '%s__isnull' % parent_attr: True,
                '%s__gt' % tree_id_attr: getattr(instance, tree_id_attr),
            }
            order_by = tree_id_attr
        else:
            filters = {
                 parent_attr: getattr(instance, '%s_id' % parent_attr),
                '%s__gt' % left_attr: getattr(instance, right_attr),
            }
            order_by = left_attr

        sibling = None
        try:
            sibling = instance._default_manager.filter(**filters).order_by(order_by)[0]
        except IndexError:
            pass
        return sibling
    return _get_next_sibling

def get_siblings(parent_attr, left_attr, tree_id_attr):
    """
    Creates a function which retrieves siblings of a model instance
    which has the given tree attributes.
    """
    def _get_siblings(instance, include_self=False):
        """
        Creates a ``QuerySet`` containing siblings of this model
        instance. Root nodes are considered to be siblings of other root
        nodes.

        If ``include_self`` is ``True``, the ``QuerySet`` will also
        include this model instance.
        """
        if instance.is_root_node():
            queryset = instance._default_manager.filter(**{
                '%s__isnull' % parent_attr: True,
            }).order_by(tree_id_attr)
        else:
            queryset = instance._default_manager.filter(**{
                parent_attr: getattr(instance, '%s_id' % parent_attr),
            }).order_by(left_attr)
        if not include_self:
            queryset = queryset.exclude(pk=instance.pk)
        return queryset
    return _get_siblings

def is_child_node(instance):
    """
    Returns ``True`` if this model instance is a child node, ``False``
    otherwise.
    """
    return not instance.is_root_node()

def is_root_node(parent_attr):
    """
    Creates a function which determines if a model instance which has
    the given tree attributes is a root node.
    """
    def _is_root_node(instance):
        """
        Returns ``True`` if this model instance is a root node,
        ``False`` otherwise.
        """
        return getattr(instance, '%s_id' % parent_attr) is None
    return _is_root_node

def move_to(instance, target, position='first-child'):
    """
    Convenience method for calling ``TreeManager.move_to`` with this
    model instance.
    """
    instance._tree_manager.move_node(instance, target, position)
