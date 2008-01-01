"""
Custom managers for working with trees of objects.
"""
from django.db import connection, models

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
