from __future__ import unicode_literals

import os
import re
import sys
import tempfile

import django
from django.contrib.auth.models import Group
from django.db.models import get_models
from django.forms.models import modelform_factory
from django.template import Template, Context
from django.test import TestCase
from django.utils.six import string_types, PY3, b

from mptt.exceptions import CantDisableUpdates, InvalidMove
from mptt.forms import MPTTAdminForm
from mptt.models import MPTTModel
from mptt.templatetags.mptt_tags import cache_tree_children
from myapp.models import (
    Category, Genre, CustomPKName, SingleProxyModel, DoubleProxyModel,
    ConcreteModel, OrderedInsertion, AutoNowDateFieldModel, Person,
    CustomTreeQueryset, Node)

extra_queries_per_update = 0
if django.VERSION < (1, 6):
    # before django 1.6, Model.save() did a select then an update/insert.
    # now, Model.save() does an update followed an insert if the update changed 0 rows.
    extra_queries_per_update = 1


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
        if not isinstance(tree1, string_types):
            tree1 = get_tree_details(tree1)
        tree1 = tree_details(tree1)
        if not isinstance(tree2, string_types):
            tree2 = get_tree_details(tree2)
        tree2 = tree_details(tree2)
        return self.assertEqual(tree1, tree2, "\n%r\n != \n%r" % (tree1, tree2))


