Change log
==========

Next version
~~~~~~~~~~~~

0.12
~~~~

- Add support for Django 3.1
- Drop support for Django 1.11.
- Drop support for Python 3.5.
- Fix an issue where the `rebuild()` method would not work correctly if you were using multiple databases.
- Update spanish translations.

0.11
~~~~

- Add support for Django 3.0.
- Add support for Python 3.8.
- Add an admin log message when moving nodes when using the `DraggableMPTTAdmin` admin method.
- Fix `_is_saved` returning `False` when `pk == 0`.
- Add an `all_descendants` argument to `drilldown_tree_for_node`.
- Add traditional Chinese localization.
- properly log error user messages at the error level in the admin.

0.10
~~~~

- Drop support for Pythons 3.4 and Python 2.
- Add support for Python 3.7.
- Add support for Django 2.1 and 2.2.
- Fix `get_cached_trees` to cleanly handle cases where nodes' parents were not included in the original queryset.
- Add a `build_tree_nodes` method to the `TreeManager` Model manager to allow for efficient bulk inserting of a tree (as represented by a bulk dictionary).


Older versions
~~~~~~~~~~~~~~

See the `Upgrade notes
<https://django-mptt.readthedocs.io/en/latest/upgrade.html>`__ section
in the docs.
