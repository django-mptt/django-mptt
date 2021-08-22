==========
Change log
==========

Next version
============

- Merged the ``docs/upgrade.rst`` file into the main ``CHANGELOG.rst``.
- Fixed the Sphinx autodoc configuration to also work locally. Ensured that
  readthedocs is able to build the docs again.
- Fixed a bug where ``DraggableMPTTAdmin`` assumed that the user model's
  primary key is called ``id``.
- Ensured that we do not install the ``tests.myapp`` package.


0.13
====

- **MARKED THE PROJECT AS UNMAINTAINED, WHICH IT STILL IS**
- Reformatted everything using black, isort etc.
- Switched from Travis CI to GitHub actions.
- Switched to a declarative setup.
- Verified compatibility with Django up to 3.2 and Python up to 3.9. Dropped
  compatibility guarantees (ha!) with anything older than Django 2.2 and Python
  3.6.
- Renamed the main development branch to main.
- Fixed a problem where our ``_get_user_field_names`` mistakenly returned
  abstract fields.
- Added a workaround for the ``default_app_config`` warning.
- Changed saving to always call ``get_ordered_insertion_target`` when using
  ordered insertion.
- Made it possible to override the starting level when using the tree node
  choice field.


0.12
====

- Add support for Django 3.1
- Drop support for Django 1.11.
- Drop support for Python 3.5.
- Fix an issue where the `rebuild()` method would not work correctly if you were using multiple databases.
- Update spanish translations.

0.11
====

- Add support for Django 3.0.
- Add support for Python 3.8.
- Add an admin log message when moving nodes when using the `DraggableMPTTAdmin` admin method.
- Fix `_is_saved` returning `False` when `pk == 0`.
- Add an `all_descendants` argument to `drilldown_tree_for_node`.
- Add traditional Chinese localization.
- properly log error user messages at the error level in the admin.

0.10
====

- Drop support for Pythons 3.4 and Python 2.
- Add support for Python 3.7.
- Add support for Django 2.1 and 2.2.
- Fix `get_cached_trees` to cleanly handle cases where nodes' parents were not included in the original queryset.
- Add a `build_tree_nodes` method to the `TreeManager` Model manager to allow for efficient bulk inserting of a tree (as represented by a bulk dictionary).

0.9.1
=====

Support for Python 3.3 has been removed.
Support for Django 2.1 has been added, support for Django<1.11 is removed.
Support for deprecated South has been removed.

Some updates have been made on the documentation such as:

- Misc updates in the docs (formatting)
- Added italian translation
- Remove unnecessary `db_index=True` from doc examples
- Include on_delete in all TreeForeignKey examples in docs
- Use https:// URLs throughout docs where available
- Document project as stable and ready for use in production
- Add an example of add_related_count usage with the admin
- Updates README.rst with svg badge
- Update tutorial

Bug fixes:

