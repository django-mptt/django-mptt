========
Tutorial
========


The Problem
===========

You've created a Django project, and you need to manage some hierarchical data. For instance you've got a bunch of hierarchical pages in a CMS, and sometimes pages are *children* of other pages

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

If you want to go into the details, there's a good explanation here: `Storing Hierarchical Data in a Database`_ or `Managing Hierarchical Data in Mysql`_

tl;dr: MPTT makes most tree operations much cheaper in terms of queries. In fact all these operations take at most one query, and sometimes zero:
 * get descendants of a node
 * get ancestors of a node
 * get all nodes at a given level
 * get leaf nodes

And this one takes zero queries:
 * count the descendants of a given node

.. _`Storing Hierarchical Data in a Database`: https://www.sitepoint.com/hierarchical-data-database/
.. _`Managing Hierarchical Data in Mysql`: http://mikehillyer.com/articles/managing-hierarchical-data-in-mysql/

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
        parent = TreeForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')

        class MPTTMeta:
            order_insertion_by = ['name']

You must define a parent field which is a ``TreeForeignKey`` to ``'self'``. A ``TreeForeignKey`` is just a regular ``ForeignKey`` that renders form fields differently in the admin and a few other places.

Because you're inheriting from MPTTModel, your model will also have a number of
other fields: ``level``, ``lft``, ``rght``, and ``tree_id``. These fields are managed by the MPTT algorithm. Most of the time you won't need to use these fields directly.

That ``MPTTMeta`` class adds some tweaks to ``django-mptt`` - in this case, just ``order_insertion_by``. This indicates the natural ordering of the data in the tree.

Now create and apply the migrations to create the table in the database::

    python manage.py makemigrations <your_app>
    python manage.py migrate


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
        return render(request, "genres.html", {'genres': Genre.objects.all()})

And add a URL for it in ``urls.py``::

    (r'^genres/$', show_genres),

Template
--------

``django-mptt`` includes some template tags for making this bit easy too.
Create a template called ``genres.html`` in your template directory and put this in it::

    {% load mptt_tags %}
    <ul>
        {% recursetree genres %}
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

.. _order_insertion_by_gotcha:

``order_insertion_by`` gotcha
-----------------------------

In the example above, we used ``order_insertion_by`` option, which makes ``django-mptt`` order items
in the tree automatically, using ``name`` key. What does this mean, technically? Well, in case you add
items in an unordered manner, ``django-mptt`` will update the database, so they will be ordered
in the tree.

So why this is exactly a gotcha?

Well, it is not. As long as you don't keep instances with references to old data. But chances are
you do keep them and you don't even know about this.

In case you do, you will need to reload your items from the database, or else you will be left
with strange bugs, looking like data inconsistency.

The sole reason behind that is we can't actually tell Django to reload every single instance
of ``django.db.models.Model`` based on the table row. You will need to reload manually, by
calling `Model.refresh_from_db()`_.

For example, using that model from the previous code snippet:

.. python::

>>> root = Genre.objects.create(name="")
#
# Bear in mind, that we're going to add children in an unordered
# manner:
#
>>> b = OrderedInsertion.objects.create(name="b", parent=root)
>>> a = OrderedInsertion.objects.create(name="a", parent=root)
#
# At this point, the tree will be reorganized in the database
# and unless you will refresh the 'b' instance, it will be left
# containing old data, which in turn will lead to bugs like:
#
>>> a in a.get_ancestors(include_self=True)
True
>>> b in b.get_ancestors(include_self=True)
False
#
# What? That's wrong! Let's reload
#
>>> b.refresh_from_db()
>>> b in b.get_ancestors(include_self=True)
True
# Everything's back to normal.

.. _`Model.refresh_from_db()`: https://docs.djangoproject.com/en/dev/ref/models/instances/#refreshing-objects-from-database
