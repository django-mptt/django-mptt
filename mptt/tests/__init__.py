r"""
>>> from mptt.tests.models import Genre

>>> def print_tree_details(nodes):
...     print '\n'.join(['%s %s %s %s %s %s' % \
...                     (n.pk, n.parent_id or '-', n.tree_id, n.level, n.lft, n.rght) \
...                     for n in nodes])

# Creation ####################################################################
>>> action = Genre.objects.create(name='Action')
>>> platformer = Genre.objects.create(name='Platformer', parent=action)
>>> platformer_2d = Genre.objects.create(name='2D Platformer', parent=platformer)
>>> platformer_3d = Genre.objects.create(name='3D Platformer', parent=platformer)
>>> platformer_4d = Genre.objects.create(name='4D Platformer', parent=platformer)
>>> rpg = Genre.objects.create(name='Role-playing Game')
>>> arpg = Genre.objects.create(name='Action RPG', parent=rpg)
>>> trpg = Genre.objects.create(name='Tactical RPG', parent=rpg)
>>> print_tree_details(Genre.tree.all())
1 - 1 0 1 10
2 1 1 1 2 9
3 2 1 2 3 4
4 2 1 2 5 6
5 2 1 2 7 8
6 - 2 0 1 6
7 6 2 1 2 3
8 6 2 1 4 5

# Model Instance Methods ######################################################
>>> action = Genre.objects.get(pk=action.pk)
>>> [g.name for g in action.get_ancestors()]
[]
>>> [g.name for g in action.get_ancestors(ascending=True)]
[]
>>> [g.name for g in action.get_descendants()]
[u'Platformer', u'2D Platformer', u'3D Platformer', u'4D Platformer']
>>> [g.name for g in action.get_descendants(include_self=True)]
[u'Action', u'Platformer', u'2D Platformer', u'3D Platformer', u'4D Platformer']
>>> action.get_descendant_count()
4
>>> [g.name for g in action.get_siblings()]
[u'Role-playing Game']
>>> [g.name for g in action.get_siblings(include_self=True)]
[u'Action', u'Role-playing Game']

>>> platformer = Genre.objects.get(pk=platformer.pk)
>>> [g.name for g in platformer.get_ancestors()]
[u'Action']
>>> [g.name for g in platformer.get_ancestors(ascending=True)]
[u'Action']
>>> [g.name for g in platformer.get_descendants()]
[u'2D Platformer', u'3D Platformer', u'4D Platformer']
>>> [g.name for g in platformer.get_descendants(include_self=True)]
[u'Platformer', u'2D Platformer', u'3D Platformer', u'4D Platformer']
>>> platformer.get_descendant_count()
3
>>> [g.name for g in platformer.get_siblings()]
[]
>>> [g.name for g in platformer.get_siblings(include_self=True)]
[u'Platformer']

>>> platformer_3d = Genre.objects.get(pk=platformer_3d.pk)
>>> [g.name for g in platformer_3d.get_ancestors()]
[u'Action', u'Platformer']
>>> [g.name for g in platformer_3d.get_ancestors(ascending=True)]
[u'Platformer', u'Action']
>>> [g.name for g in platformer_3d.get_descendants()]
[]
>>> [g.name for g in platformer_3d.get_descendants(include_self=True)]
[u'3D Platformer']
>>> platformer_3d.get_descendant_count()
0
>>> [g.name for g in platformer_3d.get_siblings()]
[u'2D Platformer', u'4D Platformer']
>>> [g.name for g in platformer_3d.get_siblings(include_self=True)]
[u'2D Platformer', u'3D Platformer', u'4D Platformer']

# Reparenting #################################################################

Test that trees are in the appropriate state and that reparented items have the
correct tree attributes defined, should they be required for use after a save.

# Extract new root node from a subtree
>>> platformer = Genre.objects.get(pk=platformer.pk)
>>> platformer.parent = None
>>> platformer.save()
>>> print_tree_details([platformer])
2 - 3 0 1 8
>>> print_tree_details(Genre.tree.all())
1 - 1 0 1 2
6 - 2 0 1 6
7 6 2 1 2 3
8 6 2 1 4 5
2 - 3 0 1 8
3 2 3 1 2 3
4 2 3 1 4 5
5 2 3 1 6 7

# Extract new root node from a leaf node which has siblings
>>> platformer_3d = Genre.objects.get(pk=platformer_3d.pk)
>>> platformer_3d.parent = None
>>> platformer_3d.save()
>>> print_tree_details([platformer_3d])
4 - 4 0 1 2
>>> print_tree_details(Genre.tree.all())
1 - 1 0 1 2
6 - 2 0 1 6
7 6 2 1 2 3
8 6 2 1 4 5
2 - 3 0 1 6
3 2 3 1 2 3
5 2 3 1 4 5
4 - 4 0 1 2

# Check that invalid parent errors are thrown appropriately when giving
# a root node a parent.
>>> rpg = Genre.objects.get(pk=rpg.pk)
>>> rpg.parent = rpg
>>> rpg.save()
Traceback (most recent call last):
    ...
InvalidParent: A root node may not have its parent changed to any node in its own tree.
>>> arpg = Genre.objects.get(pk=arpg.pk)
>>> rpg.parent = arpg
>>> rpg.save()
Traceback (most recent call last):
    ...
InvalidParent: A root node may not have its parent changed to any node in its own tree.

# Make a tree a subtree of another tree
>>> rpg = Genre.objects.get(pk=rpg.pk)
>>> platformer = Genre.objects.get(pk=platformer.pk)
>>> rpg.parent = platformer
>>> rpg.save()
>>> print_tree_details([rpg])
6 2 3 1 6 11
>>> print_tree_details(Genre.tree.all())
1 - 1 0 1 2
2 - 3 0 1 12
3 2 3 1 2 3
5 2 3 1 4 5
6 2 3 1 6 11
7 6 3 2 7 8
8 6 3 2 9 10
4 - 4 0 1 2

# Move a leaf node to another tree
>>> arpg = Genre.objects.get(pk=arpg.pk)
>>> platformer_3d = Genre.objects.get(pk=platformer_3d.pk)
>>> arpg.parent = platformer_3d
>>> arpg.save()
>>> print_tree_details([arpg])
7 4 4 1 2 3
>>> print_tree_details(Genre.tree.all())
1 - 1 0 1 2
2 - 3 0 1 10
3 2 3 1 2 3
5 2 3 1 4 5
6 2 3 1 6 9
8 6 3 2 7 8
4 - 4 0 1 4
7 4 4 1 2 3

# Move a subtree to another tree
>>> rpg = Genre.objects.get(pk=rpg.pk)
>>> platformer_3d = Genre.objects.get(pk=platformer_3d.pk)
>>> rpg.parent = platformer_3d
>>> rpg.save()
>>> print_tree_details([rpg])
6 4 4 1 4 7
>>> print_tree_details(Genre.tree.all())
1 - 1 0 1 2
2 - 3 0 1 6
3 2 3 1 2 3
5 2 3 1 4 5
4 - 4 0 1 8
7 4 4 1 2 3
6 4 4 1 4 7
8 6 4 2 5 6

# Deletion ####################################################################

# Delete a node which has siblings
>>> platformer_2d = Genre.objects.get(pk=platformer_2d.pk)
>>> platformer_2d.delete()
>>> print_tree_details(Genre.tree.all())
1 - 1 0 1 2
2 - 3 0 1 4
5 2 3 1 2 3
4 - 4 0 1 8
7 4 4 1 2 3
6 4 4 1 4 7
8 6 4 2 5 6

# Delete a node which has descendants
>>> rpg = Genre.objects.get(pk=rpg.pk)
>>> rpg.delete()
>>> print_tree_details(Genre.tree.all())
1 - 1 0 1 2
2 - 3 0 1 4
5 2 3 1 2 3
4 - 4 0 1 4
7 4 4 1 2 3

# Delete a root node
>>> platformer = Genre.objects.get(pk=platformer.pk)
>>> platformer.delete()
>>> print_tree_details(Genre.tree.all())
1 - 1 0 1 2
4 - 4 0 1 4
7 4 4 1 2 3
"""

# TODO Fixtures won't work with Django MPTT unless the pre_save signal
#      is given the ``save()`` method's ``raw`` argument, so we know not
#      to attempt any tree processing.
#
#      http://code.djangoproject.com/ticket/5422 has a patch for this.
#
#      Once this change is available, we can think about using the more
#      appropriate ``django.tests.TestCase`` with fixtures for testing
#      specific features without having a knock-on effect on other
#      tests.
