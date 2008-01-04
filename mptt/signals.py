"""
Functions which create signal receiving functions dealing with Modified
Preorder Tree Traversal related logic for a model, given the names of
its tree attributes.
"""
from django.db import connection
from django.utils.translation import ugettext as _

__all__ = ['pre_save', 'pre_delete']

qn = connection.ops.quote_name

def pre_save(parent_attr, left_attr, right_attr, tree_id_attr, level_attr):
    """
    Creates a pre-save signal receiver for a model which has the given
    tree attributes.
    """
    def _pre_save(instance):
        """
        If this is a new instance, sets tree fields  before it is added
        to the database, updating other nodes' edge indicators to make
        room if neccessary.

        If this is an existing instance and its parent has been changed,
        performs reparenting.
        """
        parent = getattr(instance, parent_attr)
        if not instance.pk:
            if parent:
                target_right = getattr(parent, right_attr) - 1
                tree_id = getattr(parent, tree_id_attr)
                instance._tree_manager._create_space(2, target_right, tree_id)
                setattr(instance, left_attr, target_right + 1)
                setattr(instance, right_attr, target_right + 2)
                setattr(instance, tree_id_attr, tree_id)
                setattr(instance, level_attr, getattr(parent, level_attr) + 1)
            else:
                setattr(instance, left_attr, 1)
                setattr(instance, right_attr, 2)
                setattr(instance, tree_id_attr,
                        instance._tree_manager._get_next_tree_id())
                setattr(instance, level_attr, 0)
        else:
            # TODO Is it possible to track the original parent so we
            #      don't have to look it up again on each save after the
            #      first?
            old_parent = getattr(instance._default_manager.get(pk=instance.pk),
                                 parent_attr)
            if parent != old_parent:
                setattr(instance, parent_attr, old_parent)
                instance.move_to(parent, position='last-child')
    return _pre_save

def pre_delete(left_attr, right_attr, tree_id_attr):
    """
    Creates a pre-delete signal receiver for a model which has the given
    tree attributes.
    """
    def _pre_delete(instance):
        """
        Updates tree node edge indicators which will by affected by the
        deletion of the given model instance and any descendants it may
        have, to ensure the integrity of the tree structure is
        maintained.
        """
        tree_width = (getattr(instance, right_attr) -
                      getattr(instance, left_attr) + 1)
        target_right = getattr(instance, right_attr)
        tree_id = getattr(instance, tree_id_attr)
        instance._tree_manager._close_gap(tree_width, target_right, tree_id)
    return _pre_delete
