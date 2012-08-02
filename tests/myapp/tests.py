import re
import sys
import unittest

import django
from django.contrib import admin
from django.test import TestCase

try:
    import feincms
except ImportError:
    feincms = False

from mptt.exceptions import CantDisableUpdates, InvalidMove
from myapp.models import Category, Genre, CustomPKName, SingleProxyModel, DoubleProxyModel, ConcreteModel


def get_tree_details(nodes):
    """
    Creates pertinent tree details for the given list of nodes.
    The fields are:
        id  parent_id  tree_id  level  left  right
    """
    if hasattr(nodes, 'order_by'):
        nodes = list(nodes.order_by('tree_id', 'lft', 'pk'))
    nodes = list(nodes)
    opts = nodes[0]._mptt_meta
    return '\n'.join(['%s %s %s %s %s %s' %
                      (n.pk, getattr(n, '%s_id' % opts.parent_attr) or '-',
                       getattr(n, opts.tree_id_attr), getattr(n, opts.level_attr),
                       getattr(n, opts.left_attr), getattr(n, opts.right_attr))
                      for n in nodes])

leading_whitespace_re = re.compile(r'^\s+', re.MULTILINE)


def tree_details(text):
    """
    Trims leading whitespace from the given text specifying tree details
    so triple-quoted strings can be used to provide tree details in a
    readable format (says who?), to be compared with the result of using
    the ``get_tree_details`` function.
    """
    return leading_whitespace_re.sub('', text.rstrip())


class TreeTestCase(TestCase):
    def assertTreeEqual(self, tree1, tree2):
        if not isinstance(tree1, basestring):
            tree1 = get_tree_details(tree1)
        tree1 = tree_details(tree1)
        if not isinstance(tree2, basestring):
            tree2 = get_tree_details(tree2)
        tree2 = tree_details(tree2)
        return self.assertEqual(tree1, tree2, "\n%r\n != \n%r" % (tree1, tree2))

    if django.VERSION < (1, 3):
        # backport

        def assertNumQueries(self, num, func=None, *args, **kwargs):
            from django.db import connection

            class _AssertNumQueriesContext(object):
                def __init__(self, test_case, num, connection):
                    self.test_case = test_case
                    self.num = num
                    self.connection = connection

                def __enter__(self):
                    self.old_debug_cursor = self.connection.use_debug_cursor
                    self.connection.use_debug_cursor = True
                    self.starting_queries = len(self.connection.queries)
                    return self

                def __exit__(self, exc_type, exc_value, traceback):
                    self.connection.use_debug_cursor = self.old_debug_cursor
                    if exc_type is not None:
                        return

                    final_queries = len(self.connection.queries)
                    executed = final_queries - self.starting_queries

                    self.test_case.assertEqual(
                        executed, self.num, "%d queries executed, %d expected" % (
                            executed, self.num
                        )
                    )

            context = _AssertNumQueriesContext(self, num, connection)
            if func is None:
                return context

            with context:
                func(*args, **kwargs)


class DocTestTestCase(TreeTestCase):
    def test_run_doctest(self):
        class DummyStream:
            content = ""

            def write(self, text):
                self.content += text

        dummy_stream = DummyStream()
        before = sys.stdout
        sys.stdout = dummy_stream
        import doctest
        doctest.testfile('doctests.txt')
        sys.stdout = before
        content = dummy_stream.content
        if content:
            print >>sys.stderr, content
            self.fail()

# genres.json defines the following tree structure
#
# 1 - 1 0 1 16   action
# 2 1 1 1 2 9    +-- platformer
# 3 2 1 2 3 4    |   |-- platformer_2d
# 4 2 1 2 5 6    |   |-- platformer_3d
# 5 2 1 2 7 8    |   +-- platformer_4d
# 6 1 1 1 10 15  +-- shmup
# 7 6 1 2 11 12      |-- shmup_vertical
# 8 6 1 2 13 14      +-- shmup_horizontal
# 9 - 2 0 1 6    rpg
# 10 9 2 1 2 3   |-- arpg
# 11 9 2 1 4 5   +-- trpg


