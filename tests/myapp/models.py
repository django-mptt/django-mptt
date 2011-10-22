from django.db import models

from mptt.models import MPTTModel
from mptt.managers import TreeManager


class CustomTreeManager(TreeManager):
    pass


class Category(MPTTModel):
    name = models.CharField(max_length=50)
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children')

    def __unicode__(self):
        return self.name

    def delete(self):
        super(Category, self).delete()


class Genre(MPTTModel):
    name = models.CharField(max_length=50, unique=True)
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children')

    def __unicode__(self):
        return self.name


class Insert(MPTTModel):
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children')


class MultiOrder(MPTTModel):
    name = models.CharField(max_length=50)
    size = models.PositiveIntegerField()
    date = models.DateField()
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children')

    class MPTTMeta:
        order_insertion_by = ['name', 'size', 'date']

    def __unicode__(self):
        return self.name


class Node(MPTTModel):
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children')

    class MPTTMeta:
        left_attr = 'does'
        right_attr = 'zis'
        level_attr = 'madness'
        tree_id_attr = 'work'


class OrderedInsertion(MPTTModel):
    name = models.CharField(max_length=50)
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children')

    class MPTTMeta:
        order_insertion_by = ['name']

    def __unicode__(self):
        return self.name


class Tree(MPTTModel):
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children')


class Person(MPTTModel):
    name = models.CharField(max_length=50)
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children')

    # just testing it's actually possible to override the tree manager
    objects = models.Manager()
    my_tree_manager = CustomTreeManager()

    class MPTTMeta:
        tree_manager_attr = 'my_tree_manager'

    def __unicode__(self):
        return self.name


class Student(Person):
    type = models.CharField(max_length=50)
