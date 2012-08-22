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
