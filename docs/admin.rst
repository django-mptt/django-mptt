=============
Admin classes
=============

``mptt.admin.MPTTModelAdmin``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This is a bare-bones tree admin. All it does is enforce ordering, and indent the nodes
in the tree to make a pretty tree list view.

Usage::

    from django.contrib import admin
    from mptt.admin import MPTTModelAdmin
    from myproject.myapp.models import Node

    admin.site.register(Node, MPTTModelAdmin)

You can change the indent pixels per level globally by putting this in your
settings.py::

    # default is 10 pixels
    MPTT_ADMIN_LEVEL_INDENT = 20

If you'd like to specify the pixel amount per Model, define an ``mptt_level_indent``
attribute in your MPTTModelAdmin::

    from django.contrib import admin
    from mptt.admin import MPTTModelAdmin
    from myproject.myapp.models import Node

    class CustomMPTTModelAdmin(MPTTModelAdmin):
        # specify pixel amount for this ModelAdmin only:
        mptt_level_indent = 20

    admin.site.register(Node, CustomMPTTModelAdmin)

If you'd like to specify which field should be indented, add an ``mptt_indent_field``
to your MPTTModelAdmin::

    # …
    class CustomMPTTModelAdmin(MPTTModelAdmin):
        mptt_indent_field = "some_node_field"
    # …


``mptt.admin.DraggableMPTTAdmin``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 0.9

This is a tree admin based on `FeinCMS <http://feincms.org/>`_ offering
drag-drop functionality for moving nodes.

.. warning::

   Does not work well with big trees (more than a few hundred nodes, or trees
   deeper than 10 levels). Patches implementing lazy-loading of deep trees
   are very much appreciated.

``DraggableMPTTAdmin.list_per_page`` is set to 2000 by default (which
effectively disables pagination for most trees).

Usage::

    from django.contrib import admin
    from mptt.admin import DraggableMPTTAdmin
    from myproject.myapp.models import Node

    admin.site.register(
        Node,
        DraggableMPTTAdmin,
        list_display=(
            'tree_actions',
            'indented_title',
            # ...more fields if you feel like it...
        ),
        list_display_links=(
            'indented_title',
        ),
    )

You should ensure that ``'tree_actions'`` is always the first value
passed  to ``list_display``. ``indented_title`` does nothing but return
the indented self-description of nodes, ``20px`` per level. Also, always
specify ``list_display_links``.


Replacing ``indented_title``
----------------------------

If you want to replace the ``indented_title`` method with your own, we
recommend using the following code::

    from django.utils.html import format_html

    class MyDraggableMPTTAdmin(DraggableMPTTAdmin):
        list_display = ('tree_actions', 'something')
        list_display_links = ('something',)

        def something(self, instance):
            return format_html(
                '<div style="text-indent:{}px">{}</div>',
                instance._mpttfield('level') * self.mptt_level_indent,
                item.name,  # Or whatever you want to put here
            )
        something.short_description = _('something nice')

For changing the indentation per node, look below. Simply replacing
``indented_title`` is insufficient because the indentation also needs
to be communicated to the JavaScript code.


Overriding admin templates per app or model
-------------------------------------------

The ``DraggableMPTTAdmin`` comes with a customized template for the admin
change list. The following template paths may be used to further customize
the template used:

- ``admin/<app_label>/<model_name>/draggable_mptt_change_list.html``
- ``admin/<app_label>/draggable_mptt_change_list.html``
- ``admin/draggable_mptt_change_list.html`` (this template is provided by
  django-mptt)


Changing the indentation of nodes
---------------------------------

Simply set ``mptt_level_indent`` to a different pixel value (defaults
to ``20``)::

    # ...
    class MyDraggableMPTTAdmin(DraggableMPTTAdmin):
        mptt_level_indent = 50
    # ...