class DocTestTestCase(TreeTestCase):
    def test_run_doctest(self):
        class DummyStream:
            content = ""
            encoding = 'utf8'

            def write(self, text):
                self.content += text

            def flush(self):
                pass

        dummy_stream = DummyStream()
        before = sys.stdout
        sys.stdout = dummy_stream

        with open(os.path.join(os.path.dirname(__file__), 'doctests.txt')) as f:
            with tempfile.NamedTemporaryFile() as temp:
                text = f.read()

                if PY3:
                    # unicode literals in the doctests screw up doctest on py3.
                    # this is pretty icky, but I can't find any other
                    # workarounds :(
                    text = re.sub(r"""\bu(["\'])""", r"\1", text)
                    temp.write(b(text))

                temp.flush()

                import doctest
                doctest.testfile(
                    temp.name,
                    module_relative=False,
                    optionflags=doctest.IGNORE_EXCEPTION_DETAIL,
                    encoding='utf-8',
                )
                sys.stdout = before
                content = dummy_stream.content
                if content:
                    before.write(content + '\n')
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
        self.assertEqual(action.parent, platformer_4d)
        self.assertEqual(platformer.parent, platformer_4d)

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
        child = Category.objects.get(id=6)
        parent = child.parent
        self.assertEqual(parent.get_descendant_count(), 2)
        child.delete()
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
        self.assertEqual(parent.get_descendant_count(), 1)
        parent = Category.objects.get(pk=parent.pk)
        self.assertEqual(parent.get_descendant_count(), 1)

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
        self.a = ConcreteModel.objects.create(name="a")
        self.b = ConcreteModel.objects.create(name="b", parent=self.a)
        self.c = ConcreteModel.objects.create(name="c", parent=self.a)
        self.d = ConcreteModel.objects.create(name="d")
        # state is now:
        self.assertTreeEqual(ConcreteModel.objects.all(), """
            1 - 1 0 1 6
            2 1 1 1 2 3
            3 1 1 1 4 5
            4 - 2 0 1 2
        """)

    def test_single_proxy(self):
        self.assertTrue(ConcreteModel._mptt_updates_enabled)
        self.assertTrue(SingleProxyModel._mptt_updates_enabled)

        self.assertRaises(
            CantDisableUpdates,
            SingleProxyModel.objects.disable_mptt_updates().__enter__)

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

        self.assertRaises(
            CantDisableUpdates,
            DoubleProxyModel.objects.disable_mptt_updates().__enter__)

        self.assertTrue(ConcreteModel._mptt_updates_enabled)
        self.assertTrue(DoubleProxyModel._mptt_updates_enabled)

        with ConcreteModel.objects.disable_mptt_updates():
            self.assertFalse(ConcreteModel._mptt_updates_enabled)
            self.assertFalse(DoubleProxyModel._mptt_updates_enabled)

        self.assertTrue(ConcreteModel._mptt_updates_enabled)
        self.assertTrue(DoubleProxyModel._mptt_updates_enabled)

    def test_insert_child(self):
        with self.assertNumQueries(2):
            with ConcreteModel.objects.disable_mptt_updates():
                # 1 query here:
                with self.assertNumQueries(1):
                    ConcreteModel.objects.create(name="e", parent=self.d)
                # 2nd query here:
                self.assertTreeEqual(ConcreteModel.objects.all(), """
                    1 - 1 0 1 6
                    2 1 1 1 2 3
                    3 1 1 1 4 5
                    4 - 2 0 1 2
                    5 4 2 1 2 3
                """)

        # yes, this is wrong. that's what disable_mptt_updates() does :/
        self.assertTreeEqual(ConcreteModel.objects.all(), """
            1 - 1 0 1 6
            2 1 1 1 2 3
            3 1 1 1 4 5
            4 - 2 0 1 2
            5 4 2 1 2 3
        """)

    def test_insert_root(self):
        with self.assertNumQueries(2):
            with ConcreteModel.objects.disable_mptt_updates():
                with self.assertNumQueries(1):
                    # 1 query here:
                    ConcreteModel.objects.create(name="e")
                # 2nd query here:
                self.assertTreeEqual(ConcreteModel.objects.all(), """
                    5 - 0 0 1 2
                    1 - 1 0 1 6
                    2 1 1 1 2 3
                    3 1 1 1 4 5
                    4 - 2 0 1 2
                """)
        self.assertTreeEqual(ConcreteModel.objects.all(), """
            5 - 0 0 1 2
            1 - 1 0 1 6
            2 1 1 1 2 3
            3 1 1 1 4 5
            4 - 2 0 1 2
        """)

    def test_move_node_same_tree(self):
        with self.assertNumQueries(2 + extra_queries_per_update):
            with ConcreteModel.objects.disable_mptt_updates():
                with self.assertNumQueries(1 + extra_queries_per_update):
                    # 2 queries here:
                    #  (django does a query to determine if the row is in the db yet)
                    self.c.parent = self.b
                    self.c.save()
                # 3rd query here:
                self.assertTreeEqual(ConcreteModel.objects.all(), """
                    1 - 1 0 1 6
                    2 1 1 1 2 3
                    3 2 1 1 4 5
                    4 - 2 0 1 2
                """)

        # yes, this is wrong. that's what disable_mptt_updates() does :/
        self.assertTreeEqual(ConcreteModel.objects.all(), """
            1 - 1 0 1 6
            2 1 1 1 2 3
            3 2 1 1 4 5
            4 - 2 0 1 2
        """)

    def test_move_node_different_tree(self):
        with self.assertNumQueries(2 + extra_queries_per_update):
            with ConcreteModel.objects.disable_mptt_updates():
                with self.assertNumQueries(1 + extra_queries_per_update):
                    # 1 update query
                    self.c.parent = self.d
                    self.c.save()
                # query 2 here:
                self.assertTreeEqual(ConcreteModel.objects.all(), """
                    1 - 1 0 1 6
                    2 1 1 1 2 3
                    3 4 1 1 4 5
                    4 - 2 0 1 2
                """)

        # yes, this is wrong. that's what disable_mptt_updates() does :/
        self.assertTreeEqual(ConcreteModel.objects.all(), """
            1 - 1 0 1 6
            2 1 1 1 2 3
            3 4 1 1 4 5
            4 - 2 0 1 2
        """)

    def test_move_node_to_root(self):
        with self.assertNumQueries(2 + extra_queries_per_update):
            with ConcreteModel.objects.disable_mptt_updates():
                with self.assertNumQueries(1 + extra_queries_per_update):
                    # 1 update query
                    self.c.parent = None
                    self.c.save()
                # query 2 here:
                self.assertTreeEqual(ConcreteModel.objects.all(), """
                    1 - 1 0 1 6
                    2 1 1 1 2 3
                    3 - 1 1 4 5
                    4 - 2 0 1 2
                """)

        # yes, this is wrong. that's what disable_mptt_updates() does :/
        self.assertTreeEqual(ConcreteModel.objects.all(), """
            1 - 1 0 1 6
            2 1 1 1 2 3
            3 - 1 1 4 5
            4 - 2 0 1 2
        """)

    def test_move_root_to_child(self):
        with self.assertNumQueries(2 + extra_queries_per_update):
            with ConcreteModel.objects.disable_mptt_updates():
                with self.assertNumQueries(1 + extra_queries_per_update):
                    # 1 update query
                    self.d.parent = self.c
                    self.d.save()
                # query 2 here:
                self.assertTreeEqual(ConcreteModel.objects.all(), """
                    1 - 1 0 1 6
                    2 1 1 1 2 3
                    3 1 1 1 4 5
                    4 3 2 0 1 2
                """)

        # yes, this is wrong. that's what disable_mptt_updates() does :/
        self.assertTreeEqual(ConcreteModel.objects.all(), """
            1 - 1 0 1 6
            2 1 1 1 2 3
            3 1 1 1 4 5
            4 3 2 0 1 2
        """)


