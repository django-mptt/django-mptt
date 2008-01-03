"""
Custom managers for working with trees of objects.
"""
from django.db import connection, models
from django.utils.translation import ugettext as _

from mptt.exceptions import InvalidTarget

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

        The given ``root`` will be modified to reflect its new tree
        state in the database.
        """
        left = getattr(root, self.left_attr)
        right = getattr(root, self.right_attr)
        level = getattr(root, self.level_attr)
        tree_id = getattr(root, self.tree_id_attr)
        new_tree_id = getattr(parent, self.tree_id_attr)
        target_right = getattr(parent, self.right_attr) - 1
        tree_width = right - left + 1
        level_change = getattr(parent, self.level_attr) + 1

        # Ensure the new parent is valid
        if tree_id == new_tree_id:
            raise InvalidTarget(_('A root node may not have its parent changed to any node in its own tree.'))

        # Create space for the tree which will be inserted
        self.create_space(tree_width, target_right, new_tree_id)

        # Move the root node and its descendants, making the root node a
        # child node.
        opts = self.model._meta
        move_tree_query = """
        UPDATE %(table)s
        SET %(level)s = %(level)s + %%s,
            %(left)s = %(left)s + %%s,
            %(right)s = %(right)s + %%s,
            %(tree_id)s = %%s,
            %(parent)s = CASE
                WHEN %(pk)s = %%s
                    THEN %%s
                ELSE %(parent)s END
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
        cursor = connection.cursor()
        cursor.execute(move_tree_query, [level_change, target_right,
            target_right, new_tree_id, root.pk, parent.pk, left, right,
            tree_id])

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

        The given ``instance`` will be modified to reflect its new tree
        state in the database.
        """
        left = getattr(instance, self.left_attr)
        right = getattr(instance, self.right_attr)
        level = getattr(instance, self.level_attr)
        tree_id = getattr(instance, self.tree_id_attr)
        new_tree_id = self.get_next_tree_id()
        left_right_change = left - 1
        gap_target_left = left - 1
        gap_size = right - left + 1

        self._inter_tree_move_and_close_gap(instance, level,
            left_right_change, new_tree_id, gap_target_left, gap_size)

        # Update the instance to be consistent with the updated
        # tree in the database.
        setattr(instance, self.left_attr, left - left_right_change)
        setattr(instance, self.right_attr, right - left_right_change)
        setattr(instance, self.level_attr, 0)
        setattr(instance, self.tree_id_attr, new_tree_id)
        setattr(instance, self.parent_attr, None)

    def move_node(self, instance, new_parent):
        """
        Moves a ``Model`` instance to a new parent, taking care of
        calling the appropriate manager method to do so.

        To remove the instance's parent, pass ``None`` for the
        ``new_parent`` argument.

        The given ``instance`` will be modified to reflect its new tree
        state in the database.
        """
        if new_parent is None:
            self.make_root_node(instance)
        else:
            parent = getattr(instance, self.parent_attr)
            if parent is None:
                self.make_child_node(instance, new_parent)
            elif (getattr(new_parent, self.tree_id_attr) !=
                  getattr(instance, self.tree_id_attr)):
                self.move_to_new_tree(instance, new_parent)
            else:
                self.move_within_tree(instance, new_parent)

    def move_to_new_tree(self, instance, parent):
        """
        Moves a ``Model`` instance from one tree to another, making it a
        child of the given ``parent`` node, which is in a different tree.

        The given ``instance`` will be modified to reflect its new tree state
        in the database.
        """
        left = getattr(instance, self.left_attr)
        right = getattr(instance, self.right_attr)
        level = getattr(instance, self.level_attr)
        tree_id = getattr(instance, self.tree_id_attr)
        new_tree_id = getattr(parent, self.tree_id_attr)

        # Make space for the subtree which will be moved
        tree_width = right - left + 1
        target_right = getattr(parent, self.right_attr) - 1
        self.create_space(tree_width, target_right, new_tree_id)

        # Move the subtree
        level_change = level - getattr(parent, self.level_attr) - 1
        left_right_change = left - getattr(parent, self.right_attr)
        gap_target_left = left - 1
        self._inter_tree_move_and_close_gap(instance, level_change,
            left_right_change, new_tree_id, gap_target_left, tree_width,
            parent.pk)

        # Update the instance to be consistent with the updated
        # tree in the database.
        setattr(instance, self.left_attr, left - left_right_change)
        setattr(instance, self.right_attr, right - left_right_change)
        setattr(instance, self.level_attr, level - level_change)
        setattr(instance, self.tree_id_attr, new_tree_id)
        setattr(instance, self.parent_attr, parent)

    def move_within_tree(self, node, target, position='last-child'):
        """
        Moves ``node`` within its current tree, relative to the given
        ``target`` node as specified by ``position``.

        Valid values for ``position`` are ``'first-child'``,
        ``'last-child'``, ``'left'`` or ``'right'``.

        The node being moved will be modified to reflect its new tree
        state in the database.
        """
        left = getattr(node, self.left_attr)
        right = getattr(node, self.right_attr)
        level = getattr(node, self.level_attr)
        subtree_width = right - left + 1
        tree_id = getattr(node, self.tree_id_attr)
        target_left = getattr(target, self.left_attr)
        target_right = getattr(target, self.right_attr)
        target_level = getattr(target, self.level_attr)

        if position == 'last-child' or position == 'first-child':
            if left <= target_left <= right:
                raise InvalidTarget(_('A node may not be made a child of itself or any of its descendants.'))
            if position == 'last-child':
                if target_right > right:
                    new_left = target_right - subtree_width
                    new_right = target_right - 1
                else:
                    new_left = target_right
                    new_right = target_right + subtree_width - 1
            else:
                if target_left > left:
                    new_left = target_left - subtree_width + 1
                    new_right = target_left
                else:
                    new_left = target_left + 1
                    new_right = target_left + subtree_width
            level_change = level - target_level - 1
            parent = target
        elif position == 'left' or position == 'right':
            if left <= target_left <= right:
                raise InvalidTarget(_('A node may not be made a sibling of itself or any of its descendants.'))
            if target_left == 1:
                raise InvalidTarget(_('A node may not be made a sibling of its root node.'))
            if position == 'left':
                if target_left > left:
                    new_left = target_left - subtree_width
                    new_right = target_left - 1
                else:
                    new_left = target_left
                    new_right = target_left + subtree_width - 1
            else:
                if target_right > right:
                    new_left = target_right - subtree_width + 1
                    new_right = target_right
                else:
                    new_left = target_right + 1
                    new_right = target_right + subtree_width
            level_change = level - target_level
            parent = getattr(target, self.parent_attr)

        left_boundary = min(left, new_left)
        right_boundary = max(right, new_right)
        left_right_change = new_left - left
        gap_size = subtree_width
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
            'table': qn(opts.db_table),
            'level': qn(opts.get_field(self.level_attr).column),
            'left': qn(opts.get_field(self.left_attr).column),
            'right': qn(opts.get_field(self.right_attr).column),
            'parent': qn(opts.get_field(self.parent_attr).column),
            'pk': qn(opts.pk.column),
            'tree_id': qn(opts.get_field(self.tree_id_attr).column),
        }

        cursor = connection.cursor()
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

    def _inter_tree_move_and_close_gap(self, node, level_change,
            left_right_change, new_tree_id, gap_target_left, gap_size,
            parent_pk=None):
        """
        Handles moving a subtree which is headed by ``node`` from its
        current tree to another tree, with the given set of changes
        being applied to ``node`` and its descendants, closing the gap
        left by moving the tree as it does so.

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
            'table': qn(opts.db_table),
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
        cursor = connection.cursor()
        cursor.execute(inter_tree_move_query, params)

    def _manage_space(self, size, target, tree_id, operator):
        """
        Manages spaces in a tree by changing the values of the left and
        right columns after a given target point.
        """
        opts = self.model._meta
        space_query = """
        UPDATE %(table)s
        SET %(left)s = CASE
                WHEN %(left)s > %%s
                    THEN %(left)s %(operator)s %%s
                ELSE %(left)s END,
            %(right)s = CASE
                WHEN %(right)s > %%s
                    THEN %(right)s %(operator)s %%s
                ELSE %(right)s END
        WHERE %(tree_id)s = %%s
          AND (%(left)s > %%s OR %(right)s > %%s)""" % {
            'table': qn(opts.db_table),
            'left': qn(opts.get_field(self.left_attr).column),
            'right': qn(opts.get_field(self.right_attr).column),
            'operator': operator,
            'tree_id': qn(opts.get_field(self.tree_id_attr).column),
        }
        cursor = connection.cursor()
        cursor.execute(space_query, [target, size, target, size, tree_id,
                                     target, target])
