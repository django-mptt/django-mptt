==========================================
**This project is currently unmaintained**
==========================================

django-mptt works by storing pre-computed left/right/level/tree_id values
alongside each row. This makes reads very fast, but it means that every
insert, move, or delete must update a potentially large number of sibling and
ancestor rows. This write amplification is the fundamental reason the library
is hard to maintain: concurrent writes can race and corrupt the tree, bulk
operations bypass the update logic entirely, and any code that touches the
database outside of django-mptt (raw SQL, ``bulk_update``, migrations) can
leave the tree in an inconsistent state. Rebuilding with ``rebuild()`` is
the escape hatch, but it locks the table.

If you are starting a new project, or can afford to migrate, consider an
alternative. Newer databases support recursive Common Table Expressions (CTE),
which let you store only a parent FK and compute ancestry on the fly. See
`django-tree-queries <https://github.com/matthiask/django-tree-queries>`_ for
such an implementation and its `announcement blog post
<https://406.ch/writing/django-tree-queries/>`__. Other alternatives are
listed on `Django Packages <https://djangopackages.org/grids/g/trees-and-graphs/>`__.

django-mptt itself is kept alive on a best-effort basis — bugs get fixed when
reported with a clear reproduction, compatibility with new Django versions is
maintained, but new features will not be added.


===========
django-mptt
===========

Utilities for implementing Modified Preorder Tree Traversal with your
Django Models and working with trees of Model instances.

.. image:: https://secure.travis-ci.org/django-mptt/django-mptt.svg?branch=master
    :alt: Build Status
    :target: https://travis-ci.org/django-mptt/django-mptt

Project home: https://github.com/django-mptt/django-mptt/

Documentation: https://django-mptt.readthedocs.io/

Discussion group: https://groups.google.com/forum/#!forum/django-mptt-dev

What is Modified Preorder Tree Traversal?
=========================================

MPTT is a technique for storing hierarchical data in a database. The aim is to
make retrieval operations very efficient.

The trade-off for this efficiency is that performing inserts and moving
items around the tree are more involved, as there's some extra work
required to keep the tree structure in a good state at all times.

Here are a few articles about MPTT to whet your appetite and provide
details about how the technique itself works:

* `Trees in SQL`_
* `Storing Hierarchical Data in a Database`_
* `Managing Hierarchical Data in MySQL`_

.. _`Trees in SQL`: https://www.ibase.ru/files/articles/programming/dbmstrees/sqltrees.html
.. _`Storing Hierarchical Data in a Database`: https://www.sitepoint.com/hierarchical-data-database/
.. _`Managing Hierarchical Data in MySQL`: http://mikehillyer.com/articles/managing-hierarchical-data-in-mysql/

What is ``django-mptt``?
========================

``django-mptt`` is a reusable Django app that aims to make it easy for you
to use MPTT with your own Django models.

It takes care of the details of managing a database table as a tree
structure and provides tools for working with trees of model instances.

Requirements
------------

* A supported version of Python: https://devguide.python.org/versions/#supported-versions
* A supported version of Django: https://www.djangoproject.com/download/#supported-versions

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
    outside of Django)

* `Form fields`_ for tree models.

* `Utility functions`_ for tree models.

* `Template tags and filters`_ for rendering trees.

* `Admin classes`_ for visualizing and modifying trees in Django's administration
  interface.

.. _`Form fields`: https://django-mptt.readthedocs.io/en/latest/forms.html
.. _`Utility functions`: https://django-mptt.readthedocs.io/en/latest/utilities.html
.. _`Template tags and filters`: https://django-mptt.readthedocs.io/en/latest/templates.html
.. _`Admin classes`: https://django-mptt.readthedocs.io/en/latest/admin.html