class DelayedUpdatesTestCase(TreeTestCase):
    def setUp(self):
        self.a = ConcreteModel.objects.create(name="a")
        self.b = ConcreteModel.objects.create(name="b", parent=self.a)
        self.c = ConcreteModel.objects.create(name="c", parent=self.a)
        self.d = ConcreteModel.objects.create(name="d")
        self.z = ConcreteModel.objects.create(name="z")
        # state is now:
        self.assertTreeEqual(ConcreteModel.objects.all(), """
            1 - 1 0 1 6
            2 1 1 1 2 3
            3 1 1 1 4 5
            4 - 2 0 1 2
            5 - 3 0 1 2
        """)

    def test_proxy(self):
        self.assertFalse(ConcreteModel._mptt_is_tracking)
        self.assertFalse(SingleProxyModel._mptt_is_tracking)

        self.assertRaises(
            CantDisableUpdates,
            SingleProxyModel.objects.delay_mptt_updates().__enter__)

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
        with self.assertNumQueries(7):
            with ConcreteModel.objects.delay_mptt_updates():
                with self.assertNumQueries(1):
                    # 1 query here:
                    ConcreteModel.objects.create(name="e", parent=self.d)
                # 2nd query here:
                self.assertTreeEqual(ConcreteModel.objects.all(), """
                    1 - 1 0 1 6
                    2 1 1 1 2 3
                    3 1 1 1 4 5
                    4 - 2 0 1 2
                    6 4 2 1 2 3
                    5 - 3 0 1 2
                """)
                # remaining queries (3 through 7) are the partial rebuild process.

        self.assertTreeEqual(ConcreteModel.objects.all(), """
            1 - 1 0 1 6
            2 1 1 1 2 3
            3 1 1 1 4 5
            4 - 2 0 1 4
            6 4 2 1 2 3
            5 - 3 0 1 2
        """)

    def test_insert_root(self):
        with self.assertNumQueries(3):
            with ConcreteModel.objects.delay_mptt_updates():
                with self.assertNumQueries(2):
                    # 2 queries required here:
                    # (one to get the correct tree_id, then one to insert)
                    ConcreteModel.objects.create(name="e")
                # 3rd query here:
                self.assertTreeEqual(ConcreteModel.objects.all(), """
                    1 - 1 0 1 6
                    2 1 1 1 2 3
                    3 1 1 1 4 5
                    4 - 2 0 1 2
                    5 - 3 0 1 2
                    6 - 4 0 1 2
                """)
                # no partial rebuild necessary, as no trees were modified
                # (newly created tree is already okay)
        self.assertTreeEqual(ConcreteModel.objects.all(), """
            1 - 1 0 1 6
            2 1 1 1 2 3
            3 1 1 1 4 5
            4 - 2 0 1 2
            5 - 3 0 1 2
            6 - 4 0 1 2
        """)

    def test_move_node_same_tree(self):
        with self.assertNumQueries(9 + extra_queries_per_update):
            with ConcreteModel.objects.delay_mptt_updates():
                with self.assertNumQueries(1 + extra_queries_per_update):
                    # 1 update query
                    self.c.parent = self.b
                    self.c.save()
                # query 2 here:
                self.assertTreeEqual(ConcreteModel.objects.all(), """
                    1 - 1 0 1 6
                    2 1 1 1 2 3
                    3 2 1 2 3 4
                    4 - 2 0 1 2
                    5 - 3 0 1 2
                """)
            # the remaining 7 queries are the partial rebuild.

        self.assertTreeEqual(ConcreteModel.objects.all(), """
            1 - 1 0 1 6
            2 1 1 1 2 5
            3 2 1 2 3 4
            4 - 2 0 1 2
            5 - 3 0 1 2
        """)

    def test_move_node_different_tree(self):
        with self.assertNumQueries(12 + extra_queries_per_update):
            with ConcreteModel.objects.delay_mptt_updates():
                with self.assertNumQueries(2 + extra_queries_per_update):
                    # 2 queries here:
                    #  1. update the node
                    #  2. collapse old tree since it is now empty.
                    self.d.parent = self.c
                    self.d.save()
                # query 3 here:
                self.assertTreeEqual(ConcreteModel.objects.all(), """
                    1 - 1 0 1 6
                    2 1 1 1 2 3
                    3 1 1 1 4 5
                    4 3 1 2 5 6
                    5 - 2 0 1 2
                """)
            # the other 9 queries are the partial rebuild

        self.assertTreeEqual(ConcreteModel.objects.all(), """
            1 - 1 0 1 8
            2 1 1 1 2 3
            3 1 1 1 4 7
            4 3 1 2 5 6
            5 - 2 0 1 2
        """)

    def test_move_node_to_root(self):
        with self.assertNumQueries(4 + extra_queries_per_update):
            with ConcreteModel.objects.delay_mptt_updates():
                with self.assertNumQueries(3 + extra_queries_per_update):
                    # 3 queries here!
                    #   1. find the next tree_id to move to
                    #   2. update the tree_id on all nodes to the right of that
                    #   3. update tree fields on self.c
                    self.c.parent = None
                    self.c.save()
                # 4th query here:
                self.assertTreeEqual(ConcreteModel.objects.all(), """
                    1 - 1 0 1 6
                    2 1 1 1 2 3
                    4 - 2 0 1 2
                    5 - 3 0 1 2
                    3 - 4 0 1 2
                """)

        self.assertTreeEqual(ConcreteModel.objects.all(), """
            1 - 1 0 1 6
            2 1 1 1 2 3
            4 - 2 0 1 2
            5 - 3 0 1 2
            3 - 4 0 1 2
        """)

    def test_move_root_to_child(self):
        with self.assertNumQueries(12 + extra_queries_per_update):
            with ConcreteModel.objects.delay_mptt_updates():
                with self.assertNumQueries(2 + extra_queries_per_update):
                    # 2 queries here:
                    #  1. update the node
                    #  2. collapse old tree since it is now empty.
                    self.d.parent = self.c
                    self.d.save()
                # query 3 here:
                self.assertTreeEqual(ConcreteModel.objects.all(), """
                    1 - 1 0 1 6
                    2 1 1 1 2 3
                    3 1 1 1 4 5
                    4 3 1 2 5 6
                    5 - 2 0 1 2
                """)
            # the remaining 9 queries are the partial rebuild.

        self.assertTreeEqual(ConcreteModel.objects.all(), """
            1 - 1 0 1 8
            2 1 1 1 2 3
            3 1 1 1 4 7
            4 3 1 2 5 6
            5 - 2 0 1 2
        """)


