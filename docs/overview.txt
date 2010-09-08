===========
Django MPTT
===========

.. admonition:: About this document

   This document provides an overview of what Modified Preorder Tree
   Traversal (MPTT) and Django MPTT are.

.. contents::
   :depth: 3


What is Modified Preorder Tree Traversal?
=========================================

MPTT is a technique for storing hierarchical data in a database in a
manner which makes tree retrieval operations such as fetching complete
trees, item ancestors and item descendants very efficient.

The trade-off for this efficiency is that performing inserts and moving
items around the tree is more involved, as there's some extra work
required to keep the tree structure in a good state at all times.

Here are a few articles about MPTT to whet your appetite and provide
details about how the technique itself works:

    * `Trees in SQL`_
    * `Storing Hierarchical Data in a Database`_
    * `Managing Hierarchical Data in MySQL`_

In particular, these articles should help you understand the two most
important fields in MPTT - the left and right "edge indicators". Other
fields involved in Django MPTT's implementation of the technique are
discusssed in the technical details documentation.

.. _`Trees in SQL`: http://www.intelligententerprise.com/001020/celko.jhtml
.. _`Storing Hierarchical Data in a Database`: http://www.sitepoint.com/print/hierarchical-data-database
.. _`Managing Hierarchical Data in MySQL`: http://dev.mysql.com/tech-resources/articles/hierarchical-data.html


What is Django MPTT?
====================

Django MPTT is a reusable/standalone Django application which aims to
make it easy for you to use Modified Preorder Tree Traversal with your
own Django models in your own applications.

It takes care of the details of managing a database table as a tree
structure and provides tools for working with trees of model instances.

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
