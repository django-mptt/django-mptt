=============
Admin classes
=============

``mptt.admin.MPTTModelAdmin``
-----------------------------

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
---------------------------------

This is a tree admin based on `FeinCMS <http://feincms.org/>`_ offering
drag-drop functionality for moving nodes.

.. warning::

   Does not work well with big trees (more than a few hundred nodes, or trees
   deeper than 10 levels). Patches implementing lazy-loading of deeper nodes
   very much appreciated.

Usage::

    from django.contrib import admin
    from mptt.admin import DraggableMPTTAdmin
    from myproject.myapp.models import Node

    class NodeAdmin(DraggableMPTTAdmin):
        list_per_page = 99999  # See the note above.

    admin.site.register(Node, NodeAdmin)