class OrderedInsertionDelayedUpdatesTestCase(TreeTestCase):
    def setUp(self):
        self.c = OrderedInsertion.objects.create(name="c")
        self.d = OrderedInsertion.objects.create(name="d", parent=self.c)
        self.e = OrderedInsertion.objects.create(name="e", parent=self.c)
        self.f = OrderedInsertion.objects.create(name="f")
        self.z = OrderedInsertion.objects.create(name="z")
        # state is now:
        self.assertTreeEqual(OrderedInsertion.objects.all(), """
            1 - 1 0 1 6
            2 1 1 1 2 3
            3 1 1 1 4 5
            4 - 2 0 1 2
            5 - 3 0 1 2
        """)

    def test_insert_child(self):
        with self.assertNumQueries(11):
            with OrderedInsertion.objects.delay_mptt_updates():
                with self.assertNumQueries(1):
                    # 1 query here:
                    OrderedInsertion.objects.create(name="dd", parent=self.c)
                # 2nd query here:
                self.assertTreeEqual(OrderedInsertion.objects.all(), """
                    1 - 1 0 1 6
                    2 1 1 1 2 3
                    3 1 1 1 4 5
                    6 1 1 1 6 7
                    4 - 2 0 1 2
                    5 - 3 0 1 2
                """)
                # remaining 9 queries are the partial rebuild process.

        self.assertTreeEqual(OrderedInsertion.objects.all(), """
            1 - 1 0 1 8
            2 1 1 1 2 3
            6 1 1 1 4 5
            3 1 1 1 6 7
            4 - 2 0 1 2
            5 - 3 0 1 2
        """)

    def test_insert_root(self):
        with self.assertNumQueries(4):
            with OrderedInsertion.objects.delay_mptt_updates():
                with self.assertNumQueries(3):
                    # 3 queries required here:
                    #   1. get correct tree_id (delay_mptt_updates doesn't handle
                    #       root-level ordering when using ordered insertion)
                    #   2. increment tree_id of all following trees
                    #   3. insert the object
                    OrderedInsertion.objects.create(name="ee")
                # 4th query here:
                self.assertTreeEqual(OrderedInsertion.objects.all(), """
                    1 - 1 0 1 6
                    2 1 1 1 2 3
                    3 1 1 1 4 5
                    6 - 2 0 1 2
                    4 - 3 0 1 2
                    5 - 4 0 1 2
                """)
            # no partial rebuild is required
        self.assertTreeEqual(OrderedInsertion.objects.all(), """
            1 - 1 0 1 6
            2 1 1 1 2 3
            3 1 1 1 4 5
            6 - 2 0 1 2
            4 - 3 0 1 2
            5 - 4 0 1 2
        """)

    def test_move_node_same_tree(self):
        with self.assertNumQueries(9 + extra_queries_per_update):
            with OrderedInsertion.objects.delay_mptt_updates():
                with self.assertNumQueries(1 + extra_queries_per_update):
                    # 1 update query
                    self.e.name = 'before d'
                    self.e.save()
                # query 2 here:
                self.assertTreeEqual(OrderedInsertion.objects.all(), """
                    1 - 1 0 1 6
                    2 1 1 1 2 3
                    3 1 1 1 4 5
                    4 - 2 0 1 2
                    5 - 3 0 1 2
                """)
            # the remaining 7 queries are the partial rebuild.

        self.assertTreeEqual(OrderedInsertion.objects.all(), """
            1 - 1 0 1 6
            3 1 1 1 2 3
            2 1 1 1 4 5
            4 - 2 0 1 2
            5 - 3 0 1 2
        """)

    def test_move_node_different_tree(self):
        with self.assertNumQueries(12 + extra_queries_per_update):
            with OrderedInsertion.objects.delay_mptt_updates():
                with self.assertNumQueries(2 + extra_queries_per_update):
                    # 2 queries here:
                    #  1. update the node
                    #  2. collapse old tree since it is now empty.
                    self.f.parent = self.c
                    self.f.name = 'dd'
                    self.f.save()
                # query 3 here:
                self.assertTreeEqual(OrderedInsertion.objects.all(), """
                    1 - 1 0 1 6
                    2 1 1 1 2 3
                    4 1 1 1 2 3
                    3 1 1 1 4 5
                    5 - 2 0 1 2
                """)
            # the remaining 9 queries are the partial rebuild

        self.assertTreeEqual(OrderedInsertion.objects.all(), """
            1 - 1 0 1 8
            2 1 1 1 2 3
            4 1 1 1 4 5
            3 1 1 1 6 7
            5 - 2 0 1 2
        """)

    def test_move_node_to_root(self):
        with self.assertNumQueries(4 + extra_queries_per_update):
            with OrderedInsertion.objects.delay_mptt_updates():
                with self.assertNumQueries(3 + extra_queries_per_update):
                    # 3 queries here!
                    #   1. find the next tree_id to move to
                    #   2. update the tree_id on all nodes to the right of that
                    #   3. update tree fields on self.c
                    self.e.parent = None
                    self.e.save()
                # query 4 here:
                self.assertTreeEqual(OrderedInsertion.objects.all(), """
                    1 - 1 0 1 6
                    2 1 1 1 2 3
                    3 - 2 0 1 2
                    4 - 3 0 1 2
                    5 - 4 0 1 2
                """)

        self.assertTreeEqual(OrderedInsertion.objects.all(), """
            1 - 1 0 1 6
            2 1 1 1 2 3
            3 - 2 0 1 2
            4 - 3 0 1 2
            5 - 4 0 1 2
        """)

    def test_move_root_to_child(self):
        with self.assertNumQueries(12 + extra_queries_per_update):
            with OrderedInsertion.objects.delay_mptt_updates():
                with self.assertNumQueries(2 + extra_queries_per_update):
                    # 2 queries here:
                    #  1. update the node
                    #  2. collapse old tree since it is now empty.
                    self.f.parent = self.e
                    self.f.save()
                # query 3 here:
                self.assertTreeEqual(OrderedInsertion.objects.all(), """
                    1 - 1 0 1 6
                    2 1 1 1 2 3
                    3 1 1 1 4 5
                    4 3 1 2 5 6
                    5 - 2 0 1 2
                """)
            # the remaining 9 queries are the partial rebuild.

        self.assertTreeEqual(OrderedInsertion.objects.all(), """
            1 - 1 0 1 8
            2 1 1 1 2 3
            3 1 1 1 4 7
            4 3 1 2 5 6
            5 - 2 0 1 2
        """)


