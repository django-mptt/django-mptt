#!/usr/bin/env python

from setuptools import find_packages, setup


setup(
    name='django-mptt',
    description='''Utilities for implementing Modified Preorder Tree Traversal
        with your Django Models and working with trees of Model instances.''',
    version=__import__('mptt').__version__,
    author='Craig de Stigter',
    author_email='craig.ds@gmail.com',
    url='http://github.com/django-mptt/django-mptt',
    license='MIT License',
    packages=find_packages(),
    include_package_data=True,
    install_requires=(
        'Django>=1.8',
    ),
    tests_require=(
        'mock-django>=0.6.7',
        'mock>=1.3',
    ),
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.2",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
        'Topic :: Utilities',
    ],
)