- Fix django-grappelli rendering bug (#661)
- Fixing MPTT models (use explicit db)

Misc:

- Update pypi.python.org URL to pypi.org
- Remove redundant tox.ini options that respecify defaults
- Remove unused argument from `_inter_tree_move_and_close_gap()`
- Trim trailing white space throughout the project
- Pass python_requires argument to setuptools
- Added MpttConfig
- Add test case to support ancestor coercion callbacks. 
- Extend tree_item_iterator with ancestor coercion callback. 

0.9.0
=====

Now supports django 1.11 and 2.0.

Removed tests for unsupported django versions (django 1.9, 1.10)

0.8.6
=====

Now supports django 1.10. After upgrading, you may come across this error when running migrations::

    Unhandled exception in thread started by <function wrapper at 0x7f32e681faa0>
    Traceback (most recent call last):
      #...
      File "venv/lib/python2.7/site-packages/django/db/models/manager.py", line 120, in contribute_to_class
        setattr(model, name, ManagerDescriptor(self))
    AttributeError: can't set attribute

To fix this, please replace ``._default_manager`` in your historic migrations with ``.objects``. For more detailed information see `#469`_, `#498`_

.. _`#469`: https://github.com/django-mptt/django-mptt/issues/469
.. _`#498`: https://github.com/django-mptt/django-mptt/issues/498

0.8.0
=====

Dropped support for old Django versions and Python 2.6
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unsupported versions of django (1.4, 1.5, 1.6, 1.7) are no longer supported, and Python 2.6 is no longer supported.

These versions of python/django no longer receive security patches. You should upgrade to Python 2.7 and Django 1.8+.

Django 1.9 support has been added.

0.7.0
=====

Dropped support for Django 1.5, Added support for 1.8
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Django 1.5 support has been removed since django 1.5 is not supported upstream any longer.

Django 1.8 support has been added.

Deprecated: Calling ``recursetree``/``cache_tree_children`` with incorrectly-ordered querysets
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Previously, when given a queryset argument, ``cache_tree_children`` called ``.order_by`` to ensure that the queryset
was in the correct order. In 0.7, calling ``cache_tree_children`` with an incorrectly-ordered queryset will cause a deprecation warning. In 0.8, it will raise an error.

This also applies to ``recursetree``, since it calls ``cache_tree_children``.

This probably doesn't affect many usages, since the default ordering for mptt models will work fine.

Minor: ``TreeManager.get_queryset`` no longer provided on Django < 1.6
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Django renamed ``get_query_set`` to ``get_queryset`` in Django 1.6. For backward compatibility django-mptt had both methods
available for 1.4-1.5 users.

This has been removed. You should use ``get_query_set`` on Django 1.4-1.5, and ``get_queryset`` if you're on 1.6+.

Removed FeinCMSModelAdmin
~~~~~~~~~~~~~~~~~~~~~~~~~

Deprecated in 0.6.0, this has now been removed.

0.6.0
=====

mptt now requires Python 2.6+, and supports Python 3.2+
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

mptt 0.6 drops support for both Python 2.4 and 2.5.

This was done to make it easier to support Python 3, as well as support the new context managers (delay_mptt_updates and disable_mptt_updates).

If you absolutely can't upgrade your Python version, you'll need to stick to mptt 0.5.5 until you can.

No more implicit ``empty_label=True`` on form fields
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Until 0.5, ``TreeNodeChoiceField`` and ``TreeNodeMultipleChoiceField`` implicitly set ``empty_label=True``.
This was around since a long time ago, for unknown reasons. It has been removed in 0.6.0 as it caused occasional headaches for users.

If you were relying on this behavior, you'll need to explicitly pass ``empty_label=True`` to any of those fields you use,
otherwise you will start seeing new '--------' choices appearing in them.

Deprecated FeinCMSModelAdmin
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you were using ``mptt.admin.FeinCMSModelAdmin``, you should switch to using
``feincms.admin.tree_editor.TreeEditor`` instead, or you'll get a loud deprecation warning.

0.4.2 to 0.5.5
==============

``TreeManager`` is now the default manager, ``YourModel.tree`` removed
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In 0.5, ``TreeManager`` now behaves just like a normal django manager. If you don't override anything,
you'll now get a ``TreeManager`` by default (``.objects``.)

Before 0.5, ``.tree`` was the default name for the ``TreeManager``. That's been removed, so we recommend
updating your code to use ``.objects``.

If you don't want to update ``.tree`` to ``.objects`` everywhere just yet, you should add an explicit ``TreeManager``
to your models::

    objects = tree = TreeManager()

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

.. _`create an issue`: https://github.com/django-mptt/django-mptt/issues
.. _`Django model docs`: https://docs.djangoproject.com/en/dev/topics/db/models/#multiple-inheritance


Compatibility with 0.3
----------------------

``MPTTModel`` was added in 0.4. If you're writing a library or reusable app that needs to work with 0.3,
you should use the ``mptt.register()`` function instead, as above.
