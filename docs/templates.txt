===============================
Working with trees in templates
===============================

.. admonition:: About this document

   This document contains details about the template tags and filters
   Django MPTT provides for working with trees of model instances.

.. contents::
   :depth: 3

Template tags and filters
=========================

The ``mptt.templatetags.mptt_tags`` module defines template tags and
filters for working with trees of model instances.

To use these, you must add ``mptt`` to your project's ``INSTALLED_APPS``
setting, then you can load the tag module in your templates using
``{% load mptt_tags %}``

Tag reference
-------------

``full_tree_for_model``
~~~~~~~~~~~~~~~~~~~~~~~

Populates a template variable with a ``QuerySet`` containing the full
tree for a given model.

Usage::

   {% full_tree_for_model [model] as [varname] %}

The model is specified in ``[appname].[modelname]`` format.

Example::

   {% full_tree_for_model tests.Genre as genres %}

``drilldown_tree_for_node``
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Populates a template variable with the drilldown tree for a given node,
optionally counting the number of items associated with its children.

A drilldown tree consists of a node's ancestors, itself and its
immediate children. For example, a drilldown tree for a book category
"Personal Finance" might look something like::

   Books
      Business, Finance & Law
         Personal Finance
            Budgeting (220)
            Financial Planning (670)

Usage::

   {% drilldown_tree_for_node [node] as [varname] %}

Extended usage::

   {% drilldown_tree_for_node [node] as [varname] count [foreign_key] in [count_attr] %}
   {% drilldown_tree_for_node [node] as [varname] cumulative count [foreign_key] in [count_attr] %}

The foreign key is specified in ``[appname].[modelname].[fieldname]``
format, where ``fieldname`` is the name of a field in the specified
model which relates it to the given node's model.

When this form is used, a ``count_attr`` attribute on each child of the
given node in the drilldown tree will contain a count of the number of
items associated with it through the given foreign key.

If cumulative is also specified, this count will be for items related to
the child node and all of its descendants.

Examples::

   {% drilldown_tree_for_node genre as drilldown %}
   {% drilldown_tree_for_node genre as drilldown count tests.Game.genre in game_count %}
   {% drilldown_tree_for_node genre as drilldown cumulative count tests.Game.genre in game_count %}

See `template tag examples`_ for an example of how to render a drilldown
tree as a nested list.

Filter reference
----------------

``tree_info``
~~~~~~~~~~~~~

Given a list of tree items, iterates over the list, generating
two-tuples of the current tree item and a ``dict`` containing
information about the tree structure around the item, with the following
keys:

   ``'new_level'``
      ``True`` if the current item is the start of a new level in
      the tree, ``False`` otherwise.

   ``'closed_levels'``
      A list of levels which end after the current item. This will
      be an empty list if the next item's level is the same as or
      greater than the level of the current item.

An optional argument can be provided to specify extra details about the
structure which should appear in the ``dict``. This should be a
comma-separated list of feature names. The valid feature names are:

   ancestors
      Adds a list of unicode representations of the ancestors of the
      current node, in descending order (root node first, immediate
      parent last), under the key ``'ancestors'``.

      For example: given the sample tree below, the contents of the list
      which would be available under the ``'ancestors'`` key are given
      on the right::

         Books                    ->  []
            Sci-fi                ->  [u'Books']
               Dystopian Futures  ->  [u'Books', u'Sci-fi']

Using this filter with unpacking in a ``{% for %}`` tag, you should have
enough information about the tree structure to create a hierarchical
representation of the tree.

Example::

   {% for genre,structure in genres|tree_info %}
   {% if structure.new_level %}<ul><li>{% else %}</li><li>{% endif %}
   {{ genre.name }}
   {% for level in structure.closed_levels %}</li></ul>{% endfor %}
   {% endfor %}

``tree_path``
~~~~~~~~~~~~~

Creates a tree path represented by a list of items by joining the items
with a separator, which can be provided as an optional argument,
defaulting to ``' :: '``.

Each path item will be coerced to unicode, so a list of model instances
may be given if required.

Example::

    {{ some_list|tree_path }}
    {{ some_node.get_ancestors|tree_path:" > " }}

Template tag examples
---------------------

An example of the ``drilldown_tree_for_node`` tag and the ``tree_info``
filter being used together to render a drilldown menu for a node, with
cumulative counts of related items being displayed for the node's
children::

   {% drilldown_tree_for_node genre as drilldown cumulative count tests.Game.genre in game_count %}
   {% for node,structure in drilldown|tree_info %}
      {% if structure.new_level %}<ul><li>{% else %}</li><li>{% endif %}
      {% ifequal node genre %}
      <strong>{{ node.name }}</strong>
      {% else %}
      <a href="{{ node.get_absolute_url }}">{{ node.name }}</a>
      {% ifequal node.parent_id genre.pk %}({{ node.game_count }}){% endifequal %}
      {% endifequal %}
      {% for level in structure.closed_levels %}</li></ul>{% endfor %}
   {% endfor %}

An example of the``tree_info`` (with its optional argument) and
``tree_path`` filters being used together to create a multiple select
which doesn't contain root nodes and displays the full path to each
option's node::

   <select name="classifiers" multiple="multiple" size="10">
   {% for node,structure in classifiers|tree_info:"ancestors" %}
   {% if node.is_child_node %}
   <option value="{{ node.pk }}">
   {{ structure.ancestors|tree_path }} :: {{ node }}
   </option>
   {% endif %}
   {% endfor %}
   </select>
