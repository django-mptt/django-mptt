===================
Models and Managers
===================

.. contents::
   :depth: 3


Setting up a Django model for MPTT
==================================

Start with a basic subclass of MPTTModel, something like this::

    from django.db import models
    from mptt.models import MPTTModel, TreeForeignKey

    class Genre(MPTTModel):
        name = models.CharField(max_length=50, unique=True)
        parent = TreeForeignKey('self', null=True, blank=True, related_name='children', db_index=True)

You must define a parent field which is a ``ForeignKey`` to ``'self'``. Recommended: use ``TreeForeignKey``. You can
call it something different if you want - see `Model Options`_ below.

Because you're inheriting from MPTTModel, your model will also have a number of
other fields: ``level``, ``lft``, ``rght``, and ``tree_id``. Most of the time
you won't need to use these fields directly, but it's helpful to know they're there.

Please note that if you are using multi-inheritance, MPTTModel should usually be the first class to be inherited from::

    class Genre(MPTTModel,Foo,Bar):
        name = models.CharField(max_length=50, unique=True)

Since MPTTModel inherits from ``models.Model``, this is very important when you have "diamond-style" multiple inheritance : you inherit from two Models that both inherit from the same base class (e.g. ``models.Model``) . In that case, If MPTTModel is not the first Model, you may get errors at Model validation, like ``AttributeError: 'NoneType' object has no attribute 'name'``.

Model Options
=============

Sometimes you might want to change the names of the above fields, for instance if
you've already got a field named ``level`` and you want to avoid conflicts.

To change the names, create an ``MPTTMeta`` class inside your class::

    class Genre(MPTTModel):
        name = models.CharField(max_length=50, unique=True)
        parent = TreeForeignKey('self', null=True, blank=True, related_name='children', db_index=True)

        class MPTTMeta:
            level_attr = 'mptt_level'
            order_insertion_by=['name']

The available options for the MPTTMeta class are:

``parent_attr``
   The name of a field which relates the model back to itself such that
   each instance can be a child of another instance. Defaults to
   ``'parent'``.

   Users are responsible for setting this field up on the model class,
   which can be done like so::

      parent = TreeForeignKey('self', null=True, blank=True, related_name='children', db_index=True)

For the following four arguments, if fields with the given names do not
exist, they will be added to the model dynamically:

``left_attr``
   The name of a field which contains the left tree node edge indicator,
   which should be a ``PositiveIntegerField``. Defaults to ``'lft'``.

``right_attr``
   The name of a field which contains the right tree node edge
   indicator, which should be a ``PositiveIntegerField``. Defaults to
   ``'rght'``.

``tree_id_attr``
   The name of a field which contains the tree id of each node, which
   should be a ``PositiveIntegerField``. Defaults to ``'tree_id'``.

   Items which do not have a parent are considered to be "root" nodes in
   the tree and will be allocated a new tree id. All descendants of root
   nodes will be given the same tree id as their root node.

``level_attr``
   The name of a field which contains the (zero-based) level at which an
   item sits in the tree, which should be a ``PositiveIntegerField``.
   Defaults to ``'level'``.

   For example, root nodes would have a level of ``0`` and their
   immediate children would have have a level of ``1``.

``order_insertion_by``
   A list of field names which should define ordering when new tree
   nodes are being inserted or existing nodes are being reparented, with
   the most significant ordering field name first. Defaults to ``[]``.

   It is assumed that any field identified as defining ordering will
   never be ``NULL`` in the database.

   Note that this will require an extra database query to determine
   where nodes should be positioned when they are being saved. This
   option is handy if you're maintaining mostly static structures, such
   as trees of categories, which should always be in alphabetical order.


Registration of existing models
===============================

The preferred way to do model registration in ``django-mptt`` is by subclassing ``MPTTModel``.

However, sometimes that doesn't quite work. For instance, suppose you want to modify Django's Group model to be hierarchical.

You can't subclass MPTTModel without modifying the Group source. Instead, you can do::

    import mptt
    from mptt.fields import TreeForeignKey
    from django.contrib.auth.models import Group

    # add a parent foreign key
    TreeForeignKey(Group, blank=True, null=True, db_index=True).contribute_to_class(Group, 'parent')

    mptt.register(Group, order_insertion_by=['name'])


MPTTModel instance methods
==========================

Subclasses of MPTTModel have the following instance methods:

``get_ancestors(ascending=False, include_self=False)``
------------------------------------------------------

Creates a ``QuerySet`` containing the ancestors of the model instance.

These default to being in descending order (root ancestor first,
immediate parent last); passing ``True`` for the ``ascending`` argument
will reverse the ordering (immediate parent first, root ancestor last).

If ``include_self`` is ``True``, the ``QuerySet`` will also include the
model instance itself.

Raises a ``ValueError`` if the instance isn't saved already.


``get_children()``
------------------

Creates a ``QuerySet`` containing the immediate children of the model
instance, in tree order.

