from django.db import models

import mptt

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

class Tree(models.Model):
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children')

mptt.register(Category)
mptt.register(Genre)
mptt.register(Node, left_attr='does', right_attr='zis', level_attr='madness',
              tree_id_attr='work')
mptt.register(Tree)
