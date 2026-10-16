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


.. _concurrency:

Concurrency
===========

Inserting, moving and deleting nodes reads the tree fields of the involved
nodes and then runs several ``UPDATE`` statements based on those values. If
two processes modify the tree at the same time these statements can
interleave and corrupt the tree. Wrapping the operations in
``transaction.atomic()`` is not enough: under ``READ COMMITTED``, which Django
uses by default on PostgreSQL and MySQL, another transaction can commit
between the reads and the updates.

django-mptt does not lock anything itself. There is no portable,
transaction-safe way to do so (MySQL's ``LOCK TABLES`` implicitly commits the
current transaction, SQLite has no table locks) and the right lock depends on
the application. Instead, serialize all writes to the tree in your code:

1. Run every operation which modifies the tree in a transaction and acquire
   a lock at its start. Use one lock for the whole table: some operations,
   e.g. inserting a root node, change the ``tree_id`` of other trees too, so
   locking only the affected tree is not sufficient.
2. Acquire the lock before django-mptt reads the tree. django-mptt reloads
   the tree fields of the involved nodes from the database when inserting,
   moving and deleting, so under ``READ COMMITTED`` it doesn't matter if your
   instances were loaded before the lock was acquired.

A portable lock is ``select_for_update()`` on a dedicated row:

.. code-block:: python

    from django.db import models


    class TreeLock(models.Model):
        """Contains exactly one row, create it in a data migration."""


    def lock_tree():
        TreeLock.objects.select_for_update().get(pk=1)

On PostgreSQL a transaction-level advisory lock works without an additional
table:

.. code-block:: python

    from django.db import connection


    def lock_tree():
        with connection.cursor() as cursor:
            # Any constant which is unique within your project
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [4711])

Then acquire the lock in all code paths which modify the tree, including the
admin, by overriding the model methods:

.. code-block:: python

    from django.db import transaction
    from mptt.models import MPTTModel


    class Category(MPTTModel):
        ...

        def save(self, *args, **kwargs):
            with transaction.atomic():
                lock_tree()
                super().save(*args, **kwargs)

        def delete(self, *args, **kwargs):
            with transaction.atomic():
                lock_tree()
                return super().delete(*args, **kwargs)

        def move_to(self, target, position="first-child"):
            with transaction.atomic():
                lock_tree()
                super().move_to(target, position)

Calls to manager methods such as ``rebuild()``, ``partial_rebuild()``,
``insert_node()`` and ``move_node()``, and ``delay_mptt_updates()`` or
``disable_mptt_updates()`` blocks have to be wrapped the same way.

Some notes on other configurations:

* SQLite only allows one writer at a time, ``select_for_update()`` is a no-op
  there.
* With ``REPEATABLE READ`` (e.g. configured using the ``isolation_level``
  option on MySQL) reads see a snapshot taken at the first read of the
  transaction. Acquire the lock before reading anything else in the
  transaction, otherwise django-mptt still sees outdated tree fields.
* With PostgreSQL's ``SERIALIZABLE`` isolation level conflicting
  transactions fail with serialization errors instead of corrupting the
  tree; they have to be retried.




Running the test suite
======================

The ``mptt.tests`` package is set up as a project which holds a test
settings module and defines models for use in testing MPTT. You can run
the tests from the command-line using the ``manage.py`` script::

   python manage.py test