The benefit of using this method over the reverse relation provided by
the ORM to the instance's children is that a database query can be
avoided in the case where the instance is a leaf node (it has no
children).

Raises a ``ValueError`` if the instance isn't saved already.


``get_descendants(include_self=False)``
---------------------------------------

Creates a ``QuerySet`` containing descendants of the model instance, in
tree order.

If ``include_self`` is ``True``, the ``QuerySet`` will also include the
model instance itself.

Raises a ``ValueError`` if the instance isn't saved already.


``get_descendant_count()``
--------------------------

Returns the number of descendants the model instance has, based on its
left and right tree node edge indicators. As such, this does not incur
any database access.

``get_family()``
----------------

Returns a ``QuerySet`` containing the ancestors, the model itself
and the descendants, in tree order.

Raises a ``ValueError`` if the instance isn't saved already.


``get_next_sibling()``
----------------------

Returns the model instance's next sibling in the tree, or ``None`` if it
doesn't have a next sibling.

Raises a ``ValueError`` if the instance isn't saved already.


``get_previous_sibling()``
--------------------------

Returns the model instance's previous sibling in the tree, or ``None``
if it doesn't have a previous sibling.

Raises a ``ValueError`` if the instance isn't saved already.


``get_root()``
--------------

Returns the root node of the model instance's tree.

Raises a ``ValueError`` if the instance isn't saved already.


``get_siblings(include_self=False)``
------------------------------------

Creates a ``QuerySet`` containing siblings of the model instance. Root
nodes are considered to be siblings of other root nodes.

If ``include_self`` is ``True``, the ``QuerySet`` will also include the
model instance itself.

Raises a ``ValueError`` if the instance isn't saved already.


``insert_at(target, position='first-child', save=False)``
-----------------------------------------------------------

Positions the model instance (which must not yet have been inserted into
the database) in the tree based on ``target`` and ``position`` (when
appropriate).

If ``save`` is True, the model instance's ``save()`` method will also be
called.

``is_child_node()``
-------------------

Returns ``True`` if the model instance is a child node, ``False``
otherwise.

``is_leaf_node()``
------------------

Returns ``True`` if the model instance is a leaf node (it has no
children), ``False`` otherwise.

``is_root_node()``
------------------

Returns ``True`` if the model instance is a root node, ``False``
otherwise.

.. _`move_to documentation`:

``move_to(target, position='first-child')``
-------------------------------------------

Moves the model instance elsewhere in the tree based on ``target`` and
``position`` (when appropriate). If moved without any exceptions
raised then the signal ``node_moved`` will be sent.

.. note::
   It is assumed that when you call this method, the tree fields in the
   instance you've called it on, and in any ``target`` instance passed
   in, reflect the current state of the database.

   Modifying the tree fields manually before calling this method or
   using tree fields which are out of sync with the database can result
   in the tree structure being put into an inaccurate state.

If ``target`` is another model instance, it will be used to determine
the type of movement which needs to take place, and will be used as the
basis for positioning the model when it is moved, in combination with
the ``position`` argument.

A ``target`` of ``None`` indicates that the model instance should be
turned into a root node. The ``position`` argument is disregarded in
this case.

Valid values for the ``position`` argument and their effects on movement
are:

   ``'first-child'``
      The instance being moved should have ``target`` set as its new
      parent and be placed as its *first* child in the tree structure.

   ``'last-child'``
      The instance being moved should have ``target`` set as its new
      parent and be placed as its *last* child in the tree structure.

   ``'left'``
      The instance being moved should have ``target``'s parent set as
      its new parent and should be placed *directly before* ``target``
      in the tree structure.

   ``'right'``
      The instance being moved should have ``target``'s parent set as
      its new parent and should be placed *directly after* ``target``
      in the tree structure.

A ``ValueError`` will be raised if an invalid value is given for the
``position`` argument.

Note that some of the moves you could attempt to make with this method
are invalid - for example, trying to make an instance be its own
child or the child of one of its descendants. In these cases, a
``mptt.exceptions.InvalidMove`` exception will be raised.

The instance itself will be also modified as a result of this call, to
reflect the state of its updated tree fields in the database, so it's
safe to go on to save it or use its tree fields after you've called this
method.


``TreeForeignKey``, ``TreeOneToOneField``, ``TreeManyToManyField``
==================================================================

.. versionadded:: 0.5

It's recommended you use ``mptt.fields.TreeForeignKey`` wherever you have a
foreign key to an MPTT model. This includes the ``parent`` link you've just
created on your model.

``TreeForeignKey`` is just like a regular ``ForeignKey`` but it makes the default
form field display choices in tree form.

There are also ``TreeOneToOneField`` and ``TreeManyToManyField`` if you need them.
These may come in useful on other models that relate to your tree model in some way.