class ReparentingTestCase(TreeTestCase):
    """
    Test that trees are in the appropriate state after reparenting and
    that reparented items have the correct tree attributes defined,
    should they be required for use after a save.
    """
    fixtures = ['genres.json']

    def test_new_root_from_subtree(self):
        shmup = Genre.objects.get(id=6)
        shmup.parent = None
        shmup.save()
        self.assertTreeEqual([shmup], '6 - 3 0 1 6')
        self.assertTreeEqual(Genre.objects.all(), """
            1 - 1 0 1 10
            2 1 1 1 2 9
            3 2 1 2 3 4
            4 2 1 2 5 6
            5 2 1 2 7 8
            9 - 2 0 1 6
            10 9 2 1 2 3
            11 9 2 1 4 5
            6 - 3 0 1 6
            7 6 3 1 2 3
            8 6 3 1 4 5
        """)

    def test_new_root_from_leaf_with_siblings(self):
        platformer_2d = Genre.objects.get(id=3)
        platformer_2d.parent = None
        platformer_2d.save()
        self.assertTreeEqual([platformer_2d], '3 - 3 0 1 2')
        self.assertTreeEqual(Genre.objects.all(), """
            1 - 1 0 1 14
            2 1 1 1 2 7
            4 2 1 2 3 4
            5 2 1 2 5 6
            6 1 1 1 8 13
            7 6 1 2 9 10
            8 6 1 2 11 12
            9 - 2 0 1 6
            10 9 2 1 2 3
            11 9 2 1 4 5
            3 - 3 0 1 2
        """)

    def test_new_child_from_root(self):
        action = Genre.objects.get(id=1)
        rpg = Genre.objects.get(id=9)
        action.parent = rpg
        action.save()
        self.assertTreeEqual([action], '1 9 2 1 6 21')
        self.assertTreeEqual([rpg], '9 - 2 0 1 22')
        self.assertTreeEqual(Genre.objects.all(), """
            9 - 2 0 1 22
            10 9 2 1 2 3
            11 9 2 1 4 5
            1 9 2 1 6 21
            2 1 2 2 7 14
            3 2 2 3 8 9
            4 2 2 3 10 11
            5 2 2 3 12 13
            6 1 2 2 15 20
            7 6 2 3 16 17
            8 6 2 3 18 19
        """)

    def test_move_leaf_to_other_tree(self):
        shmup_horizontal = Genre.objects.get(id=8)
        rpg = Genre.objects.get(id=9)
        shmup_horizontal.parent = rpg
        shmup_horizontal.save()
        self.assertTreeEqual([shmup_horizontal], '8 9 2 1 6 7')
        self.assertTreeEqual([rpg], '9 - 2 0 1 8')
        self.assertTreeEqual(Genre.objects.all(), """
            1 - 1 0 1 14
            2 1 1 1 2 9
            3 2 1 2 3 4
            4 2 1 2 5 6
            5 2 1 2 7 8
            6 1 1 1 10 13
            7 6 1 2 11 12
            9 - 2 0 1 8
            10 9 2 1 2 3
            11 9 2 1 4 5
            8 9 2 1 6 7
        """)

    def test_move_subtree_to_other_tree(self):
        shmup = Genre.objects.get(id=6)
        trpg = Genre.objects.get(id=11)
        shmup.parent = trpg
        shmup.save()
        self.assertTreeEqual([shmup], '6 11 2 2 5 10')
        self.assertTreeEqual([trpg], '11 9 2 1 4 11')
        self.assertTreeEqual(Genre.objects.all(), """
            1 - 1 0 1 10
            2 1 1 1 2 9
            3 2 1 2 3 4
            4 2 1 2 5 6
            5 2 1 2 7 8
            9 - 2 0 1 12
            10 9 2 1 2 3
            11 9 2 1 4 11
            6 11 2 2 5 10
            7 6 2 3 6 7
            8 6 2 3 8 9
        """)

    def test_move_child_up_level(self):
        shmup_horizontal = Genre.objects.get(id=8)
        action = Genre.objects.get(id=1)
        shmup_horizontal.parent = action
        shmup_horizontal.save()
        self.assertTreeEqual([shmup_horizontal], '8 1 1 1 14 15')
        self.assertTreeEqual([action], '1 - 1 0 1 16')
        self.assertTreeEqual(Genre.objects.all(), """
            1 - 1 0 1 16
            2 1 1 1 2 9
            3 2 1 2 3 4
            4 2 1 2 5 6
            5 2 1 2 7 8
            6 1 1 1 10 13
            7 6 1 2 11 12
            8 1 1 1 14 15
            9 - 2 0 1 6
            10 9 2 1 2 3
            11 9 2 1 4 5
        """)

    def test_move_subtree_down_level(self):
        shmup = Genre.objects.get(id=6)
        platformer = Genre.objects.get(id=2)
        shmup.parent = platformer
        shmup.save()
        self.assertTreeEqual([shmup], '6 2 1 2 9 14')
        self.assertTreeEqual([platformer], '2 1 1 1 2 15')
        self.assertTreeEqual(Genre.objects.all(), """
            1 - 1 0 1 16
            2 1 1 1 2 15
            3 2 1 2 3 4
            4 2 1 2 5 6
            5 2 1 2 7 8
            6 2 1 2 9 14
            7 6 1 3 10 11
            8 6 1 3 12 13
            9 - 2 0 1 6
            10 9 2 1 2 3
            11 9 2 1 4 5
        """)

    def test_move_to(self):
        rpg = Genre.objects.get(pk=9)
        action = Genre.objects.get(pk=1)
        rpg.move_to(action)
        rpg.save()
        self.assertEqual(rpg.parent, action)

    def test_invalid_moves(self):
        # A node may not be made a child of itself
        action = Genre.objects.get(id=1)
        action.parent = action
        platformer = Genre.objects.get(id=2)
        platformer.parent = platformer
        self.assertRaises(InvalidMove, action.save)
        self.assertRaises(InvalidMove, platformer.save)

        # A node may not be made a child of any of its descendants
        platformer_4d = Genre.objects.get(id=5)
        action.parent = platformer_4d
        platformer.parent = platformer_4d
        self.assertRaises(InvalidMove, action.save)
        self.assertRaises(InvalidMove, platformer.save)

        # New parent is still set when an error occurs
        self.assertEquals(action.parent, platformer_4d)
        self.assertEquals(platformer.parent, platformer_4d)

