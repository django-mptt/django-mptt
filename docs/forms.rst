==================================
Working with trees in Django forms
==================================

.. contents::
   :depth: 3


Fields
======

The following custom form fields are provided in the ``mptt.forms``
package.

``TreeNodeChoiceField``
-----------------------

This is the default formfield used by ``TreeForeignKey``

A subclass of `ModelChoiceField`_ which represents the tree level of
each node when generating option labels.

For example, where a form which used a ``ModelChoiceField``::

   category = ModelChoiceField(queryset=Category.objects.all())

...would result in a select with the following options::

   ---------
   Root 1
   Child 1.1
   Child 1.1.1
   Root 2
   Child 2.1
   Child 2.1.1

Using a ``TreeNodeChoiceField`` instead::

   category = TreeNodeChoiceField(queryset=Category.objects.all())

...would result in a select with the following options::

   Root 1
   --- Child 1.1
   ------ Child 1.1.1
   Root 2
   --- Child 2.1
   ------ Child 2.1.1

The text used to indicate a tree level can by customised by providing a
``level_indicator`` argument::

   category = TreeNodeChoiceField(queryset=Category.objects.all(),
                                  level_indicator=u'+--')

...which for this example would result in a select with the following
options::

   Root 1
   +-- Child 1.1
   +--+-- Child 1.1.1
   Root 2
   +-- Child 2.1
   +--+-- Child 2.1.1

.. _`ModelChoiceField`: https://docs.djangoproject.com/en/dev/ref/forms/fields/#django.forms.ModelChoiceField

``TreeNodeMultipleChoiceField``
-------------------------------

Just like ``TreeNodeChoiceField``, but accepts more than one value.

``TreeNodePositionField``
-------------------------

A subclass of `ChoiceField`_ whose choices default to the valid arguments
for the `move_to method`_.

.. _`ChoiceField`: https://docs.djangoproject.com/en/dev/ref/forms/fields/#choicefield


Forms
=====

The following custom form is provided in the ``mptt.forms`` package.

``MoveNodeForm``
----------------

A form which allows the user to move a given node from one location in
its tree to another, with optional restriction of the nodes which are
valid target nodes for the `move_to method`

Fields
~~~~~~

The form contains the following fields:

* ``target`` -- a ``TreeNodeChoiceField`` for selecting the target node
  for the node movement.

  Target nodes will be displayed as a single ``<select>`` with its
  ``size`` attribute set, so the user can scroll through the target
  nodes without having to open the dropdown list first.

* ``position`` -- a ``TreeNodePositionField`` for selecting the position
  of the node movement, related to the target node.

Construction
~~~~~~~~~~~~

Required arguments:

``node``
   When constructing the form, the model instance representing the
   node to be moved must be passed as the first argument.

Optional arguments:

``valid_targets``
   If provided, this keyword argument will define the list of nodes
   which are valid for selection in form. Otherwise, any instance of the
   same model class as the node being moved will be available for
   selection, apart from the node itself and any of its descendants.

   For example, if you want to restrict the node to moving within its
   own tree, pass a ``QuerySet`` containing everything in the node's
   tree except itself and its descendants (to prevent invalid moves) and
   the root node (as a user could choose to make the node a sibling of
   the root node).

``target_select_size``
   If provided, this keyword argument will be used to set the size of
   the select used for the target node. Defaults to ``10``.

``position_choices``
   A tuple of allowed position choices and their descriptions.

``level_indicator``
   A string which will be used to represent a single tree level in the
   target options.

``save()`` method
~~~~~~~~~~~~~~~~~

When the form's ``save()`` method is called, it will attempt to perform
the node movement as specified in the form.

If an invalid move is attempted, an error message will be added to the
form's non-field errors (accessible using
``{{ form.non_field_errors }}`` in templates) and the associated
``mptt.exceptions.InvalidMove`` will be re-raised.

It's recommended that you attempt to catch this error and, if caught,
allow your view to to fall through to rendering the form again again, so
the error message is displayed to the user.

Example usage
~~~~~~~~~~~~~

A sample view which shows basic usage of the form is provided below::

   from django.http import HttpResponseRedirect
   from django.shortcuts import render_to_response

   from faqs.models import Category
   from mptt.exceptions import InvalidMove
   from mptt.forms import MoveNodeForm

   def move_category(request, category_pk):
       category = get_object_or_404(Category, pk=category_pk)
       if request.method == 'POST':
           form = MoveNodeForm(category, request.POST)
           if form.is_valid():
               try:
                   category = form.save()
                   return HttpResponseRedirect(category.get_absolute_url())
               except InvalidMove:
                   pass
       else:
           form = MoveNodeForm(category)

       return render_to_response('faqs/move_category.html', {
           'form': form,
           'category': category,
           'category_tree': Category.objects.all(),
       })

.. _`move_to method`: models.html#move-to-target-position-first-child