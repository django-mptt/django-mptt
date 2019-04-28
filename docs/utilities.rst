================================
Utilities for working with trees
================================

.. contents::
   :depth: 3

List/tree utilities
===================

The ``mptt.utils`` module contains the following functions for working
with and creating lists of model instances which represent trees.

``previous_current_next()``
---------------------------

From http://www.wordaligned.org/articles/zippy-triples-served-with-python

Creates an iterator which returns (previous, current, next) triples,
with ``None`` filling in when there is no previous or next available.

This function is useful if you want to step through a tree one item at a
time and you need to refer to the previous or next item in the tree. It
is used in the implementation of `tree_item_iterator()`_.

Required arguments
~~~~~~~~~~~~~~~~~~

``items``
   A list or other iterable item.

``tree_item_iterator()``
------------------------

This function is used to implement the ``tree_info`` template filter,
yielding two-tuples of (tree item, tree structure information ``dict``).

See the ``tree_info`` documentation for more information.

Required arguments
~~~~~~~~~~~~~~~~~~

``items``
   A list or iterable of model instances which represent a tree.

Optional arguments
~~~~~~~~~~~~~~~~~~

``ancestors``
   Boolean. If ``True``, a list of unicode representations of the
   ancestors of the current node, in descending order (root node first,
   immediate parent last), will be added to the tree structure
   information ``dict` under the key ``'ancestors'``.

``drilldown_tree_for_node()``
-----------------------------

This function is used in the implementation of the
``drilldown_tree_for_node`` template tag.

It creates an iterable which yields model instances representing a
drilldown tree for a given node.

A drilldown tree consists of a node's ancestors, itself and its
immediate children or all descendants, all in tree order.

Optional arguments may be given to specify details of a relationship
between the given node's class and another model class, for the
purpose of adding related item counts to the node's children.

Required arguments
~~~~~~~~~~~~~~~~~~

``node``
   A model instance which represents a node in a tree.

Optional arguments
~~~~~~~~~~~~~~~~~~

``rel_cls``
   A model class which has a relationship to the node's class.

``rel_field``
   The name of the field in ``rel_cls`` which holds the relationship
   to the node's class.

``count_attr``
   The name of an attribute which should be added to each child of the
   node in the drilldown tree (if any), containing a count of how many
   instances of ``rel_cls`` are related to it through ``rel_field``.

``cumulative``
   If ``True``, the count will be for items related to the child
   node *and* all of its descendants. Defaults to ``False``.

``get_cached_trees()``
-----------------------------

Takes a list/queryset of model objects in MPTT left (depth-first) order and
caches the children and parent on each node. This allows up and down traversal
through the tree without the need for further queries. Use cases include using
a recursively included template or arbitrarily traversing trees.

Returns a list of top-level nodes. If a single tree was provided in its
entirety, the list will of course consist of just the tree's root node.

Aliases to this function are also available:

``mptt.templatetags.mptt_tag.cache_tree_children``
   Use for recursive rendering in templates.

``mptt.querysets.TreeQuerySet.get_cached_trees``
   Useful for chaining with queries; e.g.,
   `Node.objects.filter(**kwargs).get_cached_trees()`

Required arguments
~~~~~~~~~~~~~~~~~~

``queryset``
   An iterable that consists of all nodes which are to be cached.
