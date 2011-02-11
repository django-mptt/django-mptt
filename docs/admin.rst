=============
Admin classes
=============

.. versionadded:: 0.4

To add admin functionality to your tree model, use one of the ``ModelAdmin``
classes in ``django-mptt.admin``:

MPTTModelAdmin
--------------

This is a bare-bones tree admin. All it does is enforce ordering, and indent the nodes 
in the tree to make a pretty tree list view.

Usage::

    from django.contrib import admin
    from mptt.admin import MPTTModelAdmin
    from myproject.myapp.models import Node

    admin.site.register(Node, MPTTModelAdmin)

You can change the indent pixels per level by putting this in your settings.py::

    # default is 10 pixels
    MPTT_ADMIN_LEVEL_INDENT = 20

If you'd like to specify which field should be indented, add an `mptt_indent_field` 
to your MPTTModelAdmin: 

    from django.contrib import admin
    from mptt.admin import MPTTModelAdmin
    from myproject.myapp.models import Node

    class CustomMPTTModelAdmin(MPTTModelAdmin)
        mptt_indent_field = "some_node_field"

    admin.site.register(Node, CustomMPTTModelAdmin)

FeinCMSModelAdmin
-----------------

This requires `FeinCMS`_ to be installed.

In addition to enforcing ordering and indenting the nodes, it has:

 - Javascript expand/collapse for parent nodes
 - Javascript widgets for moving nodes on the list view page

.. _`FeinCMS`: http://www.feinheit.ch/labs/feincms-django-cms/
