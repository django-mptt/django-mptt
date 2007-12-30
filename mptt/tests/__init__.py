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

# Deletion ####################################################################
>>> platformer_3d = Genre.objects.get(pk=platformer_3d.pk)
>>> platformer_3d.delete()
>>> print_tree_details(Genre.tree.all())
1 - 1 0 1 8
2 1 1 1 2 7
3 2 1 2 3 4
5 2 1 2 5 6
6 - 2 0 1 6
7 6 2 1 2 3
8 6 2 1 4 5

>>> platformer = Genre.objects.get(pk=platformer.pk)
>>> platformer.delete()
>>> print_tree_details(Genre.tree.all())
1 - 1 0 1 2
6 - 2 0 1 6
7 6 2 1 2 3
8 6 2 1 4 5

>>> action = Genre.objects.get(pk=action.pk)
>>> action.delete()
>>> print_tree_details(Genre.tree.all())
6 - 2 0 1 6
7 6 2 1 2 3
8 6 2 1 4 5
"""
