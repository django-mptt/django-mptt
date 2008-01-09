"""
Functions which create signal receiving functions dealing with Modified
Preorder Tree Traversal related logic for a model, given the names of
its tree attributes.
"""
from django.db import connection
from django.utils.translation import ugettext as _

__all__ = ['pre_save', 'pre_delete']

qn = connection.ops.quote_name

def pre_save(instance):
    """
    If this is a new instance, sets tree fields  before it is added
    to the database, updating other nodes' edge indicators to make
    room if neccessary.

    If this is an existing instance and its parent has been changed,
    performs reparenting.
    """
    opts = instance._meta
    parent = getattr(instance, opts.parent_attr)
    if not instance.pk:
        if parent:
            target_right = getattr(parent, opts.right_attr) - 1
            tree_id = getattr(parent, opts.tree_id_attr)
            instance._tree_manager._create_space(2, target_right, tree_id)
            setattr(instance, opts.left_attr, target_right + 1)
            setattr(instance, opts.right_attr, target_right + 2)
            setattr(instance, opts.tree_id_attr, tree_id)
            setattr(instance, opts.level_attr,
                    getattr(parent, opts.level_attr) + 1)
        else:
            setattr(instance, opts.left_attr, 1)
            setattr(instance, opts.right_attr, 2)
            setattr(instance, opts.tree_id_attr,
                    instance._tree_manager._get_next_tree_id())
            setattr(instance, opts.level_attr, 0)
    else:
        # TODO Is it possible to track the original parent so we
        #      don't have to look it up again on each save after the
        #      first?
        old_parent = getattr(instance._default_manager.get(pk=instance.pk),
                             opts.parent_attr)
        if parent != old_parent:
            setattr(instance, opts.parent_attr, old_parent)
            try:
                instance.move_to(parent, position='last-child')
            finally:
                # Make sure the instance's new parent is always
                # restored on the way out
                setattr(instance, opts.parent_attr, parent)

def pre_delete(instance):
    """
    Updates tree node edge indicators which will by affected by the
    deletion of the given model instance and any descendants it may
    have, to ensure the integrity of the tree structure is
    maintained.
    """
    opts = instance._meta
    tree_width = (getattr(instance, opts.right_attr) -
                  getattr(instance, opts.left_attr) + 1)
    target_right = getattr(instance, opts.right_attr)
    tree_id = getattr(instance, opts.tree_id_attr)
    instance._tree_manager._close_gap(tree_width, target_right, tree_id)
