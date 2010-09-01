"""
Django mptt setup file
"""
import os
from setuptools import setup, find_packages

# Dynamically calculate the version based on mptt.VERSION
version_tuple = __import__('mptt').VERSION
version = "%d.%d.%d" % version_tuple

setup(
    name = 'django-mptt-2',
    description = '''Utilities for implementing Modified Preorder Tree
    Traversal with your Django Models and working with trees of Model instances.
    This package is maintained for Django 1.1.1 and the incoming 1.2''',
    version = version,
    author = 'Jonathan Buchanan',
    author_email = 'batiste.bieler@gmail.com',
    url = 'http://github.com/batiste/django-mptt',
    install_requires=[
        'Django',
    ],
    test_suite="mptt.tests.test_runner.run_tests",
    packages=find_packages(exclude=['mptt.tests']),
    classifiers = ['Development Status :: 4 - Beta',
                   'Environment :: Web Environment',
                   'Framework :: Django',
                   'Intended Audience :: Developers',
                   'License :: OSI Approved :: BSD License',
                   'Operating System :: OS Independent',
                   'Programming Language :: Python',
                   'Topic :: Utilities'],
)
