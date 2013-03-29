from django.contrib.auth.models import Group
from django.db import models
try:
    from django.utils.six import PY3
except ImportError:
    PY3 = False

import mptt
from mptt.models import MPTTModel, TreeForeignKey
from mptt.managers import TreeManager


class CustomTreeManager(TreeManager):
    pass


class Category(MPTTModel):
    name = models.CharField(max_length=50)
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children')

    def __unicode__(self):
        return self.name

    def __str__(self):
        if PY3:
            return self.name
        else:
            return self.name.encode('utf-8')

    def delete(self):
        super(Category, self).delete()


class Genre(MPTTModel):
    name = models.CharField(max_length=50, unique=True)
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children')

    def __unicode__(self):
        return self.name

    def __str__(self):
        if PY3:
            return self.name
        else:
            return self.name.encode('utf-8')


class Insert(MPTTModel):
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children')


class MultiOrder(MPTTModel):
    name = models.CharField(max_length=50)
    size = models.PositiveIntegerField()
    date = models.DateField()
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children')

    class MPTTMeta:
        order_insertion_by = ['name', 'size', '-date']

    def __unicode__(self):
        return self.name

    def __str__(self):
        if PY3:
            return self.name
        else:
            return self.name.encode('utf-8')


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

    def __str__(self):
        if PY3:
            return self.name
        else:
            return self.name.encode('utf-8')


class Tree(MPTTModel):
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children')


class NewStyleMPTTMeta(MPTTModel):
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children')

    class MPTTMeta(object):
        left_attr = 'testing'


class Person(MPTTModel):
    name = models.CharField(max_length=50)
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children')

    # just testing it's actually possible to override the tree manager
    objects = models.Manager()
    my_tree_manager = CustomTreeManager()

    def __unicode__(self):
        return self.name

    def __str__(self):
        if PY3:
            return self.name
        else:
            return self.name.encode('utf-8')


class Student(Person):
    type = models.CharField(max_length=50)


class CustomPKName(MPTTModel):
    my_id = models.AutoField(db_column='my_custom_name', primary_key=True)
    name = models.CharField(max_length=50)
    parent = models.ForeignKey('self', null=True, blank=True,
            related_name='children', db_column="my_cusom_parent")

    def __unicode__(self):
        return self.name

    def __str__(self):
        if PY3:
            return self.name
        else:
            return self.name.encode('utf-8')


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


# test registering of remote model
TreeForeignKey(Group, blank=True, null=True).contribute_to_class(Group, 'parent')
mptt.register(Group, order_insertion_by=('name',))
