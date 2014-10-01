#!/usr/bin/env python
from __future__ import unicode_literals

from mptt import VERSION

requires = (str('Django>=1.4.2'),)
try:
    from setuptools import setup
    kwargs = {str('install_requires'): requires}
except ImportError:
    from distutils.core import setup
    kwargs = {str('requires'): requires}

# Dynamically calculate the version based on mptt.VERSION
version_tuple = VERSION
version = ".".join(str(v) for v in version_tuple)

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
    packages=[str('mptt'), str('mptt.templatetags')],
    package_data={str('mptt'): [str('templates/admin/*'), str('locale/*/*/*.*')]},
    classifiers=[
        str('Development Status :: 4 - Beta'),
        str('Environment :: Web Environment'),
        str('Framework :: Django'),
        str('Intended Audience :: Developers'),
        str('License :: OSI Approved :: MIT License'),
        str('Operating System :: OS Independent'),
        str('Programming Language :: Python'),
        str("Programming Language :: Python :: 2"),
        str("Programming Language :: Python :: 2.6"),
        str("Programming Language :: Python :: 2.7"),
        str("Programming Language :: Python :: 3"),
        str("Programming Language :: Python :: 3.1"),
        str("Programming Language :: Python :: 3.2"),
        str("Programming Language :: Python :: 3.3"),
        str("Programming Language :: Python :: 3.4"),
        str("Programming Language :: Python :: Implementation :: CPython"),
        str("Programming Language :: Python :: Implementation :: PyPy"),
        str('Topic :: Utilities'),
    ],
    **kwargs
)
