from django.db import models

from mptt.models import treeify

class Category(models.Model):
    name = models.CharField(max_length=50)
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children')

    def __unicode__(self):
        return self.name

class Genre(models.Model):
    name = models.CharField(max_length=50, unique=True)
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children')

    def __unicode__(self):
        return self.name

class Node(models.Model):
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children')

treeify(Category)
treeify(Genre)
treeify(Node)