class ManagerTests(TreeTestCase):
    fixtures = ['categories.json']

    def test_all_managers_are_different(self):
        # all tree managers should be different. otherwise, possible infinite recursion.
        seen = {}
        for model in get_models():
            if not issubclass(model, MPTTModel):
                continue
            tm = model._tree_manager
            if tm in seen:
                self.fail(
                    "Tree managers for %s and %s are the same manager"
                    % (model.__name__, seen[tm].__name__))
            seen[tm] = model

    def test_all_managers_have_correct_model(self):
        # all tree managers should have the correct model.
        for model in get_models():
            if not issubclass(model, MPTTModel):
                continue
            self.assertEqual(model._tree_manager.model, model)

    def test_base_manager_infinite_recursion(self):
        # repeatedly calling _base_manager should eventually return None
        for model in get_models():
            if not issubclass(model, MPTTModel):
                continue
            manager = model._tree_manager
            for i in range(20):
                manager = manager._base_manager
                if manager is None:
                    break
            else:
                self.fail("Detected infinite recursion in %s._tree_manager._base_manager" % model)

    def test_get_queryset_descendants(self):
        def get_desc_names(qs, include_self=False):
            desc = Category.objects.get_queryset_descendants(qs, include_self=include_self)
            return list(desc.values_list('name', flat=True).order_by('name'))

        qs = Category.objects.filter(name='Nintendo Wii')
        self.assertEqual(
            get_desc_names(qs),
            ['Games', 'Hardware & Accessories'],
        )
        self.assertEqual(
            get_desc_names(qs, include_self=True),
            ['Games', 'Hardware & Accessories', 'Nintendo Wii'],
        )

    def test_get_queryset_ancestors(self):
        def get_anc_names(qs, include_self=False):
            anc = Category.objects.get_queryset_ancestors(qs, include_self=include_self)
            return list(anc.values_list('name', flat=True).order_by('name'))

        qs = Category.objects.filter(name='Nintendo Wii')
        self.assertEqual(
            get_anc_names(qs),
            ['PC & Video Games'],
        )
        self.assertEqual(
            get_anc_names(qs, include_self=True),
            ['Nintendo Wii', 'PC & Video Games'],
        )

    def test_custom_querysets(self):
        """
        Test that a custom manager also provides custom querysets.
        """

        self.assertTrue(isinstance(Person.objects.all(), CustomTreeQueryset))
        self.assertEqual(
            type(Person.objects.all()),
            type(Person.objects.root_nodes())
        )


