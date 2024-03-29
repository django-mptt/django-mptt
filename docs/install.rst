============
Installation
============

.. contents::
   :depth: 3

Official releases
=================

Official releases are available from `PyPI`_. You can install it using the `pip`::

   pip install django-mptt

You can also download the .zip distribution file and unpack it. Inside is a script
named ``setup.py``. Enter this command::

   python setup.py install

...and the package will install automatically.

.. _`PyPI`: https://pypi.org/project/django-mptt/
.. _`pip`: https://pip.pypa.io/en/stable/


Development version
===================

Alternatively, you can get the latest source from our `git`_ repository::

   git clone git://github.com/django-mptt/django-mptt.git django-mptt

Add the resulting folder to your `PYTHONPATH`_ or symlink the ``mptt`` directory
inside it into a directory which is on your PYTHONPATH, such as your Python
installation's ``site-packages`` directory.

You can verify that the application is available on your PYTHONPATH by
opening a Python interpreter and entering the following commands::

   >>> import mptt
   >>> mptt.__version__
   '0.14.0'

When you want to update your copy of the source code, run ``git pull``
from within the ``django-mptt`` directory.

.. caution::

   The development version may contain bugs which are not present in the
   release version and introduce backwards-incompatible changes.

   If you're tracking master, keep an eye on the recent `Commit History`_
   before you update your copy of the source code.

.. _`git`: https://git-scm.com/
.. _`PYTHONPATH`: http://docs.python.org/tut/node8.html#SECTION008110000000000000000
.. _`Commit History`: https://github.com/django-mptt/django-mptt/commits/master
