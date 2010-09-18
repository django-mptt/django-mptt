==========================
How to install Django MPTT
==========================

.. admonition:: About this document

   This document describes how to install Django MPTT and use it in your
   Django applications.

.. contents::
   :depth: 3

Installing an official release
==============================

Official releases are made available from
http://code.google.com/p/django-mptt/

Source distribution
-------------------

Download the .zip distribution file and unpack it. Inside is a script
named ``setup.py``. Enter this command::

   python setup.py install

...and the package will install automatically.


Installing the development version
==================================

Alternatively, you can get the latest source from our `git`_ repository::

   git clone git://github.com/django-mptt/django-mptt.git django-mptt

Add the resulting folder to your `PYTHONPATH`_ or symlink (`junction`_,
if you're on Windows) the ``mptt`` directory inside it into a directory
which is on your PYTHONPATH, such as your Python installation's
``site-packages`` directory.

You can verify that the application is available on your PYTHONPATH by
opening a Python interpreter and entering the following commands::

   >>> import mptt
   >>> mptt.VERSION
   (0, 4, 'pre')

When you want to update your copy of the source code, run ``git pull``
from within the ``django-mptt`` directory.

.. caution::

   The development version may contain bugs which are not present in the
   release version and introduce backwards-incompatible changes.

   If you're tracking master, keep an eye on the recent `Commit History`_ and the
   `backwards-incompatible changes wiki page`_ before you update your
   copy of the source code.

.. _`git`: http://git-scm.com/
.. _`PYTHONPATH`: http://docs.python.org/tut/node8.html#SECTION008110000000000000000
.. _`junction`: http://www.microsoft.com/technet/sysinternals/FileAndDisk/Junction.mspx
.. _`Commit History`: http://github.com/django-mptt/django-mptt/commits/master
.. _`backwards-incompatible changes wiki page`: http://code.google.com/p/django-mptt/wiki/BackwardsIncompatibleChanges


Using Django MPTT in your applications
======================================

Once you've installed Django MPTT and want to use it in your Django
applications, do the following:

   1. Put ``'mptt'`` in your ``INSTALLED_APPS`` setting.
   2. Subclass MPTTModel, like this::
   
       from django.db import models
       from mptt.models import MPTTModel
       
       class MyTreeNode(MPTTModel):
           name = models.CharField(max_length=30)
           parent = models.ForeignKey('self', related_name='children')

That's it!

To customize your model further, have a look at the `models documentation`.

.. _`models documentation`: models.html