.. note::
   You can't use a many-to-many as your 'parent' field. That's because
   the mptt algorithm only handles trees, not arbitrary graphs. A tree where nodes
   can have multiple parents isn't really a tree at all.


The ``TreeManager`` custom manager
==================================

The default manager for an MPTTModel is a ``TreeManager``.

Any ``QuerySet`` created with this manager will be ordered based on the
tree structure, with root nodes appearing in tree id order and their
descendants being ordered in a depth-first fashion.

Methods
-------

The following manager methods are available:

``disable_mptt_updates()`` and ``delay_mptt_updates()``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

These two methods return context managers, and are both for doing efficient bulk updates of large trees.
See the autogenerated docs for more information:

 * `delay_mptt_updates`_
 * `disable_mptt_updates`_

.. _`delay_mptt_updates`: mptt.managers.html#mptt.managers.TreeManager.delay_mptt_updates
.. _`disable_mptt_updates`: mptt.managers.html#mptt.managers.TreeManager.disable_mptt_updates

``rebuild()``
~~~~~~~~~~~~~

Rebuilds the mptt fields for the entire table. This can be handy:

 * if your tree gets corrupted somehow.
 * After large bulk operations, when you've used ``disable_mptt_updates``

It is recommended to rebuild the tree inside a ``transaction.atomic()`` block
for safety and better performance.

``add_related_count(queryset, rel_cls, rel_field, count_attr, cumulative=False)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Adds a related item count to a given ``QuerySet`` using its
`extra method`_, for a model which has a relation to this manager's
model.

``rel_cls``
   A Django model class which has a relation to this manager's model.

``rel_field``
   The name of the field in ``rel_cls`` which holds the relation.

``count_attr``
   The name of an attribute which should be added to each item in this
   ``QuerySet``, containing a count of how many instances of ``rel_cls``
   are related to it through ``rel_field``.

``cumulative``
   If ``True``, the count will be for each item and all of its
   descendants, otherwise it will be for each item itself.


Example usage in the admin
--------------------------

::

    from mptt.admin import DraggableMPTTAdmin
    from .models import Category, Product


    class CategoryAdmin(DraggableMPTTAdmin):
        mptt_indent_field = "name"
        list_display = ('tree_actions', 'indented_title', 
                        'related_products_count', 'related_products_cumulative_count')
        list_display_links = ('indented_title',)
    
        def get_queryset(self, request):
            qs = super().get_queryset(request)
    
            # Add cumulative product count
            qs = Category.objects.add_related_count(
                    qs,
                    Product,
                    'category',
                    'products_cumulative_count',
                    cumulative=True)
    
            # Add non cumulative product count
            qs = Category.objects.add_related_count(qs,
                     Product,
                     'categories',
                     'products_count',
                     cumulative=False)
            return qs
    
        def related_products_count(self, instance):
            return instance.products_count
        related_product_count.short_description = 'Related products (for this specific category)'
    
        def related_products_cumulative_count(self, instance):
            return instance.products_cumulative_count
        related_products_cumulative_count.short_description = 'Related products (in tree)'



``root_node(tree_id)``
~~~~~~~~~~~~~~~~~~~~~~

Returns the root node of tree with the given id.

``insert_node(node, target, position='last-child', save=False)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Sets up the tree state for ``node`` (which has not yet been inserted
into in the database) so it will be positioned relative to a given
``target`` node as specified by ``position`` (when appropriate) when it
is inserted, with any neccessary space already having been made for it.

A ``target`` of ``None`` indicates that ``node`` should be the last root
node.

If ``save`` is ``True``, ``node``'s ``save()`` method will be called
before it is returned.

``move_node(node, target, position='last-child')``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Moves ``node`` based on ``target``, relative to ``position`` when
appropriate.

A ``target`` of ``None`` indicates that ``node`` should be removed from
its current position and turned into a root node. If ``node`` is a root
node in this case, no action will be taken.

The given ``node`` will be modified to reflect its new tree state in the
database.

For more details, see the `move_to documentation`_ above.

``root_nodes()``
~~~~~~~~~~~~~~~~

Creates a ``QuerySet`` containing root nodes.

.. _`extra method`: https://docs.djangoproject.com/en/dev/ref/models/querysets/#extra-select-none-where-none-params-none-tables-none-order-by-none-select-params-none

Example usage
-------------

In the following examples, we have ``Category`` and ``Question`` models.
``Question`` has a ``category`` field which is a ``TreeForeignKey`` to
``Category``.

Retrieving a list of root Categories which have a ``question_count``
attribute containing the number of Questions associated with each root
and all of its descendants::

   roots = Category.objects.add_related_count(Category.objects.root_nodes(), Question,
                                           'category', 'question_counts',
                                           cumulative=True)

Retrieving a list of child Categories which have a ``question_count``
attribute containing the number of Questions associated with each of
them::

   node = Category.objects.get(name='Some Category')
   children = Category.objects.add_related_count(node.get_children(), Question,
                                              'category', 'question_counts')
