===========
django-mptt
===========

Utilities for implementing Modified Preorder Tree Traversal with your
Django Models and working with trees of Model instances.

.. image:: https://secure.travis-ci.org/django-mptt/django-mptt.png?branch=master

Project home: http://github.com/django-mptt/django-mptt/

Documentation: http://django-mptt.github.io/django-mptt/

Discussion group: http://groups.google.com/group/django-mptt-dev

What is Modified Preorder Tree Traversal?
=========================================

MPTT is a technique for storing hierarchical data in a database. The aim is to
make retrieval operations very efficient.

The trade-off for this efficiency is that performing inserts and moving
items around the tree is more involved, as there's some extra work
required to keep the tree structure in a good state at all times.

Here are a few articles about MPTT to whet your appetite and provide
details about how the technique itself works:

    * `Trees in SQL`_
    * `Storing Hierarchical Data in a Database`_
    * `Managing Hierarchical Data in MySQL`_

.. _`Trees in SQL`: http://www.ibase.ru/devinfo/DBMSTrees/sqltrees.html
.. _`Storing Hierarchical Data in a Database`: http://www.sitepoint.com/print/hierarchical-data-database
.. _`Managing Hierarchical Data in MySQL`: http://mirror.neu.edu.cn/mysql/tech-resources/articles/hierarchical-data.html


What is ``django-mptt``?
========================

``django-mptt`` is a reusable Django app which aims to make it easy for you 
to use MPTT with your own Django models.

It takes care of the details of managing a database table as a tree
structure and provides tools for working with trees of model instances.

Requirements
------------

* Python 2.6+ (with experimental support for python 3.2+)
* Django 1.4.2+

Feature overview
----------------

* Simple registration of models - fields required for tree structure will be
  added automatically.

* The tree structure is automatically updated when you create or delete
  model instances, or change an instance's parent.

* Each level of the tree is automatically sorted by a field (or fields) of your
  choice.

* New model methods are added to each registered model for:

  * changing position in the tree
  * retrieving ancestors, siblings, descendants
  * counting descendants
  * other tree-related operations

* A ``TreeManager`` manager is added to all registered models. This provides
  methods to:
  
  * move nodes around a tree, or into a different tree
  * insert a node anywhere in a tree
  * rebuild the MPTT fields for the tree (useful when you do bulk updates
    outside of django)

* Form fields for tree models.

* Utility functions for tree models.

* Template tags and filters for rendering trees.


What's different about this fork?
---------------------------------

The only difference at this time is that this version includes a manager method called ``get_queryset_ancestors``. This method is similar to ``get_queryset_descendants`` only it works in the opposite direction. You may be wondering "What's the point? Why can't you use get_ancestors()?" What if you wanted to filter a queryset using characteristics of its descendants to determine the results of the filter?

Here's an example of such a query using files and directories arranged in the usual hierarchical fashion that we're all familiar with. In this scenario we are determining whether a user has access to a directory based off of the content, or _type_ of file or files that exist within said directory. So we start with this:

``>>> Directory.objects.filter(file__filetype__accessible_filetypes__users = 1)
[<Directory: /Files/2010/July>, <Directory: /Files/2010/June]```

We see from the output above that the user with the id ``1`` can access ``/Files/2010/{June,July}`` but what if we wanted to list the intermediate directories as well? We'd have to retrieve the ancestors of each object in the results, store them somewhere, and filter them for duplicates. But this will result in our having a list of ancestor directories, not a chainable queryset. We want a queryset so we can narrow down our results with more filters if we need to. That's where ``get_queryset_ancestors`` comes in, observe:

``>>> Directory.tree_manager.get_queryset_ancestors(Directory.objects.filter(file__filetype__accessible_filetypes__users = 1))
[<Directory: /Files/2010>, <Directory: /Files>]``

Now we have queryset of intermediate directories that we can filter even further:

``>>> Directory.tree_manager.get_queryset_ancestors(Directory.objects.filter(file__filetype__accessible_filetypes__users = 1)).filter(parent = 1)
[<Directory: /Files/2010>]``

