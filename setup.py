#!/usr/bin/env python
from __future__ import unicode_literals
from distutils.core import setup

from mptt import VERSION

# Dynamically calculate the version based on mptt.VERSION
version_tuple = VERSION
version = ".".join([str(v) for v in version_tuple])


# on py3, all these are text strings
# on py2, they're all byte strings.
# ... and that's how setuptools likes it.
setup(
    name=str('django-mptt'),
    description=str('''Utilities for implementing Modified Preorder Tree Traversal
        with your Django Models and working with trees of Model instances.'''),
    version=version,
    author=str('Craig de Stigter'),
    author_email=str('craig.ds@gmail.com'),
    url=str('http://github.com/django-mptt/django-mptt'),
    packages=[str('mptt'), str('mptt.templatetags'), str('mptt.vendor')],
    package_data={str('mptt'): [str('templates/admin/*'), str('locale/*/*/*.*')]},
    classifiers=[
        str('Development Status :: 4 - Beta'),
        str('Environment :: Web Environment'),
        str('Framework :: Django'),
        str('Intended Audience :: Developers'),
        str('License :: OSI Approved :: BSD License'),
        str('Operating System :: OS Independent'),
        str('Programming Language :: Python'),
        str('Topic :: Utilities'),
    ],
)