class CacheTreeChildrenTestCase(TreeTestCase):
    """
    Tests for the ``cache_tree_children`` template filter.
    """
    fixtures = ['categories.json']

    def test_cache_tree_children_caches_parents(self):
        """
        Ensures that each node's parent is cached by ``cache_tree_children``.
        """
        # Ensure only 1 query is used during this test
        with self.assertNumQueries(1):
            roots = cache_tree_children(Category.objects.all())
            games = roots[0]
            wii = games.get_children()[0]
            wii_games = wii.get_children()[0]
            # Ensure that ``wii`` is cached as ``parent`` on ``wii_games``, and
            # likewise for ``games`` being ``parent`` on the attached ``wii``
            self.assertEqual(wii, wii_games.parent)
            self.assertEqual(games, wii_games.parent.parent)


class RecurseTreeTestCase(TreeTestCase):
    """
    Tests for the ``recursetree`` template filter.
    """
    fixtures = ['categories.json']
    template = re.sub(r'(?m)^[\s]+', '', '''
        {% load mptt_tags %}
        <ul>
            {% recursetree nodes %}
                <li>
                    {{ node.name }}
                    {% if not node.is_leaf_node %}
                        <ul class="children">
                            {{ children }}
                        </ul>
                    {% endif %}
                </li>
            {% endrecursetree %}
        </ul>
    ''')

    def test_leaf_html(self):
        html = Template(self.template).render(Context({
            'nodes': Category.objects.filter(pk=10),
        })).replace('\n', '')
        self.assertEqual(html, '<ul><li>Hardware &amp; Accessories</li></ul>')

    def test_nonleaf_html(self):
        qs = Category.objects.get(pk=8).get_descendants(include_self=True)
        html = Template(self.template).render(Context({
            'nodes': qs,
        })).replace('\n', '')
        self.assertEqual(html, (
            '<ul><li>PlayStation 3<ul class="children">'
            '<li>Games</li><li>Hardware &amp; Accessories</li></ul></li></ul>'
        ))


class TestAutoNowDateFieldModel(TreeTestCase):
    # https://github.com/django-mptt/django-mptt/issues/175

    def test_save_auto_now_date_field_model(self):
        a = AutoNowDateFieldModel()
        a.save()


class RegisteredRemoteModel(TreeTestCase):
    def test_save_registered_model(self):
        g1 = Group.objects.create(name='group 1')
        g1.save()


class TestForms(TreeTestCase):
    fixtures = ['categories.json']

    def test_adminform_instantiation(self):
        # https://github.com/django-mptt/django-mptt/issues/264
        c = Category.objects.get(name='Nintendo Wii')
        CategoryForm = modelform_factory(
            Category,
            form=MPTTAdminForm,
            fields=('name', 'parent'),
        )
        CategoryForm(instance=c)


class TestAltersData(TreeTestCase):
    def test_alters_data(self):
        node = Node()
        output = Template('{{ node.save }}').render(Context({
            'node': node,
        }))
        self.assertEqual(output, '')
        self.assertEqual(node.pk, None)

        node.save()
        self.assertNotEqual(node.pk, None)

        output = Template('{{ node.delete }}').render(Context({
            'node': node,
        }))

        self.assertEqual(node, Node.objects.get(pk=node.pk))