# categories.json defines the following tree structure:
#
# 1 - 1 0 1 20    games
# 2 1 1 1 2 7     +-- wii
# 3 2 1 2 3 4     |   |-- wii_games
# 4 2 1 2 5 6     |   +-- wii_hardware
# 5 1 1 1 8 13    +-- xbox360
# 6 5 1 2 9 10    |   |-- xbox360_games
# 7 5 1 2 11 12   |   +-- xbox360_hardware
# 8 1 1 1 14 19   +-- ps3
# 9 8 1 2 15 16       |-- ps3_games
# 10 8 1 2 17 18      +-- ps3_hardware


class DeletionTestCase(TreeTestCase):
    """
    Tests that the tree structure is maintained appropriately in various
    deletion scenarios.
    """
    fixtures = ['categories.json']

    def test_delete_root_node(self):
        # Add a few other roots to verify that they aren't affected
        Category(name='Preceding root').insert_at(Category.objects.get(id=1),
                                                  'left', save=True)
        Category(name='Following root').insert_at(Category.objects.get(id=1),
                                                  'right', save=True)
        self.assertTreeEqual(Category.objects.all(), """
            11 - 1 0 1 2
            1 - 2 0 1 20
            2 1 2 1 2 7
            3 2 2 2 3 4
            4 2 2 2 5 6
            5 1 2 1 8 13
            6 5 2 2 9 10
            7 5 2 2 11 12
            8 1 2 1 14 19
            9 8 2 2 15 16
            10 8 2 2 17 18
            12 - 3 0 1 2
        """)

        Category.objects.get(id=1).delete()
        self.assertTreeEqual(
            Category.objects.all(), """
            11 - 1 0 1 2
            12 - 3 0 1 2
        """)

    def test_delete_last_node_with_siblings(self):
        Category.objects.get(id=9).delete()
        self.assertTreeEqual(Category.objects.all(), """
            1 - 1 0 1 18
            2 1 1 1 2 7
            3 2 1 2 3 4
            4 2 1 2 5 6
            5 1 1 1 8 13
            6 5 1 2 9 10
            7 5 1 2 11 12
            8 1 1 1 14 17
            10 8 1 2 15 16
        """)

    def test_delete_last_node_with_descendants(self):
        Category.objects.get(id=8).delete()
        self.assertTreeEqual(Category.objects.all(), """
            1 - 1 0 1 14
            2 1 1 1 2 7
            3 2 1 2 3 4
            4 2 1 2 5 6
            5 1 1 1 8 13
            6 5 1 2 9 10
            7 5 1 2 11 12
        """)

    def test_delete_node_with_siblings(self):
        Category.objects.get(id=6).delete()
        self.assertTreeEqual(Category.objects.all(), """
            1 - 1 0 1 18
            2 1 1 1 2 7
            3 2 1 2 3 4
            4 2 1 2 5 6
            5 1 1 1 8 11
            7 5 1 2 9 10
            8 1 1 1 12 17
            9 8 1 2 13 14
            10 8 1 2 15 16
        """)

    def test_delete_node_with_descendants_and_siblings(self):
        """
        Regression test for Issue 23 - we used to use pre_delete, which
        resulted in tree cleanup being performed for every node being
        deleted, rather than just the node on which ``delete()`` was
        called.
        """
        Category.objects.get(id=5).delete()
        self.assertTreeEqual(Category.objects.all(), """
            1 - 1 0 1 14
            2 1 1 1 2 7
            3 2 1 2 3 4
            4 2 1 2 5 6
            8 1 1 1 8 13
            9 8 1 2 9 10
            10 8 1 2 11 12
        """)


