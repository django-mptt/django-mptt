=================
Technical details
=================

.. contents::
   :depth: 3

Tree structure
==============

In addition to the left and right identifiers which form the core of how
MPTT works and the parent field, Django MPTT has the following
additional fields on each tree node.

Tree id
-------

**A unique identifier assigned to each root node and inherited by all its
descendants.**

This identifier is the means by which Django MPTT implements multiple
root nodes.

Since we can use it to identify all nodes which belong to a particular
tree, the subtree headed by each root node can have its edge indicators
starting at ``1`` - as long as tree operations are constrained to the
appropriate tree id(s), we don't have to worry about overlapping of left
and right edge indicator values with those of nodes in other trees.

This approach limits the number of rows affected when making space to
insert new nodes and removing gaps left by deleted nodes.

Root node ordering
~~~~~~~~~~~~~~~~~~

This field also defines the order in which root nodes are retrieved when
you create a ``QuerySet`` using ``TreeManager``, which by default
orders the resulting ``QuerySet`` by tree id, then left edge indicator
(for depth-first ordering).

When a new root node is created, it is assigned the next-largest tree id
available, so by default root nodes (and thus their subtrees) are
displayed in the order they were created.

Movement and volatility
~~~~~~~~~~~~~~~~~~~~~~~

Since root node ordering is defined by tree id, it can also be used to
implement movement of other nodes as siblings of a target root node.

When you use the node movement API to move a node to be a sibling of a
root node, tree ids are shuffled around to achieve the new ordering
required. Given this, you should consider the tree id to be
**volatile**, so it's recommended that you don't store tree ids in your
applications to identify particular trees.

Since *every* node has a tree id, movement of a node to be a sibling of
a root node can potentially result in a large number of rows being
modified, as the further away the node you're moving is from its target
location, the larger the number of rows affected - every node with a
tree id between that of the node being moved and the target root node
will require its tree id to be modified.

Level
-----

**The level (or "depth") at which a node sits in the tree.**

Root nodes are level ``0``, their immediate children are level ``1``,
*their* immediate children are level ``2`` and so on...

This field is purely denormalisation for convenience. It avoids the need
to examine the tree structure to determine the level of a particular
node and makes queries which need to take depth into account easier to
implement using Django's ORM. For example, limiting the number of levels
of nodes which are retrieved for the whole tree or any subtree::

   # Retrieve root nodes and their immediate children only
   SomeModel.objects.filter(level__lte=1)

   # Retrieve descendants of a node up to two levels below it
   node.get_descendants().filter(level__lte=node.level + 2)


Concurrency
===========

Most CRUD methods involve the execution of multiple queries. These
methods need to be made mutually exclusive, otherwise corrupt hierarchies might get created.
Mutual exclusivity is usually achieved by placing the queries between
**LOCK TABLE** and **UNLOCK TABLE** statements. However, mptt
can't do the locking itself because the `LOCK/UNLOCK statements are not transaction safe`_
and would therefore mess up the client code's transactions. This means that it's
the client code's responsibility to ensure that calls to mptt CRUD methods are mutually
exclusive.

Note: In the above paragraph 'client code' means any django app that uses mptt base models.

.. _`LOCK/UNLOCK statements are not transaction safe`: https://dev.mysql.com/doc/refman/5.7/en/lock-tables-and-transactions.html




Running the test suite
======================

The ``mptt.tests`` package is set up as a project which holds a test
settings module and defines models for use in testing MPTT. You can run
the tests from the command-line using the ``manage.py`` script::

   python manage.py test
