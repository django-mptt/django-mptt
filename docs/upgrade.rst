=============
Upgrade notes
=============

Development version - since 0.4.2
=================================

``save(raw=True)`` keyword argument removed
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In earlier versions, MPTTModel.save() had a ``raw`` keyword argument.
If True, the MPTT fields would not be updated during the save.
This (undocumented) argument has now been removed.

``_meta`` attributes moved to ``_mptt_meta``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In 0.4, we deprecated all these attributes on model._meta. These have now been removed::

    MyModel._meta.left_attr
    MyModel._meta.right_attr
    MyModel._meta.tree_id_attr
    MyModel._meta.level_attr
    MyModel._meta.tree_manager_attr
    MyModel._meta.parent_attr
    MyModel._meta.order_insertion_by

If you're still using any of these, you'll need to update by simply renaming ``_meta`` to ``_mptt_meta``.

Running the tests
~~~~~~~~~~~~~~~~~

Tests are now run with::

    cd tests/
    ./runtests.sh

The previous method (``python setup.py test``) no longer works since we switched to plain distutils.

0.3 to 0.4.2
============


Model changes
~~~~~~~~~~~~~

MPTT attributes on ``MyModel._meta`` deprecated, moved to ``MyModel._mptt_meta``
----------------------------------------------------------------------------------

Most people won't need to worry about this, but if you're using any of the following, note that these are deprecated and will be removed in 0.5::

    MyModel._meta.left_attr
    MyModel._meta.right_attr
    MyModel._meta.tree_id_attr
    MyModel._meta.level_attr
    MyModel._meta.tree_manager_attr
    MyModel._meta.parent_attr
    MyModel._meta.order_insertion_by

They'll continue to work as previously for now, but you should upgrade your code if you can. Simply replace ``_meta`` with ``_mptt_meta``.


Use model inheritance where possible
------------------------------------

The preferred way to do model registration in ``django-mptt`` 0.4 is via model inheritance.

Suppose you start with this::

    class Node(models.Model):
        ...
    
    mptt.register(Node, order_insertion_by=['name'], parent_attr='padre')


First, Make your model a subclass of ``MPTTModel``, instead of ``models.Model``::

    from mptt.models import MPTTModel
    
    class Node(MPTTModel):
        ...

Then remove your call to ``mptt.register()``. If you were passing it keyword arguments, you should add them to an ``MPTTMeta`` inner class on the model::

    class Node(MPTTModel):
        ...
        class MPTTMeta:
            order_insertion_by = ['name']
            parent_attr = 'padre'

If necessary you can still use ``mptt.register``. It was removed in 0.4.0 but restored in 0.4.2, since people reported use cases that didn't work without it.)

For instance, if you need to register models where the code isn't under your control, you'll need to use ``mptt.register()``.

Behind the scenes, ``mptt.register()`` in 0.4 will actually add MPTTModel to ``Node.__bases__``,
thus achieving the same result as subclassing ``MPTTModel``.
If you're already inheriting from something other than ``Model``, that means multiple inheritance.

You're probably all upgraded at this point :) A couple more notes for more complex scenarios:


More complicated scenarios
~~~~~~~~~~~~~~~~~~~~~~~~~~

What if I'm already inheriting from something?
----------------------------------------------

If your model is already a subclass of an abstract model, you should use multiple inheritance::

    class Node(MPTTModel, ParentModel):
        ...

You should always put MPTTModel as the first model base. This is because there's some
complicated metaclass stuff going on behind the scenes, and if Django's model metaclass
gets called before the MPTT one, strange things can happen.

Isn't multiple inheritance evil? Well, maybe. However, the 
`Django model docs`_ don't forbid this, and as long as your other model doesn't have conflicting methods, it should be fine.

.. note::
   As always when dealing with multiple inheritance, approach with a bit of caution.
   
   Our brief testing says it works, but if you find that the Django internals are somehow
   breaking this approach for you, please `create an issue`_ with specifics.

.. _`create an issue`: http://github.com/django-mptt/django-mptt/issues
.. _`Django model docs`: http://docs.djangoproject.com/en/dev/topics/db/models/#multiple-inheritance


Compatibility with 0.3
----------------------

``MPTTModel`` was added in 0.4. If you're writing a library or reusable app that needs to work with 0.3,
you should use the ``mptt.register()`` function instead, as above.