class IntraTreeMovementTestCase(TreeTestCase):
    pass


class InterTreeMovementTestCase(TreeTestCase):
    pass


class PositionedInsertionTestCase(TreeTestCase):
    pass


class FeinCMSModelAdminTestCase(TreeTestCase):
    """
    Tests for FeinCMSModelAdmin.
    """
    fixtures = ['categories.json']

    @unittest.skipIf(not feincms, "Requires feincms")
    def test_actions_column(self):
        """
        The action column should have an "add" button inserted.
        """
        from mptt.admin import FeinCMSModelAdmin
        model_admin = FeinCMSModelAdmin(Category, admin.site)

        # See implementation notes.
        if django.VERSION < (1, 4):
            prefix = '/static/admin/img/admin/'
        else:
            prefix = '/static/admin/img/'

        category = Category.objects.get(id=1)
        self.assertEqual(model_admin._actions_column(category), [
            u'<a href="add/?parent=1" title="Add child">'
                u'<img src="%sicon_addlink.gif" alt="Add child" /></a>' % prefix,
            '<div class="drag_handle"></div>'])


class CustomPKNameTestCase(TreeTestCase):
    def setUp(self):
        manager = CustomPKName.objects
        c1 = manager.create(name="c1")
        manager.create(name="c11", parent=c1)
        manager.create(name="c12", parent=c1)

        c2 = manager.create(name="c2")
        manager.create(name="c21", parent=c2)
        manager.create(name="c22", parent=c2)

        manager.create(name="c3")

    def test_get_next_sibling(self):
        root = CustomPKName.objects.get(name="c12")
        sib = root.get_next_sibling()
        self.assertTrue(sib is None)


class DisabledUpdatesTestCase(TreeTestCase):
    def setUp(self):
        # a
        # -- b
        # c
        self.a = ConcreteModel.objects.create(name="a")
        self.b = ConcreteModel.objects.create(name="b", parent=self.a)
        self.c = ConcreteModel.objects.create(name="c")

    def test_single_proxy(self):
        self.assertTrue(ConcreteModel._mptt_updates_enabled)
        self.assertTrue(SingleProxyModel._mptt_updates_enabled)

        self.assertRaises(CantDisableUpdates, SingleProxyModel.objects.disable_mptt_updates().__enter__)

        self.assertTrue(ConcreteModel._mptt_updates_enabled)
        self.assertTrue(SingleProxyModel._mptt_updates_enabled)

        with ConcreteModel.objects.disable_mptt_updates():
            self.assertFalse(ConcreteModel._mptt_updates_enabled)
            self.assertFalse(SingleProxyModel._mptt_updates_enabled)

        self.assertTrue(ConcreteModel._mptt_updates_enabled)
        self.assertTrue(SingleProxyModel._mptt_updates_enabled)

    def test_double_proxy(self):
        self.assertTrue(ConcreteModel._mptt_updates_enabled)
        self.assertTrue(DoubleProxyModel._mptt_updates_enabled)

        self.assertRaises(CantDisableUpdates, DoubleProxyModel.objects.disable_mptt_updates().__enter__)

        self.assertTrue(ConcreteModel._mptt_updates_enabled)
        self.assertTrue(DoubleProxyModel._mptt_updates_enabled)

        with ConcreteModel.objects.disable_mptt_updates():
            self.assertFalse(ConcreteModel._mptt_updates_enabled)
            self.assertFalse(DoubleProxyModel._mptt_updates_enabled)

        self.assertTrue(ConcreteModel._mptt_updates_enabled)
        self.assertTrue(DoubleProxyModel._mptt_updates_enabled)

    def test_insert_child(self):
        self.assertTreeEqual(ConcreteModel.objects.all(), """
            1 - 1 0 1 4
            2 1 1 1 2 3
            3 - 2 0 1 2
        """)
        with self.assertNumQueries(2):
            with ConcreteModel.objects.disable_mptt_updates():
                # 1 query here:
                with self.assertNumQueries(1):
                    ConcreteModel.objects.create(name="d", parent=self.c)
                # 2nd query here:
                self.assertTreeEqual(ConcreteModel.objects.all(), """
                    1 - 1 0 1 4
                    2 1 1 1 2 3
                    3 - 2 0 1 2
                    4 3 2 1 2 3
                """)

        # yes, this is wrong. that's what disable_mptt_updates() does :/
        self.assertTreeEqual(ConcreteModel.objects.all(), """
            1 - 1 0 1 4
            2 1 1 1 2 3
            3 - 2 0 1 2
            4 3 2 1 2 3
        """)

    def test_insert_root(self):
        self.assertTreeEqual(ConcreteModel.objects.all(), """
            1 - 1 0 1 4
            2 1 1 1 2 3
            3 - 2 0 1 2
        """)
        with self.assertNumQueries(2):
            with ConcreteModel.objects.disable_mptt_updates():
                with self.assertNumQueries(1):
                    # 1 query here:
                    ConcreteModel.objects.create(name="d")
                # 2nd query here:
                self.assertTreeEqual(ConcreteModel.objects.all(), """
                    4 - 0 0 1 2
                    1 - 1 0 1 4
                    2 1 1 1 2 3
                    3 - 2 0 1 2
                """)
        self.assertTreeEqual(ConcreteModel.objects.all(), """
            4 - 0 0 1 2
            1 - 1 0 1 4
            2 1 1 1 2 3
            3 - 2 0 1 2
        """)


