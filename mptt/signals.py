"""
Functions which create signal receiving functions dealing with Modified
Preorder Tree Traversal related logic for a model, given the names of
its tree attributes.
"""
from django.db import connection
from django.utils.translation import ugettext as _

from mptt.exceptions import InvalidParent

__all__ = ['pre_save', 'pre_delete']

qn = connection.ops.quote_name

def _get_next_tree_id(model, tree_id_attr):
    """
    Determines the next tree id for the given model or model instance.
    """
    cursor = connection.cursor()
    cursor.execute('SELECT MAX(%s) FROM %s' % (
        qn(model._meta.get_field(tree_id_attr).column),
        qn(model._meta.db_table)))
    row = cursor.fetchone()
    return row[0] and (row[0] + 1) or 1

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
        opts = instance._meta
        parent = getattr(instance, parent_attr)
        if not instance.pk:
            cursor = connection.cursor()
            db_table = qn(opts.db_table)
            if parent:
                target_right = getattr(parent, right_attr) - 1
                tree_id = getattr(parent, tree_id_attr)
                update_query = 'UPDATE %s SET %%(col)s = %%(col)s + 2 WHERE %%(col)s > %%%%s AND %s = %%%%s' % (
                    qn(opts.db_table),
                    qn(opts.get_field(tree_id_attr).column))
                cursor.execute(update_query % {
                    'col': qn(opts.get_field(right_attr).column),
                }, [target_right, tree_id])
                cursor.execute(update_query % {
                    'col': qn(opts.get_field(left_attr).column),
                }, [target_right, tree_id])
                setattr(instance, left_attr, target_right + 1)
                setattr(instance, right_attr, target_right + 2)
                setattr(instance, tree_id_attr, tree_id)
                setattr(instance, level_attr, getattr(parent, level_attr) + 1)
            else:
                setattr(instance, left_attr, 1)
                setattr(instance, right_attr, 2)
                setattr(instance, tree_id_attr,
                        _get_next_tree_id(instance, tree_id_attr))
                setattr(instance, level_attr, 0)
        else:
            # TODO Is it possible to track the original parent so we
            #      don't have to look it up again on each save after the
            #      first?
            old_parent = getattr(instance._default_manager.get(pk=instance.pk),
                                 parent_attr)
            if parent != old_parent:
                cursor = connection.cursor()
                db_table = qn(opts.db_table)
                if parent is None:
                    # Move this node and its descendants, making the
                    # node a new root node.
                    move_subtree_query = """
                    UPDATE %(table)s
                    SET %(level)s = %(level)s - %%s,
                        %(left)s = %(left)s - %%s,
                        %(right)s = %(right)s - %%s,
                        %(tree_id)s = %%s
                    WHERE %(left)s >= %%s AND %(left)s <= %%s
                      AND %(tree_id)s = %%s""" % {
                        'table': db_table,
                        'level': qn(opts.get_field(level_attr).column),
                        'left': qn(opts.get_field(left_attr).column),
                        'right': qn(opts.get_field(right_attr).column),
                        'tree_id': qn(opts.get_field(tree_id_attr).column),
                    }
                    tree_id = getattr(instance, tree_id_attr)
                    new_tree_id = _get_next_tree_id(instance, tree_id_attr)
                    edge_change = getattr(instance, left_attr) - 1
                    cursor.execute(move_subtree_query, [
                        getattr(instance, level_attr),
                        edge_change, edge_change, new_tree_id,
                        getattr(instance, left_attr),
                        getattr(instance, right_attr),
                        tree_id])

                    # Plug the gap left by moving the subtree.
                    plug_gap_query = """
                    UPDATE %(table)s
                    SET %%(col)s = %%(col)s - %%%%s
                    WHERE %%(col)s > %%%%s
                      AND %(tree_id)s = %%%%s""" % {
                        'table': db_table,
                        'tree_id': qn(opts.get_field(tree_id_attr).column),
                    }
                    gap_size = (getattr(instance, right_attr) -
                                getattr(instance, left_attr) + 1)
                    cursor.execute(plug_gap_query % {
                        'col': qn(opts.get_field(left_attr).column),
                    }, [gap_size, getattr(instance, left_attr), tree_id])
                    cursor.execute(plug_gap_query % {
                        'col': qn(opts.get_field(right_attr).column),
                    }, [gap_size, getattr(instance, right_attr), tree_id])

                    # The model instance is yet to be saved, so make sure its
                    # new tree values are present.
                    setattr(instance, left_attr,
                            getattr(instance, left_attr) - edge_change)
                    setattr(instance, right_attr,
                            getattr(instance, right_attr) - edge_change)
                    setattr(instance, level_attr, 0)
                    setattr(instance, tree_id_attr, new_tree_id)
                elif old_parent is None:
                    # Check the validity of the new parent
                    if (getattr(parent, tree_id_attr) ==
                        getattr(instance, tree_id_attr)):
                        raise InvalidParent(_('A root node may not have its parent changed to any node in its own tree.'))

                    # Make space for the tree which will be moved
                    target_right = getattr(parent, right_attr) - 1
                    new_tree_id = getattr(parent, tree_id_attr)
                    tree_width = (getattr(instance, right_attr) -
                                  getattr(instance, left_attr) + 1)
                    update_query = 'UPDATE %s SET %%(col)s = %%(col)s + %%%%s WHERE %%(col)s > %%%%s AND %s = %%%%s' % (
                        qn(opts.db_table),
                        qn(opts.get_field(tree_id_attr).column))
                    cursor.execute(update_query % {
                        'col': qn(opts.get_field(right_attr).column),
                    }, [tree_width, target_right, new_tree_id])
                    cursor.execute(update_query % {
                        'col': qn(opts.get_field(left_attr).column),
                    }, [tree_width, target_right, new_tree_id])

                    # Move the tree's root node and its descendants,
                    # making the root node a child node.
                    move_tree_query = """
                    UPDATE %(table)s
                    SET %(level)s = %(level)s + %%s,
                        %(left)s = %(left)s + %%s,
                        %(right)s = %(right)s + %%s,
                        %(tree_id)s = %%s
                    WHERE %(tree_id)s = %%s""" % {
                        'table': db_table,
                        'level': qn(opts.get_field(level_attr).column),
                        'left': qn(opts.get_field(left_attr).column),
                        'right': qn(opts.get_field(right_attr).column),
                        'tree_id': qn(opts.get_field(tree_id_attr).column),
                    }
                    tree_id = getattr(instance, tree_id_attr)
                    level_change = getattr(parent, level_attr) + 1
                    cursor.execute(move_tree_query, [level_change, target_right,
                        target_right, new_tree_id, tree_id])

                    # The model instance is yet to be saved, so make sure its
                    # new tree values are present.
                    setattr(instance, left_attr,
                            getattr(instance, left_attr) + target_right)
                    setattr(instance, right_attr,
                            getattr(instance, right_attr) + target_right)
                    setattr(instance, level_attr,
                            getattr(instance, level_attr) + level_change)
                    setattr(instance, tree_id_attr, new_tree_id)
                elif (getattr(parent, tree_id_attr) !=
                      getattr(instance, tree_id_attr)):
                    # Make space for the subtree which will be moved
                    target_right = getattr(parent, right_attr) - 1
                    new_tree_id = getattr(parent, tree_id_attr)
                    tree_width = (getattr(instance, right_attr) -
                                  getattr(instance, left_attr) + 1)
                    update_query = 'UPDATE %s SET %%(col)s = %%(col)s + %%%%s WHERE %%(col)s > %%%%s AND %s = %%%%s' % (
                        qn(opts.db_table),
                        qn(opts.get_field(tree_id_attr).column))
                    cursor.execute(update_query % {
                        'col': qn(opts.get_field(right_attr).column),
                    }, [tree_width, target_right, new_tree_id])
                    cursor.execute(update_query % {
                        'col': qn(opts.get_field(left_attr).column),
                    }, [tree_width, target_right, new_tree_id])

                    # Move the subtree
                    move_subtree_query = """
                    UPDATE %(table)s
                    SET %(level)s = %(level)s - %%s,
                        %(left)s = %(left)s - %%s,
                        %(right)s = %(right)s - %%s,
                        %(tree_id)s = %%s
                    WHERE %(left)s >= %%s AND %(left)s <= %%s
                      AND %(tree_id)s = %%s""" % {
                        'table': db_table,
                        'level': qn(opts.get_field(level_attr).column),
                        'left': qn(opts.get_field(left_attr).column),
                        'right': qn(opts.get_field(right_attr).column),
                        'tree_id': qn(opts.get_field(tree_id_attr).column),
                    }
                    tree_id = getattr(instance, tree_id_attr)
                    level_change = (getattr(instance, level_attr) -
                                    getattr(parent, level_attr) - 1)
                    left_right_change = (getattr(instance, left_attr) -
                                         getattr(parent, right_attr))
                    cursor.execute(move_subtree_query, [level_change,
                        left_right_change, left_right_change, new_tree_id,
                        getattr(instance, left_attr),
                        getattr(instance, right_attr),
                        tree_id])

                    # Plug the gap left by moving the subtree.
                    plug_gap_query = """
                    UPDATE %(table)s
                    SET %%(col)s = %%(col)s - %%%%s
                    WHERE %%(col)s > %%%%s
                      AND %(tree_id)s = %%%%s""" % {
                        'table': db_table,
                        'tree_id': qn(opts.get_field(tree_id_attr).column),
                    }
                    cursor.execute(plug_gap_query % {
                        'col': qn(opts.get_field(left_attr).column),
                    }, [tree_width, getattr(instance, left_attr), tree_id])
                    cursor.execute(plug_gap_query % {
                        'col': qn(opts.get_field(right_attr).column),
                    }, [tree_width, getattr(instance, right_attr), tree_id])

                    # The model instance is yet to be saved, so make sure its
                    # new tree values are present.
                    setattr(instance, left_attr,
                            getattr(instance, left_attr) - left_right_change)
                    setattr(instance, right_attr,
                            getattr(instance, right_attr) - left_right_change)
                    setattr(instance, level_attr,
                            getattr(instance, level_attr) - level_change)
                    setattr(instance, tree_id_attr, new_tree_id)
                else:
                    # Check the validity of the new parent
                    if (getattr(instance, left_attr)
                        <= getattr(parent, left_attr)
                        <= getattr(instance, right_attr)):
                        raise InvalidParent(_('A node may not have its parent changed to itself or any of its descendants.'))

                    tree_id = getattr(instance, tree_id_attr)
                    node_left = getattr(instance, left_attr)
                    node_right = getattr(instance, right_attr)

                    if (getattr(parent, level_attr) !=
                        getattr(old_parent, level_attr)):
                        level_change_query = """
                        UPDATE %(table)s
                        SET %(level)s = %(level)s - %%s
                        WHERE %(left)s >= %%s AND %(left)s <= %%s
                          AND %(tree_id)s = %%s""" % {
                            'table': db_table,
                            'level': qn(opts.get_field(level_attr).column),
                            'left': qn(opts.get_field(left_attr).column),
                            'tree_id': qn(opts.get_field(tree_id_attr).column),
                        }
                        level_change = (getattr(instance, level_attr) -
                                        getattr(parent, level_attr) - 1)
                        cursor.execute(level_change_query, [level_change,
                            node_left, node_right, tree_id])

                    move_subtree_query = """
                    UPDATE %(table)s
                    SET %(left)s = CASE
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
                        ELSE %(right)s END
                    WHERE %(tree_id)s = %%s""" % {
                        'table': db_table,
                        'left': qn(opts.get_field(left_attr).column),
                        'right': qn(opts.get_field(right_attr).column),
                        'tree_id': qn(opts.get_field(tree_id_attr).column),
                    }

                    parent_right = getattr(parent, right_attr)
                    subtree_width = node_right - node_left + 1
                    new_left = parent_right - subtree_width
                    new_right = parent_right - 1
                    left_boundary = min(node_left, new_left)
                    right_boundary = max(node_right, new_right)
                    left_right_change = new_left - node_left
                    gap_size = subtree_width
                    if left_right_change > 0:
                        gap_size = -gap_size

                    cursor.execute(move_subtree_query, [
                        node_left, node_right, left_right_change,
                        left_boundary, right_boundary, gap_size,
                        node_left, node_right, left_right_change,
                        left_boundary, right_boundary, gap_size,
                        tree_id])

                    # The model instance is yet to be saved, so make sure its
                    # new tree values are present.
                    setattr(instance, left_attr, new_left)
                    setattr(instance, right_attr, new_right)
                    setattr(instance, level_attr,
                            getattr(instance, level_attr) - level_change)
    return _pre_save

def pre_delete(left_attr, right_attr, tree_id_attr):
    """
    Creates a pre-delete signal receiver for a model which has the given
    tree attributes.
    """
    def _pre_delete(instance):
        """
        Updates tree node edge indicators which will by affected by the
        deletion of the given model instance and any childrem it may
        have, to ensure the integrity of the tree structure is
        maintained.
        """
        span = getattr(instance, right_attr) - getattr(instance, left_attr) + 1
        update_query = 'UPDATE %s SET %%(col)s = %%(col)s - %%%%s WHERE %%(col)s > %%%%s AND %s = %%%%s' % (
            qn(instance._meta.db_table),
            qn(instance._meta.get_field(tree_id_attr).column))
        tree_id = getattr(instance, tree_id_attr)
        right = getattr(instance, right_attr)
        cursor = connection.cursor()
        cursor.execute(update_query % {
            'col': qn(instance._meta.get_field(right_attr).column),
        }, [span, right, tree_id])
        cursor.execute(update_query % {
            'col': qn(instance._meta.get_field(left_attr).column),
        }, [span, right, tree_id])
    return _pre_delete
