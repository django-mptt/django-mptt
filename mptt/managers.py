"""
Custom managers for working with trees of objects.
"""
from django.db import connection, models
from django.utils.translation import ugettext as _

from mptt.exceptions import InvalidParent

__all__ = ['TreeManager']

qn = connection.ops.quote_name

class TreeManager(models.Manager):
    """
    A manager for working with trees of objects.
    """
    def __init__(self, parent_attr, left_attr, right_attr, tree_id_attr,
                 level_attr):
        """
        Tree related attributes for the model being managed are held as
        attributes of this manager for later use.
        """
        super(TreeManager, self).__init__()
        self.parent_attr = parent_attr
        self.left_attr = left_attr
        self.right_attr = right_attr
        self.tree_id_attr = tree_id_attr
        self.level_attr = level_attr

    def get_query_set(self):
        """
        Returns a ``QuerySet`` which contains all tree items, ordered in
        such a way that that trees appear in the order they were created
        and items appear in depth-first order within their tree.
        """
        return super(TreeManager, self).get_query_set().order_by(
            self.tree_id_attr, self.left_attr)

    def close_gap(self, size, target, tree_id):
        """
        Closes a gap of a certain size after the given target point in
        the tree with the given id.
        """
        self._manage_space(size, target, tree_id, '-')

    def create_space(self, size, target, tree_id):
        """
        Creates a space of a certain size after the given target point
        in the tree with the given id.
        """
        self._manage_space(size, target, tree_id, '+')

    def get_next_tree_id(self):
        """
        Determines the next available tree id for the tree managed by
        this manager.
        """
        opts = self.model._meta
        cursor = connection.cursor()
        cursor.execute('SELECT MAX(%s) FROM %s' % (
            qn(opts.get_field(self.tree_id_attr).column),
            qn(opts.db_table)))
        row = cursor.fetchone()
        return row[0] and (row[0] + 1) or 1

    def make_child_node(self, root, parent):
        """
        Transforms a ``Model`` instance which is the root node of a tree
        into a child of a given parent node in another tree.

        The given instance will be modified to reflect its new tree
        state in the database.
        """
        left = getattr(root, self.left_attr)
        right = getattr(root, self.right_attr)
        level = getattr(root, self.level_attr)
        tree_id = getattr(root, self.tree_id_attr)
        new_tree_id = getattr(parent, self.tree_id_attr)

        # Ensure the new parent is valid
        if tree_id == new_tree_id:
            raise InvalidParent(_('A root node may not have its parent changed to any node in its own tree.'))

        # Create space for the tree which will be inserted
        target_right = getattr(parent, self.right_attr) - 1
        tree_width = right - left + 1
        self.create_space(tree_width, target_right, new_tree_id)

        # Move the root node and its descendants, making the root node a
        # child node.
        opts = self.model._meta
        make_child_node_query = """
        UPDATE %(table)s
        SET %(level)s = %(level)s + %%s,
            %(left)s = %(left)s + %%s,
            %(right)s = %(right)s + %%s,
            %(tree_id)s = %%s,
            %(parent)s = CASE WHEN %(pk)s = %%s THEN %%s ELSE %(parent)s END
        WHERE %(tree_id)s = %%s""" % {
            'table': qn(opts.db_table),
            'level': qn(opts.get_field(self.level_attr).column),
            'left': qn(opts.get_field(self.left_attr).column),
            'right': qn(opts.get_field(self.right_attr).column),
            'tree_id': qn(opts.get_field(self.tree_id_attr).column),
            'parent': qn(opts.get_field(self.parent_attr).column),
            'pk': qn(opts.pk.column),
        }
        level_change = getattr(parent, self.level_attr) + 1
        cursor = connection.cursor()
        cursor.execute(make_child_node_query, [level_change, target_right,
            target_right, new_tree_id, root.pk, parent.pk, tree_id])

        # Update the former root node to be consistent with the updated
        # tree in the database.
        setattr(root, self.left_attr, left + target_right)
        setattr(root, self.right_attr, right + target_right)
        setattr(root, self.level_attr, level + level_change)
        setattr(root, self.tree_id_attr, new_tree_id)
        setattr(root, self.parent_attr, parent)

    def make_root_node(self, instance):
        """
        Transforms a ``Model`` instance which is a child node into the
        root node of a new tree, removing it and any descendants from
        the tree it currently occupies.

        The given instance will be modified to reflect its new tree
        state in the database.
        """
        left = getattr(instance, self.left_attr)
        right = getattr(instance, self.right_attr)
        level = getattr(instance, self.level_attr)
        tree_id = getattr(instance, self.tree_id_attr)

        opts = self.model._meta
        make_root_node_query = """
        UPDATE %(table)s
        SET %(level)s = %(level)s - %%s,
            %(left)s = %(left)s - %%s,
            %(right)s = %(right)s - %%s,
            %(tree_id)s = %%s,
            %(parent)s = CASE WHEN %(pk)s = %%s THEN NULL ELSE %(parent)s END
        WHERE %(left)s >= %%s AND %(left)s <= %%s
          AND %(tree_id)s = %%s""" % {
            'table': qn(opts.db_table),
            'level': qn(opts.get_field(self.level_attr).column),
            'left': qn(opts.get_field(self.left_attr).column),
            'right': qn(opts.get_field(self.right_attr).column),
            'tree_id': qn(opts.get_field(self.tree_id_attr).column),
            'parent': qn(opts.get_field(self.parent_attr).column),
            'pk': qn(opts.pk.column),
        }
        new_tree_id = self.get_next_tree_id()
        left_right_change = left - 1
        cursor = connection.cursor()
        cursor.execute(make_root_node_query, (level, left_right_change,
            left_right_change, new_tree_id, instance.pk, left, right, tree_id))

        # Close the gap left after the node was moved
        target_left = left - 1
        gap_size = right - left + 1
        instance._tree_manager.close_gap(gap_size, target_left,
                                         tree_id)

        # Update the instance to be consistent with the updated
        # tree in the database.
        setattr(instance, self.left_attr, left - left_right_change)
        setattr(instance, self.right_attr, right - left_right_change)
        setattr(instance, self.level_attr, 0)
        setattr(instance, self.tree_id_attr, new_tree_id)
        setattr(instance, self.parent_attr, None)

    def _manage_space(self, size, target, tree_id, operator):
        """
        Manages spaces in a tree by changing the values of the left and
        right columns after a given target point.
        """
        opts = self.model._meta
        space_query = """
        UPDATE %(table)s
        SET %%(col)s = %%(col)s %(operator)s %%%%s
        WHERE %%(col)s > %%%%s
          AND %(tree_id)s = %%%%s""" % {
            'table': qn(opts.db_table),
            'operator': operator,
            'tree_id': qn(opts.get_field(self.tree_id_attr).column),
        }
        cursor = connection.cursor()
        cursor.execute(space_query % {
            'col': qn(opts.get_field(self.right_attr).column),
        }, [size, target, tree_id])
        cursor.execute(space_query % {
            'col': qn(opts.get_field(self.left_attr).column),
        }, [size, target, tree_id])
