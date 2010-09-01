"""
Django mptt setup file
"""
from setuptools import setup, find_packages

# Dynamically calculate the version based on mptt.VERSION
version_tuple = __import__('mptt').VERSION
version = ".".join([str(v) for v in version_tuple])

setup(
    name = 'django-mptt-2',
    description = '''Utilities for implementing Modified Preorder Tree
    Traversal with your Django Models and working with trees of Model instances.
    Requires Django 1.1+''',
    version = version,
    author = 'Jonathan Buchanan',
    author_email = 'craig.ds@gmail.com',
    url = 'http://github.com/django-mptt/django-mptt',
    install_requires=[
        'Django >= 1.1',
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
