from __future__ import unicode_literals

import io
import os
import re
import sys
import tempfile
import unittest

from django import forms
from django.contrib.auth.models import User
from django.db.models import Q, Manager
from django.db.models.query_utils import DeferredAttribute
from django.db.utils import IntegrityError
from django.apps import apps
from django.forms.models import modelform_factory
from django.template import Template, TemplateSyntaxError, Context
from django.test import RequestFactory, TestCase
from django.utils.six import string_types, PY3, b, assertRaisesRegex
from django.contrib.admin.views.main import ChangeList
from django.contrib.admin import ModelAdmin, site
from mptt.admin import TreeRelatedFieldListFilter

try:
    from mock_django import mock_signal_receiver
except ImportError:
    mock_signal_receiver = None

from mptt.admin import JS
from mptt.exceptions import InvalidMove
from mptt.forms import (
    MPTTAdminForm, TreeNodeChoiceField, TreeNodeMultipleChoiceField,
    MoveNodeForm)
from mptt.models import MPTTModel
from mptt.managers import TreeManager
from mptt.signals import node_moved
from mptt.templatetags.mptt_tags import cache_tree_children
from mptt.utils import print_debug_info

from myapp.models import (
    Category, Item, Genre, CustomPKName, SingleProxyModel,
    ConcreteModel, OrderedInsertion, AutoNowDateFieldModel, Person,
    CustomTreeQueryset, Node, ReferencingModel, CustomTreeManager, Book,
    UUIDNode, UniqueCodePerParentModel)


