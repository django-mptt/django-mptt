
========
Tutorial
========


The Problem
===========

You've created a Django project, and you need to manage some hierarchical data. For instance you've got a bunch of hierarchical pages in a CMS, and sometimes pages are *chidren* of other pages

Now suppose you want to show a breadcrumb on your site, like this::

    Home > Products > Food > Meat > Spam > Spammy McDelicious

To get all those page titles you might do something like this::

    titles = []
    while page:
        titles.append(page.title)
        page = page.parent

That's one database query for each page in the breadcrumb, and database queries are slow. Let's do this a better way.


The Solution
============

Modified Preorder Tree Traversal can be a bit daunting at first, but it's one of the best ways to solve this problem.

If you want to go into the details, there's a good explanation here: `Storing Hierarchical Data in a Database`_

tl;dr: MPTT makes most tree operations much cheaper in terms of queries. In fact all these operations take at most one query, and sometimes zero:
 * get descendents of a node
 * get ancestors of a node
 * get all nodes at a given level
 * get leaf nodes

And this one takes zero queries:
 * count the descendents of a given node

.. _`Storing Hierarchical Data in a Database`: http://www.sitepoint.com/hierarchical-data-database/

Enough intro. Let's get started.


Getting started
===============


Add ``mptt`` To ``INSTALLED_APPS``
----------------------------------

As with most Django applications, you should add ``mptt`` to the ``INSTALLED_APPS`` in your ``settings.py`` file::

    INSTALLED_APPS = (
        'django.contrib.auth',
        # ...
        'mptt',
    )


Set up your model
-----------------

Start with a basic subclass of MPTTModel, something like this::
   
    from django.db import models
    from mptt.models import MPTTModel, TreeForeignKey
    
    class Genre(MPTTModel):
        name = models.CharField(max_length=50, unique=True)
        parent = TreeForeignKey('self', null=True, blank=True, related_name='children')

        class MPTTMeta:
            order_insertion_by = ['name']

You must define a parent field which is a ``TreeForeignKey`` to ``'self'``. A ``TreeForeignKey`` is just a regular ``ForeignKey`` that renders form fields differently in the admin and a few other places.

Because you're inheriting from MPTTModel, your model will also have a number of
other fields: ``level``, ``lft``, ``rght``, and ``tree_id``. These fields are managed by the MPTT algorithm. Most of the time you won't need to use these fields directly.

That ``MPTTMeta`` class adds some tweaks to ``django-mptt`` - in this case, just ``order_insertion_by``. This indicates the natural ordering of the data in the tree.

Now create your table in the database::

    python manage.py syncdb


Create some data
----------------

Fire up a django shell::

    python manage.py shell

Now create some data to test::

    from myapp.models import Genre
    rock = Genre.objects.create(name="Rock")
    blues = Genre.objects.create(name="Blues")
    Genre.objects.create(name="Hard Rock", parent=rock)
    Genre.objects.create(name="Pop Rock", parent=rock)

Make a view
-----------

This one's pretty simple for now. Add this lightweight view to your ``views.py``::

    def show_genres(request):
        return render_to_response("genres.html",
                              {'nodes':Genre.objects.all()},
                              context_instance=RequestContext(request))

And add a URL for it in ``urls.py``::

    (r'^genres/$', 'myapp.views.show_genres'),

Template
--------
.. highlightlang:: html+django

``django-mptt`` includes some template tags for making this bit easy too.
Create a template called ``genres.html`` in your template directory and put this in it::

    {% load mptt_tags %}
    <ul>
        {% recursetree nodes %}
            <li>
                {{ node.name }}
                {% if not node.is_leaf_node %}
                    <ul class="children">
                        {{ children }}
                    </ul>
                {% endif %}
            </li>
        {% endrecursetree %}
    </ul>

That recursetree tag will recursively render that template fragment for all the nodes. Try it out by going to ``/genres/``.

There's more; `check out the docs`_ for custom admin-site stuff, more template tags, tree rebuild functions etc.

Now you can stop thinking about how to do trees, and start making a great django app!

.. _`check out the docs`: http://django-mptt.github.com/django-mptt/