class DelayedUpdatesTestCase(TreeTestCase):
    def setUp(self):
        # a
        # -- b
        # c
        self.a = ConcreteModel.objects.create(name="a")
        self.b = ConcreteModel.objects.create(name="b", parent=self.a)
        self.c = ConcreteModel.objects.create(name="c")

    def test_proxy(self):
        self.assertFalse(ConcreteModel._mptt_is_tracking)
        self.assertFalse(SingleProxyModel._mptt_is_tracking)

        self.assertRaises(CantDisableUpdates, SingleProxyModel.objects.delay_mptt_updates().__enter__)

        self.assertFalse(ConcreteModel._mptt_is_tracking)
        self.assertFalse(SingleProxyModel._mptt_is_tracking)

        with ConcreteModel.objects.delay_mptt_updates():
            self.assertTrue(ConcreteModel._mptt_is_tracking)
            self.assertTrue(SingleProxyModel._mptt_is_tracking)

        self.assertFalse(ConcreteModel._mptt_is_tracking)
        self.assertFalse(SingleProxyModel._mptt_is_tracking)

    def test_double_context_manager(self):
        with ConcreteModel.objects.delay_mptt_updates():
            self.assertTrue(ConcreteModel._mptt_is_tracking)
            with ConcreteModel.objects.delay_mptt_updates():
                self.assertTrue(ConcreteModel._mptt_is_tracking)
            self.assertTrue(ConcreteModel._mptt_is_tracking)
        self.assertFalse(ConcreteModel._mptt_is_tracking)

    def test_insert_child(self):
        self.assertTreeEqual(ConcreteModel.objects.all(), """
            1 - 1 0 1 4
            2 1 1 1 2 3
            3 - 2 0 1 2
        """)
        with self.assertNumQueries(7):
            with ConcreteModel.objects.delay_mptt_updates():
                with self.assertNumQueries(1):
                    # 1 query here:
                    ConcreteModel.objects.create(name="d", parent=self.c)
                # 2nd query here:
                self.assertTreeEqual(ConcreteModel.objects.all(), """
                    1 - 1 0 1 4
                    2 1 1 1 2 3
                    3 - 2 0 1 2
                    4 3 2 1 2 3
                """)
                # remaining queries (3 through 7) are the partial rebuild process.

        self.assertTreeEqual(ConcreteModel.objects.all(), """
            1 - 1 0 1 4
            2 1 1 1 2 3
            3 - 2 0 1 4
            4 3 2 1 2 3
        """)

    def test_insert_root(self):
        self.assertTreeEqual(ConcreteModel.objects.all(), """
            1 - 1 0 1 4
            2 1 1 1 2 3
            3 - 2 0 1 2
        """)
        with self.assertNumQueries(3):
            with ConcreteModel.objects.delay_mptt_updates():
                with self.assertNumQueries(2):
                    # 2 queries required here:
                    # (one to get the correct tree_id, then one to insert)
                    ConcreteModel.objects.create(name="d")
                # 3rd query here:
                self.assertTreeEqual(ConcreteModel.objects.all(), """
                    1 - 1 0 1 4
                    2 1 1 1 2 3
                    3 - 2 0 1 2
                    4 - 3 0 1 2
                """)
                # no partial rebuild necessary, as no trees were modified
                # (newly created tree is already okay)
        self.assertTreeEqual(ConcreteModel.objects.all(), """
            1 - 1 0 1 4
            2 1 1 1 2 3
            3 - 2 0 1 2
            4 - 3 0 1 2
        """)