def get_tree_details(nodes):
    """
    Creates pertinent tree details for the given list of nodes.
    The fields are:
        id  parent_id  tree_id  level  left  right
    """
    if hasattr(nodes, 'order_by'):
        nodes = list(nodes.order_by('tree_id', 'lft', 'pk'))
    nodes = list(nodes)
    return '\n'.join([
        '%s %s %s %s %s %s' % (
            n.pk,
            n.parent_id or '-',
            n.tree_id,
            n.level,
            n.lft,
            n.rght,
        ) for n in nodes
    ])

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
                else:
                    temp.write(text)

                temp.flush()

                import doctest
                doctest.testfile(
                    temp.name,
                    module_relative=False,
                    optionflags=doctest.IGNORE_EXCEPTION_DETAIL | doctest.ELLIPSIS,
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
        self.assertTreeEqual([action], '1 9 1 1 6 21')
        self.assertTreeEqual([rpg], '9 - 1 0 1 22')
        self.assertTreeEqual(Genre.objects.all(), """
            9 - 1 0 1 22
            10 9 1 1 2 3
            11 9 1 1 4 5
            1 9 1 1 6 21
            2 1 1 2 7 14
            3 2 1 3 8 9
            4 2 1 3 10 11
            5 2 1 3 12 13
            6 1 1 2 15 20
            7 6 1 3 16 17
            8 6 1 3 18 19
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


class ConcurrencyTestCase(TreeTestCase):

    """
    Test that tree structure remains intact when saving nodes (without setting new parent) after
    tree structure has been changed.
    """

    def setUp(self):
        fruit = ConcreteModel.objects.create(name="Fruit")
        vegie = ConcreteModel.objects.create(name="Vegie")
        ConcreteModel.objects.create(name="Apple", parent=fruit)
        ConcreteModel.objects.create(name="Pear", parent=fruit)
        ConcreteModel.objects.create(name="Tomato", parent=vegie)
        ConcreteModel.objects.create(name="Carrot", parent=vegie)

        # sanity check
        self.assertTreeEqual(ConcreteModel.objects.all(), """
            1 - 1 0 1 6
            3 1 1 1 2 3
            4 1 1 1 4 5
            2 - 2 0 1 6
            5 2 2 1 2 3
            6 2 2 1 4 5
        """)

    def _modify_tree(self):
        fruit = ConcreteModel.objects.get(name="Fruit")
        vegie = ConcreteModel.objects.get(name="Vegie")
        vegie.move_to(fruit)

    def _assert_modified_tree_state(self):
        carrot = ConcreteModel.objects.get(id=6)
        self.assertTreeEqual([carrot], '6 2 1 2 5 6')
        self.assertTreeEqual(ConcreteModel.objects.all(), """
            1 - 1 0 1 12
            2 1 1 1 2 7
            5 2 1 2 3 4
            6 2 1 2 5 6
            3 1 1 1 8 9
            4 1 1 1 10 11
        """)

    def test_node_save_after_tree_restructuring(self):
        carrot = ConcreteModel.objects.get(id=6)

        self._modify_tree()

        carrot.name = "Purple carrot"
        carrot.save()

        self._assert_modified_tree_state()

    def test_node_save_after_tree_restructuring_with_update_fields(self):
        """
        Test that model is saved properly when passing update_fields
        """
        carrot = ConcreteModel.objects.get(id=6)

        self._modify_tree()

        # update with kwargs
        carrot.name = "Won't change"
        carrot.ghosts = "Will get updated"
        carrot.save(update_fields=["ghosts"])

        self._assert_modified_tree_state()

        updated_carrot = ConcreteModel.objects.get(id=6)

        self.assertEqual(updated_carrot.ghosts, carrot.ghosts)
        self.assertNotEqual(updated_carrot.name, carrot.name)

        carrot.name = "Will change"
        carrot.ghosts = "Will not be updated"
        carrot.save(update_fields=["name"])

        updated_carrot = ConcreteModel.objects.get(id=6)
        self.assertNotEqual(updated_carrot.ghosts, carrot.ghosts)
        self.assertEqual(updated_carrot.name, carrot.name)


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
            12 - 2 0 1 2
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

    def test_insert_child(self):
        with self.assertNumQueries(5):
            # 1. refresh parent (without "parent"??)
            # 2. manage space
            # 3. refresh parent again
            # 4. insert
            # 5. refresh our own mptt attributes
            ConcreteModel.objects.create(name="e", parent=self.d)

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
            # 1. select MAX tree_id
            # 2. insert
            # 3. mptt refresh
            ConcreteModel.objects.create(name="e")

        self.assertTreeEqual(ConcreteModel.objects.all(), """
            1 - 1 0 1 6
            2 1 1 1 2 3
            3 1 1 1 4 5
            4 - 2 0 1 2
            5 - 3 0 1 2
            6 - 4 0 1 2
        """)

    def test_move_node_same_tree(self):
        with self.assertNumQueries(5):
            # 1. update mptt
            # 2. refresh mptt pk3
            # 3. refresh mptt pk2
            # 4. update
            # 5. refresh mptt pk3
            self.c.parent = self.b
            self.c.save()

        self.assertTreeEqual(ConcreteModel.objects.all(), """
            1 - 1 0 1 6
            2 1 1 1 2 5
            3 2 1 2 3 4
            4 - 2 0 1 2
            5 - 3 0 1 2
        """)

    def test_move_node_different_tree(self):
        with self.assertNumQueries(7):
            # 1. update mptt (create space)
            # 2. update mptt (close space)
            # 3. update mptt (tree_id)
            # 4. refresh mptt pk4
            # 5. refresh mptt pk3
            # 6. update
            # 7. refresh mptt pk4
            self.d.parent = self.c
            self.d.save()

        self.assertTreeEqual(ConcreteModel.objects.all(), """
            1 - 1 0 1 8
            2 1 1 1 2 3
            3 1 1 1 4 7
            4 3 1 2 5 6
            5 - 2 0 1 2
        """)

    def test_move_node_to_root(self):
        with self.assertNumQueries(4):
            # 1. create tree space
            # 2. update mptt (move)
            # 3. update
            # 4. refresh mptt
            self.c.parent = None
            self.c.save()

        self.assertTreeEqual(ConcreteModel.objects.all(), """
            1 - 1 0 1 4
            2 1 1 1 2 3
            4 - 2 0 1 2
            5 - 3 0 1 2
            3 - 4 0 1 2
        """)

    def test_move_root_to_child(self):
        with self.assertNumQueries(7):
            # 1. update mptt (create space)
            # 2. update mptt (close space)
            # 3. update mptt (tree_id)
            # 4. refresh mptt pk4
            # 5. refresh mptt pk3
            # 6. update
            # 7. refresh mptt pk4
            self.d.parent = self.c
            self.d.save()

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
        with self.assertNumQueries(7):
            # - find insertion point
            # - select parent
            # - create space
            # - refresh mptt pk1
            # - refresh mptt pk1 (FIXME? twice)
            # - insert
            # - refresh mptt pk6
            OrderedInsertion.objects.create(name="dd", parent=self.c)

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
            # - find insertion point
            # - update tree_id
            # - insert
            # - refresh mptt
            with OrderedInsertion.objects.delay_mptt_updates():
                OrderedInsertion.objects.create(name="ee")

        self.assertTreeEqual(OrderedInsertion.objects.all(), """
            1 - 1 0 1 6
            2 1 1 1 2 3
            3 1 1 1 4 5
            6 - 2 0 1 2
            4 - 3 0 1 2
            5 - 4 0 1 2
        """)

    def test_move_node_same_tree(self):
        with self.assertNumQueries(6):
            # - find insertion point
            # - select parent
            # - manage space
            # - refresh mptt pk3
            # - update
            # - refresh mptt pk3
            self.e.name = 'before d'
            self.e.save()

        self.assertTreeEqual(OrderedInsertion.objects.all(), """
            1 - 1 0 1 6
            3 1 1 1 2 3
            2 1 1 1 4 5
            4 - 2 0 1 2
            5 - 3 0 1 2
        """)

    def test_move_node_different_tree(self):
        with self.assertNumQueries(9):
            # - find insertion point
            # - select parent
            # - create space
            # - remove space
            # - update tree_id
            # - refresh mptt pk4
            # - refresh mptt pk1
            # - update
            # - refresh mptt pk4
            self.f.parent = self.c
            self.f.name = 'dd'
            self.f.save()

        self.assertTreeEqual(OrderedInsertion.objects.all(), """
            1 - 1 0 1 8
            2 1 1 1 2 3
            4 1 1 1 4 5
            3 1 1 1 6 7
            5 - 2 0 1 2
        """)

    def test_move_node_to_root(self):
        with self.assertNumQueries(5):
            # - find insertion point
            # - update tree_id
            # - manage space
            # - update
            # - refresh mptt
            self.e.parent = None
            self.e.save()

        self.assertTreeEqual(OrderedInsertion.objects.all(), """
            1 - 1 0 1 4
            2 1 1 1 2 3
            3 - 2 0 1 2
            4 - 3 0 1 2
            5 - 4 0 1 2
        """)

    def test_move_root_to_child(self):
        with self.assertNumQueries(7):
            # 1. create space
            # 2. close space
            # 3. update tree_id
            # 4. refresh mptt
            # 5. refresh mptt
            # 6. update
            # 7. refresh mptt
            self.f.parent = self.e
            self.f.save()

        self.assertTreeEqual(OrderedInsertion.objects.all(), """
            1 - 1 0 1 8
            2 1 1 1 2 3
            3 1 1 1 4 7
            4 3 1 2 5 6
            5 - 2 0 1 2
        """)


class ManagerTests(TreeTestCase):
    fixtures = ['categories.json',
                'genres.json',
                'persons.json']

    def test_all_managers_are_different(self):
        # all tree managers should be different. otherwise, possible infinite recursion.
        seen = {}
        for model in apps.get_models():
            if not issubclass(model, MPTTModel):
                continue
            tm = model._default_manager
            if id(tm) in seen:
                self.fail(
                    "Tree managers for %s and %s are the same manager"
                    % (model.__name__, seen[id(tm)].__name__))
            seen[id(tm)] = model

    def test_all_managers_have_correct_model(self):
        # all tree managers should have the correct model.
        for model in apps.get_models():
            if not issubclass(model, MPTTModel):
                continue
            self.assertEqual(model._default_manager.model, model)

    def test_proxy_custom_manager(self):
        self.assertIsInstance(SingleProxyModel._default_manager, CustomTreeManager)
        self.assertIsInstance(SingleProxyModel.objects, CustomTreeManager)
        self.assertIsInstance(SingleProxyModel._base_manager, Manager)

    def test_get_queryset_descendants(self):
        def get_desc_names(qs, include_self=False):
            desc = qs.model.objects.get_queryset_descendants(
                qs, include_self=include_self)
            return list(desc.values_list('name', flat=True).order_by('name'))

        qs = Category.objects.filter(Q(name='Nintendo Wii') | Q(name='PlayStation 3'))

        self.assertEqual(
            get_desc_names(qs),
            ['Games', 'Games',
             'Hardware & Accessories', 'Hardware & Accessories'],
        )

        self.assertEqual(
            get_desc_names(qs, include_self=True),
            ['Games', 'Games', 'Hardware & Accessories',
             'Hardware & Accessories', 'Nintendo Wii', 'PlayStation 3']
        )

        qs = Genre.objects.filter(parent=None)

        self.assertEqual(
            get_desc_names(qs),
            ['2D Platformer', '3D Platformer', '4D Platformer',
             'Action RPG', 'Horizontal Scrolling Shootemup', 'Platformer',
             'Shootemup', 'Tactical RPG', 'Vertical Scrolling Shootemup']
        )

        self.assertEqual(
            get_desc_names(qs, include_self=True),
            ['2D Platformer', '3D Platformer', '4D Platformer',
             'Action', 'Action RPG', 'Horizontal Scrolling Shootemup',
             'Platformer', 'Role-playing Game', 'Shootemup', 'Tactical RPG',
             'Vertical Scrolling Shootemup']
        )

    def _get_anc_names(self, qs, include_self=False):
        anc = qs.model.objects.get_queryset_ancestors(
            qs, include_self=include_self)
        return list(anc.values_list('name', flat=True).order_by('name'))

    def test_get_queryset_ancestors(self):
        qs = Category.objects.filter(Q(name='Nintendo Wii') | Q(name='PlayStation 3'))

        self.assertEqual(
            self._get_anc_names(qs),
            ['PC & Video Games']
        )

        self.assertEqual(
            self._get_anc_names(qs, include_self=True),
            ['Nintendo Wii', 'PC & Video Games', 'PlayStation 3']
        )

        qs = Genre.objects.filter(parent=None)
        self.assertEqual(self._get_anc_names(qs), [])
        self.assertEqual(
            self._get_anc_names(qs, include_self=True),
            ['Action', 'Role-playing Game'])

    def test_get_queryset_ancestors_regression_379(self):
        # https://github.com/django-mptt/django-mptt/issues/379
        qs = Genre.objects.all()
        self.assertEqual(
            self._get_anc_names(qs, include_self=True),
            list(Genre.objects.values_list('name', flat=True).order_by('name')))

    def test_custom_querysets(self):
        """
        Test that a custom manager also provides custom querysets.
        """

        self.assertTrue(isinstance(Person.objects.all(), CustomTreeQueryset))
        self.assertTrue(isinstance(Person.objects.all()[0].get_children(), CustomTreeQueryset))
        self.assertTrue(hasattr(Person.objects.none(), 'custom_method'))

        # Check that empty querysets get custom methods
        self.assertTrue(hasattr(Person.objects.all()[0].get_children().none(), 'custom_method'))

        self.assertEqual(
            type(Person.objects.all()),
            type(Person.objects.root_nodes())
        )

    def test_manager_from_custom_queryset(self):
        """
        Test that a manager created from a custom queryset works.
        Regression test for #378.
        """
        TreeManager.from_queryset(CustomTreeQueryset)().contribute_to_class(Genre, 'my_manager')

        self.assertIsInstance(Genre.my_manager.get_queryset(), CustomTreeQueryset)

    def test_num_queries_on_get_queryset_descendants(self):
        """
        Test the number of queries to access descendants
        is not O(n).
        At the moment it is O(1)+1.
        Ideally we should aim for O(1).
        """
        with self.assertNumQueries(2):
            qs = Category.objects.get_queryset_descendants(
                Category.objects.all(), include_self=True)
            self.assertEqual(len(qs), 10)


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

    def test_cache_tree_children_with_invalid_ordering(self):
        """
        Ensures that ``cache_tree_children`` fails with a ``ValueError`` when
        passed a list which is not in tree order.
        """

        with self.assertNumQueries(1):
            with self.assertRaises(ValueError):
                cache_tree_children(list(Category.objects.order_by('-id')))

        # Passing a list with correct ordering should work, though.
        with self.assertNumQueries(1):
            cache_tree_children(list(Category.objects.all()))

        # The exact ordering tuple doesn't matter, long as the nodes end up in depth-first order.
        cache_tree_children(Category.objects.order_by('tree_id', 'lft', 'name'))
        cache_tree_children(Category.objects.filter(tree_id=1).order_by('lft'))


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

    def test_parsing_fail(self):
        self.assertRaises(
            TemplateSyntaxError,
            Template,
            '{% load mptt_tags %}{% recursetree %}{% endrecursetree %}')

    def test_cached_ancestors(self):
        template = Template('''
            {% load mptt_tags %}
            {% recursetree nodes %}
                {{ node.get_ancestors|join:" > " }} {{ node.name }}
                {% if not node.is_leaf_node %}
                    {{ children }}
                {% endif %}
            {% endrecursetree %}
        ''')
        with self.assertNumQueries(1):
            qs = Category.objects.all()
            template.render(Context({'nodes': qs}))


class TreeInfoTestCase(TreeTestCase):
    fixtures = ['genres.json']
    template = re.sub(r'(?m)^[\s]+', '', '''
        {% load mptt_tags %}
        {% for node, structure in nodes|tree_info %}
        {% if structure.new_level %}<ul><li>{% else %}</li><li>{% endif %}
        {{ node.pk }}
        {% for level in structure.closed_levels %}</li></ul>{% endfor %}
        {% endfor %}''')

    template_with_ancestors = re.sub(r'(?m)^[\s]+', '', '''
        {% load mptt_tags %}
        {% for node, structure in nodes|tree_info:"ancestors" %}
        {% if structure.new_level %}<ul><li>{% else %}</li><li>{% endif %}
        {{ node.pk }}
        {% for ancestor in structure.ancestors %}
            {% if forloop.first %}A:{% endif %}
            {{ ancestor }}{% if not forloop.last %},{% endif %}
        {% endfor %}
        {% for level in structure.closed_levels %}</li></ul>{% endfor %}
        {% endfor %}''')

    def test_tree_info_html(self):
        html = Template(self.template).render(Context({
            'nodes': Genre.objects.all(),
        })).replace('\n', '')

        self.assertEqual(
            html,
            '<ul><li>1<ul><li>2<ul><li>3</li><li>4</li><li>5</li></ul></li>'
            '<li>6<ul><li>7</li><li>8</li></ul></li></ul></li><li>9<ul>'
            '<li>10</li><li>11</li></ul></li></ul>')

        html = Template(self.template).render(Context({
            'nodes': Genre.objects.filter(
                level__gte=1,
                level__lte=2,
            ),
        })).replace('\n', '')

        self.assertEqual(
            html,
            '<ul><li>2<ul><li>3</li><li>4</li><li>5</li></ul></li><li>6<ul>'
            '<li>7</li><li>8</li></ul></li><li>10</li><li>11</li></ul>')

        html = Template(self.template_with_ancestors).render(Context({
            'nodes': Genre.objects.filter(
                level__gte=1,
                level__lte=2,
            ),
        })).replace('\n', '')

        self.assertEqual(
            html,
            '<ul><li>2<ul><li>3A:Platformer</li><li>4A:Platformer</li>'
            '<li>5A:Platformer</li></ul></li><li>6<ul><li>7A:Shootemup</li>'
            '<li>8A:Shootemup</li></ul></li><li>10</li><li>11</li></ul>')


class FullTreeTestCase(TreeTestCase):
    fixtures = ['genres.json']
    template = re.sub(r'(?m)^[\s]+', '', '''
        {% load mptt_tags %}
        {% full_tree_for_model myapp.Genre as tree %}
        {% for node in tree %}{{ node.pk }},{% endfor %}
        ''')

    def test_full_tree_html(self):
        html = Template(self.template).render(Context({})).replace('\n', '')
        self.assertEqual(
            html,
            '1,2,3,4,5,6,7,8,9,10,11,')


class DrilldownTreeTestCase(TreeTestCase):
    fixtures = ['genres.json']
    template = re.sub(r'(?m)^[\s]+', '', '''
        {% load mptt_tags %}
        {% drilldown_tree_for_node node as tree count myapp.Game.genre in game_count %}
        {% for n in tree %}
            {% ifequal n node %}[{% endifequal %}
            {{ n.pk }}:{{ n.game_count }}
            {% ifequal n node %}]{% endifequal %}{% if not forloop.last %},{% endif %}
        {% endfor %}
        ''')

    def render_for_node(self, pk, cumulative=False, m2m=False):
        template = self.template
        if cumulative:
            template = template.replace(' count ', ' cumulative count ')
        if m2m:
            template = template.replace('Game.genre', 'Game.genres_m2m')

        return Template(template).render(Context({
            'node': Genre.objects.get(pk=pk),
        })).replace('\n', '')

    def test_drilldown_html(self):
        for idx, genre in enumerate(Genre.objects.all()):
            for i in range(idx):
                game = genre.game_set.create(name='Game %s' % i)
                genre.games_m2m.add(game)

        self.assertEqual(
            self.render_for_node(1),
            '[1:],2:1,6:5')
        self.assertEqual(
            self.render_for_node(2),
            '1:,[2:],3:2,4:3,5:4')

        self.assertEqual(
            self.render_for_node(1, cumulative=True),
            '[1:],2:10,6:18')
        self.assertEqual(
            self.render_for_node(2, cumulative=True),
            '1:,[2:],3:2,4:3,5:4')

        self.assertEqual(
            self.render_for_node(1, m2m=True),
            '[1:],2:1,6:5')
        self.assertEqual(
            self.render_for_node(2, m2m=True),
            '1:,[2:],3:2,4:3,5:4')

        self.assertEqual(
            self.render_for_node(1, cumulative=True, m2m=True),
            '[1:],2:10,6:18')
        self.assertEqual(
            self.render_for_node(2, cumulative=True, m2m=True),
            '1:,[2:],3:2,4:3,5:4')


class TestAutoNowDateFieldModel(TreeTestCase):
    # https://github.com/django-mptt/django-mptt/issues/175

    def test_save_auto_now_date_field_model(self):
        a = AutoNowDateFieldModel()
        a.save()


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
        self.assertTrue(CategoryForm(instance=c))

        # Test that the parent field is properly limited. (queryset)
        form = CategoryForm({
            'name': c.name,
            'parent': c.children.all()[0].pk,
        }, instance=c)
        self.assertFalse(form.is_valid())
        self.assertIn(
            'Select a valid choice',
            '%s' % form.errors)

        # Test that even though we remove the field queryset limit,
        # validation still fails.
        form = CategoryForm({
            'name': c.name,
            'parent': c.children.all()[0].pk,
        }, instance=c)
        form.fields['parent'].queryset = Category.objects.all()
        self.assertFalse(form.is_valid())
        self.assertIn(
            'Invalid parent',
            '%s' % form.errors)

    def test_field_types(self):
        ReferencingModelForm = modelform_factory(
            ReferencingModel,
            exclude=('id',))

        form = ReferencingModelForm()

        # Also check whether we have the correct form field type
        self.assertTrue(isinstance(
            form.fields['fk'],
            TreeNodeChoiceField))
        self.assertTrue(isinstance(
            form.fields['one'],
            TreeNodeChoiceField))
        self.assertTrue(isinstance(
            form.fields['m2m'],
            TreeNodeMultipleChoiceField))

    def test_movenodeform(self):
        c = Category.objects.get(pk=2)
        form = MoveNodeForm(c, {
            'target': '5',
            'position': 'first-child',
        })
        self.assertTrue(form.is_valid())
        form.save()

        self.assertTreeEqual(Category.objects.all(), '''
            1 - 1 0 1 20
            5 1 1 1 2 13
            2 5 1 2 3 8
            3 2 1 3 4 5
            4 2 1 3 6 7
            6 5 1 2 9 10
            7 5 1 2 11 12
            8 1 1 1 14 19
            9 8 1 2 15 16
            10 8 1 2 17 18
        ''')


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


class TestDebugInfo(TreeTestCase):
    fixtures = ['categories.json']

    def test_debug_info(self):  # Currently fails either on PY2 or PY3.
        stream_type = io.StringIO if PY3 else io.BytesIO
        with stream_type() as out:
            print_debug_info(Category.objects.all(), file=out)
            output = out.getvalue()

        self.assertIn('1,0,,1,1,20', output)


class AdminBatch(TreeTestCase):
    fixtures = ['categories.json']

    def test_changelist(self):
        user = User.objects.create_superuser('admin', 'test@example.com', 'p')

        self.client.login(username=user.username, password='p')

        response = self.client.get('/admin/myapp/category/')
        self.assertContains(
            response,
            'name="_selected_action"',
            10)

        self.assertEqual(
            response.context['cl'].result_list.query.order_by[:2],
            ['tree_id', 'lft'])

        data = {
            'action': 'delete_selected',
            '_selected_action': ['5', '8', '9'],
        }
        response = self.client.post('/admin/myapp/category/', data)
        self.assertContains(response, 'value="Yes, I\'m sure"', 1)

        data['post'] = 'yes'
        response = self.client.post('/admin/myapp/category/', data)

        self.assertRedirects(
            response,
            '/admin/myapp/category/')

        self.assertEqual(Category.objects.count(), 4)

        # Batch deletion has not clobbered MPTT values, because our method
        # delete_selected_tree has been used.
        self.assertTreeEqual(Category.objects.all(), '''
            1 - 1 0 1 8
            2 1 1 1 2 7
            3 2 1 2 3 4
            4 2 1 2 5 6
        ''')


class TestUnsaved(TreeTestCase):

    def test_unsaved(self):
        for method in [
            'get_ancestors',
            'get_family',
            'get_children',
            'get_descendants',
            'get_leafnodes',
            'get_next_sibling',
            'get_previous_sibling',
            'get_root',
            'get_siblings',
        ]:
            assertRaisesRegex(
                self,
                ValueError,
                'Cannot call %s on unsaved Genre instances' % method,
                getattr(Genre(), method))


class QuerySetTests(TreeTestCase):
    fixtures = ['categories.json']

    def test_get_ancestors(self):
        self.assertEqual(
            [
                c.pk for c in
                Category.objects.get(name="Nintendo Wii").get_ancestors(include_self=False)],
            [
                c.pk for c in
                Category.objects.filter(name="Nintendo Wii").get_ancestors(include_self=False)],
        )
        self.assertEqual(
            [
                c.pk for c in
                Category.objects.get(name="Nintendo Wii").get_ancestors(include_self=True)],
            [
                c.pk for c in
                Category.objects.filter(name="Nintendo Wii").get_ancestors(include_self=True)],
        )

    def test_get_descendants(self):
        self.assertEqual(
            [
                c.pk for c in
                Category.objects.get(name="Nintendo Wii").get_descendants(include_self=False)],
            [
                c.pk for c in
                Category.objects.filter(name="Nintendo Wii").get_descendants(include_self=False)],
        )
        self.assertEqual(
            [
                c.pk for c in
                Category.objects.get(name="Nintendo Wii").get_descendants(include_self=True)],
            [
                c.pk for c in
                Category.objects.filter(name="Nintendo Wii").get_descendants(include_self=True)],
        )


class TreeManagerTestCase(TreeTestCase):

    fixtures = ['categories.json', 'items.json']

    def test_add_related_count_with_fk_to_natural_key(self):
        # Regression test for #284
        queryset = Category.objects.filter(name='Xbox 360').order_by('id')

        # Test using FK that doesn't point to a primary key
        for c in Category.objects.add_related_count(
                queryset, Item, 'category_fk', 'item_count', cumulative=False):
            self.assertEqual(c.item_count, c.items_by_pk.count())

        # Also works when using the FK that *does* point to a primary key
        for c in Category.objects.add_related_count(
                queryset, Item, 'category_pk', 'item_count', cumulative=False):
            self.assertEqual(c.item_count, c.items_by_pk.count())


class TestOrderedInsertionBFS(TreeTestCase):

    def test_insert_ordered_DFS_backwards_root_nodes(self):
        rock = OrderedInsertion.objects.create(name="Rock")

        OrderedInsertion.objects.create(name="Led Zeppelin", parent=rock)

        OrderedInsertion.objects.create(name="Classical")

        self.assertTreeEqual(OrderedInsertion.objects.all(), """
            3 - 1 0 1 2
            1 - 2 0 1 4
            2 1 2 1 2 3
        """)

    def test_insert_ordered_BFS_backwards_root_nodes(self):
        rock = OrderedInsertion.objects.create(name="Rock")

        self.assertTreeEqual(OrderedInsertion.objects.all(), """
            1 - 1 0 1 2
        """)

        OrderedInsertion.objects.create(name="Classical")

        self.assertTreeEqual(OrderedInsertion.objects.all(), """
            2 - 1 0 1 2
            1 - 2 0 1 2
        """)

        # This tends to fail if it uses `rock.tree_id`, which is 1, although
        # in the database Rock's tree_id has been updated to 2.

        OrderedInsertion.objects.create(name="Led Zeppelin", parent=rock)
        self.assertTreeEqual(OrderedInsertion.objects.all(), """
            2 - 1 0 1 2
            1 - 2 0 1 4
            3 1 2 1 2 3
        """)

    def test_insert_ordered_DFS_backwards_nonroot_nodes(self):
        music = OrderedInsertion.objects.create(name='music')
        rock = OrderedInsertion.objects.create(name="Rock", parent=music)

        OrderedInsertion.objects.create(name="Led Zeppelin", parent=rock)

        OrderedInsertion.objects.create(name="Classical", parent=music)

        self.assertTreeEqual(OrderedInsertion.objects.all(), """
            1 - 1 0 1 8
            4 1 1 1 2 3
            2 1 1 1 4 7
            3 2 1 2 5 6
        """)

    def test_insert_ordered_BFS_backwards_nonroot_nodes(self):
        music = OrderedInsertion.objects.create(name='music')
        rock = OrderedInsertion.objects.create(name="Rock", parent=music)
        OrderedInsertion.objects.create(name="Classical", parent=music)

        self.assertTreeEqual(OrderedInsertion.objects.all(), """
            1 - 1 0 1 6
            3 1 1 1 2 3
            2 1 1 1 4 5
        """)

        OrderedInsertion.objects.create(name="Led Zeppelin", parent=rock)

        self.assertTreeEqual(OrderedInsertion.objects.all(), """
            1 - 1 0 1 8
            3 1 1 1 2 3
            2 1 1 1 4 7
            4 2 1 2 5 6
        """)


class CacheChildrenTestCase(TreeTestCase):

    """
    Tests that the queryset function `get_cached_trees` results in a minimum
    number of database queries.
    """
    fixtures = ['genres.json']

    def test_genre_iter(self):
        """
        Test a query with two root nodes.
        """
        with self.assertNumQueries(1):
            root_nodes = Genre.objects.all().get_cached_trees()

        # `get_cached_trees` should only return the root nodes
        self.assertEqual(len(root_nodes), 2)

        # Getting the children of each node should not result in db hits.
        with self.assertNumQueries(0):
            for genre in root_nodes:
                self.assertIsInstance(genre, Genre)
                for child in genre.get_children():
                    self.assertIsInstance(child, Genre)
                    for child2 in child.get_children():
                        self.assertIsInstance(child2, Genre)


@unittest.skipUnless(mock_signal_receiver, "Signals tests require mock_django installed")
class Signals(TestCase):
    fixtures = ['categories.json']

    def setUp(self):
        self.signal = node_moved
        self.wii = Category.objects.get(pk=2)
        self.ps3 = Category.objects.get(pk=8)

    def test_signal_should_not_be_sent_when_parent_hasnt_changed(self):
        with mock_signal_receiver(self.signal, sender=Category) as receiver:
            self.wii.name = 'Woo'
            self.wii.save()

            self.assertEqual(receiver.call_count, 0)

    def test_signal_should_not_be_sent_when_model_created(self):
        with mock_signal_receiver(self.signal, sender=Category) as receiver:
            Category.objects.create(name='Descriptive name')

            self.assertEqual(receiver.call_count, 0)

    def test_move_by_using_move_to_should_send_signal(self):
        with mock_signal_receiver(self.signal, sender=Category) as receiver:
            self.wii.move_to(self.ps3)

            receiver.assert_called_once_with(
                instance=self.wii,
                signal=self.signal,
                target=self.ps3,
                sender=Category,
                position='first-child'
            )

    def test_move_by_changing_parent_should_send_signal(self):
        '''position is not set when sent from save(). I assume it
        would be the default(first-child) but didn't feel comfortable
        setting it.
        '''
        with mock_signal_receiver(self.signal, sender=Category) as receiver:
            self.wii.parent = self.ps3
            self.wii.save()

            receiver.assert_called_once_with(
                instance=self.wii,
                signal=self.signal,
                target=self.ps3,
                sender=Category
            )


class DeferredAttributeTests(TreeTestCase):

    """
    Regression tests for #176 and #424
    """

    def setUp(self):
        OrderedInsertion.objects.create(name="a")

    def test_deferred_order_insertion_by(self):
        qs = OrderedInsertion.objects.defer('name')
        with self.assertNumQueries(1):
            nodes = list(qs)
        with self.assertNumQueries(0):
            self.assertTreeEqual(nodes, '''
                1 - 1 0 1 2
            ''')

    def test_deferred_cached_field_undeferred(self):
        obj = OrderedInsertion.objects.defer('name').get()
        self.assertEqual(obj._mptt_cached_fields['name'], DeferredAttribute)

        with self.assertNumQueries(1):
            obj.name
        with self.assertNumQueries(7):  # XXX previously 3 queries
            # does a node move, since the order_insertion_by field changed
            obj.save()

        self.assertEqual(obj._mptt_cached_fields['name'], 'a')

    def test_deferred_cached_field_change(self):
        obj = OrderedInsertion.objects.defer('name').get()
        self.assertEqual(obj._mptt_cached_fields['name'], DeferredAttribute)

        with self.assertNumQueries(0):
            obj.name = 'b'

        with self.assertNumQueries(7):  # XXX previously 3 queries
            # does a node move, since the order_insertion_by field changed
            obj.save()

        self.assertEqual(obj._mptt_cached_fields['name'], 'b')


class DraggableMPTTAdminTestCase(TreeTestCase):

    def setUp(self):
        self.user = User.objects.create_superuser(
            'admin', 'test@example.com', 'p')
        self.client.login(username=self.user.username, password='p')

    def test_changelist(self):
        p1 = Person.objects.create(name='Franz')
        p2 = Person.objects.create(name='Fritz')
        p3 = Person.objects.create(name='Hans')

        self.assertNotEqual(p1.tree_id, p2.tree_id)

        self.assertTreeEqual(Person.objects.all(), '''
        1 - 1 0 1 2
        2 - 2 0 1 2
        3 - 3 0 1 2
        ''')

        response = self.client.get('/admin/myapp/person/')
        self.assertContains(response, 'class="drag-handle"', 3)
        self.assertContains(response, 'style="text-indent:0px"', 3)
        self.assertContains(
            response,
            'javascript" src="/static/mptt/draggable-admin.js"'
            ' data-context="{&quot;')
        self.assertContains(
            response,
            '}" id="draggable-admin-context"></script>')

        response = self.client.post(
            '/admin/myapp/person/',
            {
                'cmd': 'move_node',
                'cut_item': p1.pk,
                'pasted_on': p2.pk,
                'position': 'last-child',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200)

        p1.refresh_from_db()
        p2.refresh_from_db()

        self.assertEqual(p1.parent, p2)

        self.assertTreeEqual(Person.objects.all(), """
            2 - 1 0 1 4
            1 2 1 1 2 3
            3 - 2 0 1 2
            """)

        response = self.client.get('/admin/myapp/person/')
        self.assertContains(response, 'style="text-indent:0px"', 2)
        self.assertContains(response, 'style="text-indent:20px"', 1)

        response = self.client.post(
            '/admin/myapp/person/',
            {
                'cmd': 'move_node',
                'cut_item': p3.pk,
                'pasted_on': p1.pk,
                'position': 'left',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200)

        self.assertTreeEqual(Person.objects.all(), """
            2 - 1 0 1 6
            3 2 1 1 2 3
            1 2 1 1 4 5
            """)

        response = self.client.post('/admin/myapp/person/', {
            'action': 'delete_selected',
            '_selected_action': [1],
        })
        self.assertContains(response, 'Are you sure?')
        response = self.client.post('/admin/myapp/person/', {
            'action': 'delete_selected',
            '_selected_action': [1],
            'post': 'yes',
        })

        self.assertRedirects(response, '/admin/myapp/person/')

        self.assertTreeEqual(Person.objects.all(), """
            2 - 1 0 1 4
            3 2 1 1 2 3
            """)

    def test_js(self):
        media = forms.Media()
        media.add_js([
            JS('asset1.js', {}),
            JS('asset2.js', {'id': 'something', 'answer': '"42"'}),
        ])

        # We can test the exact representation since forms.Media has been
        # really stable for a long time, and JS() uses flatatt which
        # alphabetically sorts its attributes.
        self.assertEqual(
            '%s' % media,
            '<script type="text/javascript" src="/static/asset1.js"></script>\n'
            '<script type="text/javascript" src="/static/asset2.js"'
            ' answer="&quot;42&quot;" id="something"></script>'
        )


class BookAdmin(ModelAdmin):
    list_filter = (
        ('fk', TreeRelatedFieldListFilter),
        ('m2m', TreeRelatedFieldListFilter),
    )
    ordering = ('id',)


class CategoryAdmin(ModelAdmin):
    list_filter = (
        ('books_fk', TreeRelatedFieldListFilter),
        ('books_m2m', TreeRelatedFieldListFilter),
    )
    ordering = ('id',)


class ListFiltersTests(TestCase):

    def setUp(self):
        self.request_factory = RequestFactory()

        self.parent_category = Category.objects.create(name='Parent category')
        self.child_category1 = Category.objects.create(name='Child category1',
                                                       parent=self.parent_category)
        self.child_category2 = Category.objects.create(name='Child category2',
                                                       parent=self.parent_category)
        self.simple_category = Category.objects.create(name='Simple category')

        self.book1 = Book.objects.create(name='book1', fk=self.child_category1)
        self.book2 = Book.objects.create(name='book2', fk=self.parent_category, parent=self.book1)
        self.book3 = Book.objects.create(name='book3', fk=self.simple_category, parent=self.book1)
        self.book4 = Book.objects.create(name='book4')

        self.book1.m2m.add(self.child_category1)
        self.book2.m2m.add(self.parent_category)
        self.book3.m2m.add(self.simple_category)

    def get_changelist(self, request, model, modeladmin):
        return ChangeList(
            request, model, modeladmin.list_display,
            modeladmin.list_display_links, modeladmin.list_filter,
            modeladmin.date_hierarchy, modeladmin.search_fields,
            modeladmin.list_select_related, modeladmin.list_per_page,
            modeladmin.list_max_show_all, modeladmin.list_editable, modeladmin,
        )

    def test_treerelatedfieldlistfilter_foreignkey(self):
        modeladmin = BookAdmin(Book, site)

        request = self.request_factory.get('/')
        changelist = self.get_changelist(request, Book, modeladmin)

        # Make sure that all categories are present in the referencing model's list filter
        filterspec = changelist.get_filters(request)[0][0]
        expected = [
            (self.parent_category.pk, self.parent_category.name, ' style="padding-left:0px"'),
            (self.child_category1.pk, self.child_category1.name, ' style="padding-left:10px"'),
            (self.child_category2.pk, self.child_category2.name, ' style="padding-left:10px"'),
            (self.simple_category.pk, self.simple_category.name, ' style="padding-left:0px"'),
        ]
        self.assertEqual(sorted(filterspec.lookup_choices), sorted(expected))

        request = self.request_factory.get('/', {'fk__isnull': 'True'})
        changelist = self.get_changelist(request, Book, modeladmin)
        queryset = changelist.get_queryset(request)
        self.assertEqual(list(queryset), [self.book4])

        # Make sure the last choice is None and is selected
        filterspec = changelist.get_filters(request)[0][0]
        choices = list(filterspec.choices(changelist))
        self.assertEqual(choices[-1]['selected'], True)
        self.assertEqual(choices[-1]['query_string'], '?fk__isnull=True')

        # Make sure child's categories books included
        request = self.request_factory.get('/', {'fk__id__inhierarchy': self.parent_category.pk})
        changelist = self.get_changelist(request, Book, modeladmin)
        queryset = changelist.get_queryset(request)
        self.assertEqual((list(queryset)), [self.book1, self.book2])

        # Make sure filter for child category works as expected
        request = self.request_factory.get('/', {'fk__id__inhierarchy': self.child_category1.pk})
        changelist = self.get_changelist(request, Book, modeladmin)
        queryset = changelist.get_queryset(request)
        self.assertEqual((list(queryset)), [self.book1])

        # Make sure filter for empty category works as expected
        request = self.request_factory.get('/', {'fk__id__inhierarchy': self.child_category2.pk})
        changelist = self.get_changelist(request, Book, modeladmin)
        queryset = changelist.get_queryset(request)
        self.assertEqual(queryset.count(), 0)

        # Make sure filter for simple category with no hierarchy works as expected
        request = self.request_factory.get('/', {'fk__id__inhierarchy': self.simple_category.pk})
        changelist = self.get_changelist(request, Book, modeladmin)
        queryset = changelist.get_queryset(request)
        self.assertEqual((list(queryset)), [self.book3])

    def test_treerelatedfieldlistfilter_manytomany(self):
        modeladmin = BookAdmin(Book, site)

        request = self.request_factory.get('/')
        changelist = self.get_changelist(request, Book, modeladmin)

        # Make sure that all categories are present in the referencing model's list filter
        filterspec = changelist.get_filters(request)[0][1]
        expected = [
            (self.parent_category.pk, self.parent_category.name, ' style="padding-left:0px"'),
            (self.child_category1.pk, self.child_category1.name, ' style="padding-left:10px"'),
            (self.child_category2.pk, self.child_category2.name, ' style="padding-left:10px"'),
            (self.simple_category.pk, self.simple_category.name, ' style="padding-left:0px"'),

        ]
        self.assertEqual(sorted(filterspec.lookup_choices), sorted(expected))

        request = self.request_factory.get('/', {'m2m__isnull': 'True'})
        changelist = self.get_changelist(request, Book, modeladmin)

        # Make sure the correct queryset is returned
        queryset = changelist.get_queryset(request)
        self.assertEqual(list(queryset), [self.book4])

        # Make sure the last choice is None and is selected
        filterspec = changelist.get_filters(request)[0][1]
        choices = list(filterspec.choices(changelist))
        self.assertEqual(choices[-1]['selected'], True)
        self.assertEqual(choices[-1]['query_string'], '?m2m__isnull=True')

        # Make sure child's categories books included
        request = self.request_factory.get('/', {'m2m__id__inhierarchy': self.parent_category.pk})
        changelist = self.get_changelist(request, Book, modeladmin)
        queryset = changelist.get_queryset(request)
        self.assertEqual((list(queryset)), [self.book1, self.book2])

        # Make sure filter for child category works as expected
        request = self.request_factory.get('/', {'m2m__id__inhierarchy': self.child_category1.pk})
        changelist = self.get_changelist(request, Book, modeladmin)
        queryset = changelist.get_queryset(request)
        self.assertEqual((list(queryset)), [self.book1])

        # Make sure filter for empty category works as expected
        request = self.request_factory.get('/', {'fk__id__inhierarchy': self.child_category2.pk})
        changelist = self.get_changelist(request, Book, modeladmin)
        queryset = changelist.get_queryset(request)
        self.assertEqual(queryset.count(), 0)

        # Make sure filter for simple category with no hierarchy works as expected
        request = self.request_factory.get('/', {'m2m__id__inhierarchy': self.simple_category.pk})
        changelist = self.get_changelist(request, Book, modeladmin)
        queryset = changelist.get_queryset(request)
        self.assertEqual((list(queryset)), [self.book3])

    def test_treerelatedfieldlistfilter_reverse_relationships(self):
        modeladmin = CategoryAdmin(Category, site)

        # FK relationship -----
        request = self.request_factory.get('/', {'books_fk__isnull': 'True'})
        changelist = self.get_changelist(request, Category, modeladmin)

        # Make sure the correct queryset is returned
        queryset = changelist.get_queryset(request)
        self.assertEqual(list(queryset), [self.child_category2])

        # Make sure the last choice is None and is selected
        filterspec = changelist.get_filters(request)[0][0]
        choices = list(filterspec.choices(changelist))
        self.assertEqual(choices[-1]['selected'], True)
        self.assertEqual(choices[-1]['query_string'], '?books_fk__isnull=True')

        # Make sure child's books categories included
        request = self.request_factory.get('/', {'books_fk__id__inhierarchy': self.book1.pk})
        changelist = self.get_changelist(request, Category, modeladmin)
        queryset = changelist.get_queryset(request)
        self.assertEqual((list(queryset)),
                         [self.parent_category, self.child_category1, self.simple_category])

        # Make sure filter for child book works as expected
        request = self.request_factory.get('/', {'books_fk__id__inhierarchy': self.book2.pk})
        changelist = self.get_changelist(request, Category, modeladmin)
        queryset = changelist.get_queryset(request)
        self.assertEqual((list(queryset)), [self.parent_category])

        # Make sure filter for book with no category works as expected
        request = self.request_factory.get('/', {'books_fk__id__inhierarchy': self.book4.pk})
        changelist = self.get_changelist(request, Category, modeladmin)
        queryset = changelist.get_queryset(request)
        self.assertEqual(queryset.count(), 0)

        # M2M relationship -----
        request = self.request_factory.get('/', {'books_m2m__isnull': 'True'})
        changelist = self.get_changelist(request, Category, modeladmin)
        queryset = changelist.get_queryset(request)
        self.assertEqual(list(queryset), [self.child_category2])

        # Make sure the last choice is None and is selected
        filterspec = changelist.get_filters(request)[0][1]
        choices = list(filterspec.choices(changelist))
        self.assertEqual(choices[-1]['selected'], True)
        self.assertEqual(choices[-1]['query_string'], '?books_m2m__isnull=True')

        # Make sure child's books categories included
        request = self.request_factory.get('/', {'books_m2m__id__inhierarchy': self.book1.pk})
        changelist = self.get_changelist(request, Category, modeladmin)
        queryset = changelist.get_queryset(request)
        self.assertEqual((list(queryset)),
                         [self.parent_category, self.child_category1, self.simple_category])

        # Make sure filter for child book works as expected
        request = self.request_factory.get('/', {'books_m2m__id__inhierarchy': self.book2.pk})
        changelist = self.get_changelist(request, Category, modeladmin)
        queryset = changelist.get_queryset(request)
        self.assertEqual((list(queryset)), [self.parent_category])

        # Make sure filter for book with no category works as expected
        request = self.request_factory.get('/', {'books_m2m__id__inhierarchy': self.book4.pk})
        changelist = self.get_changelist(request, Category, modeladmin)
        queryset = changelist.get_queryset(request)
        self.assertEqual(queryset.count(), 0)


class UUIDPrimaryKey(TreeTestCase):

    def test_save_uuid_model(self):
        n1 = UUIDNode.objects.create(name='node')
        n2 = UUIDNode.objects.create(name='sub_node', parent=n1)
        self.assertEqual(n1.name, 'node')
        self.assertEqual(n1.tree_id, n2.tree_id)
        self.assertEqual(n2.parent, n1)

    def test_move_uuid_node(self):
        n1 = UUIDNode.objects.create(name='n1')
        n2 = UUIDNode.objects.create(name='n2', parent=n1)
        n3 = UUIDNode.objects.create(name='n3', parent=n1)
        self.assertEqual(list(n1.get_children()), [n2, n3])

        n3.move_to(n2, 'left')

        self.assertEqual(list(n1.get_children()), [n3, n2])

    def test_move_root_node(self):
        root1 = UUIDNode.objects.create(name='n1')
        child = UUIDNode.objects.create(name='n2', parent=root1)
        root2 = UUIDNode.objects.create(name='n3')
        self.assertEqual(list(root1.get_children()), [child])

        root2.move_to(child, 'left')

        self.assertEqual(list(root1.get_children()), [root2, child])

    def test_move_child_node(self):
        root1 = UUIDNode.objects.create(name='n1')
        child1 = UUIDNode.objects.create(name='n2', parent=root1)
        root2 = UUIDNode.objects.create(name='n3')
        child2 = UUIDNode.objects.create(name='n4', parent=root2)
        self.assertEqual(list(root1.get_children()), [child1])

        child2.move_to(child1, 'left')

        self.assertEqual(list(root1.get_children()), [child2, child1])


class DirectParentAssignment(TreeTestCase):
    def test_assignment(self):
        """Regression test for #428"""
        n1 = Node.objects.create()
        n2 = Node.objects.create()
        n1.parent_id = n2.id
        n1.save()


class FromDoctests(TreeTestCase):
    def test_sibling_ordered_root_nodes(self):
        a = OrderedInsertion.objects.create(name='a')
        OrderedInsertion.objects.create(name='b')
        a.refresh_from_db()
        a.name = 'c'
        a.save()
        self.assertTreeEqual(OrderedInsertion.objects.all(), '''
        2 - 1 0 1 2
        1 - 2 0 1 2
        ''')


class UniqueTogetherTestCase(TreeTestCase):
    def test_move_and_conflict(self):
        a = UniqueCodePerParentModel.objects.create(code='a', parent=None)
        b = UniqueCodePerParentModel.objects.create(code='b', parent=None)
        UniqueCodePerParentModel.objects.create(code='1', parent=a)
        b1 = UniqueCodePerParentModel.objects.create(code='1', parent=b)

        b1.parent = a  # it tries to be a1, conflicting
        self.assertRaises(IntegrityError, lambda: b1.save())

    def test_move_and_deconflict(self):
        c = UniqueCodePerParentModel.objects.create(code='c', parent=None)
        d = UniqueCodePerParentModel.objects.create(code='d', parent=None)
        UniqueCodePerParentModel.objects.create(code='1', parent=c)
        d1 = UniqueCodePerParentModel.objects.create(code='1', parent=d)

        d1.code = '2'
        d1.parent = c
        d1.save()  # it tries to be c2, not conflicting

    def test_deconflict_and_move(self):
        e = UniqueCodePerParentModel.objects.create(code='e', parent=None)
        f = UniqueCodePerParentModel.objects.create(code='f', parent=None)
        UniqueCodePerParentModel.objects.create(code='1', parent=e)
        e2 = UniqueCodePerParentModel.objects.create(code='2', parent=e)

        e2.code = '1'
        e2.parent = f
        e2.save()  # it tries to be f1, not conflicting


class RebuildTestCase(TreeTestCase):
    fixtures = ['genres.json']

    def test_rebuild(self):
        Genre.objects.update(
            lft=-1,
            rght=-1,
            level=-1,
            tree_id=-1,
        )

        with self.assertNumQueries(23):
            Genre.objects.rebuild()

        self.assertTreeEqual(Genre.objects.all(), """
            1 - 1 0 1 16
            2 1 1 1 2 9
            3 2 1 2 3 4
            4 2 1 2 5 6
            5 2 1 2 7 8
            6 1 1 1 10 15
            7 6 1 2 11 12
            8 6 1 2 13 14
            9 - 2 0 1 6
            10 9 2 1 2 3
            11 9 2 1 4 5
        """)
