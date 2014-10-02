from __future__ import unicode_literals
from django.db import models
from django_extensions.db.fields import UUIDField
from django.utils.encoding import python_2_unicode_compatible

import mptt
from mptt.fields import TreeForeignKey, TreeOneToOneField, TreeManyToManyField
from mptt.models import MPTTModel
from mptt.managers import TreeManager
from django.db.models.query import QuerySet


class CustomTreeQueryset(QuerySet):
    pass


class CustomTreeManager(TreeManager):
    def get_query_set(self):
        return CustomTreeQueryset(model=self.model, using=self._db)

    def get_queryset(self):
        # Django 1.8 removed the fallbacks here.
        return CustomTreeQueryset(model=self.model, using=self._db)


@python_2_unicode_compatible
class Category(MPTTModel):
    name = models.CharField(max_length=50)
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children')

    def __str__(self):
        return self.name

    def delete(self):
        super(Category, self).delete()
    delete.alters_data = True


@python_2_unicode_compatible
class Genre(MPTTModel):
    name = models.CharField(max_length=50, unique=True)
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children')

    def __str__(self):
        return self.name


class Game(models.Model):
    genre = models.ForeignKey(Genre)
    genres_m2m = models.ManyToManyField(Genre, related_name='games_m2m')
    name = models.CharField(max_length=50)

    def __str__(self):
        return self.name


class Insert(MPTTModel):
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children')


@python_2_unicode_compatible
class MultiOrder(MPTTModel):
    name = models.CharField(max_length=50)
    size = models.PositiveIntegerField()
    date = models.DateField()
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children')

    class MPTTMeta:
        order_insertion_by = ['name', 'size', '-date']

    def __str__(self):
        return self.name


class Node(MPTTModel):
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children')

    class MPTTMeta:
        left_attr = 'does'
        right_attr = 'zis'
        level_attr = 'madness'
        tree_id_attr = 'work'


class UUIDNode(MPTTModel):
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children')
    uuid = UUIDField(primary_key=True)
    name = models.CharField(max_length=50)


@python_2_unicode_compatible
class OrderedInsertion(MPTTModel):
    name = models.CharField(max_length=50)
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children')

    class MPTTMeta:
        order_insertion_by = ['name']

    def __str__(self):
        return self.name


class Tree(MPTTModel):
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children')


class NewStyleMPTTMeta(MPTTModel):
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children')

    class MPTTMeta(object):
        left_attr = 'testing'


@python_2_unicode_compatible
class Person(MPTTModel):
    name = models.CharField(max_length=50)
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children')

    # just testing it's actually possible to override the tree manager
    my_tree_manager = CustomTreeManager()

    def __str__(self):
        return self.name


class Student(Person):
    type = models.CharField(max_length=50)


@python_2_unicode_compatible
class CustomPKName(MPTTModel):
    my_id = models.AutoField(db_column='my_custom_name', primary_key=True)
    name = models.CharField(max_length=50)
    parent = models.ForeignKey(
        'self', null=True, blank=True,
        related_name='children', db_column="my_cusom_parent")

    def __str__(self):
        return self.name


class ReferencingModel(models.Model):
    fk = TreeForeignKey(Category, related_name='+')
    one = TreeOneToOneField(Category, related_name='+')
    m2m = TreeManyToManyField(Category, related_name='+')


# for testing various types of inheritance:

# 1. multi-table inheritance, with mptt fields on base class.

class MultiTableInheritanceA1(MPTTModel):
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children')


class MultiTableInheritanceA2(MultiTableInheritanceA1):
    name = models.CharField(max_length=50)


# 2. multi-table inheritance, with mptt fields on child class.

class MultiTableInheritanceB1(MPTTModel):
    name = models.CharField(max_length=50)


class MultiTableInheritanceB2(MultiTableInheritanceB1):
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children')


# 3. abstract models

class AbstractModel(MPTTModel):
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children')
    ghosts = models.CharField(max_length=50)

    class Meta:
        abstract = True


class ConcreteModel(AbstractModel):
    name = models.CharField(max_length=50)


class AbstractConcreteAbstract(ConcreteModel):
    # abstract --> concrete --> abstract
    class Meta:
        abstract = True


class ConcreteAbstractConcreteAbstract(ConcreteModel):
    # concrete --> abstract --> concrete --> abstract
    pass


class ConcreteConcrete(ConcreteModel):
    # another subclass (concrete this time) of the root concrete model
    pass


# 4. proxy models

class SingleProxyModel(ConcreteModel):
    class Meta:
        proxy = True


class DoubleProxyModel(SingleProxyModel):
    class Meta:
        proxy = True


class AutoNowDateFieldModel(MPTTModel):
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children')
    now = models.DateTimeField(auto_now_add=True)

    class MPTTMeta:
        order_insertion_by = ('now',)


# test registering of remote model
class Group(models.Model):
    name = models.CharField(max_length=100)

TreeForeignKey(Group, blank=True, null=True).contribute_to_class(Group, 'parent')
mptt.register(Group, order_insertion_by=('name',))
