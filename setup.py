#!/usr/bin/env python3

from setuptools import find_packages, setup

setup(
    name="django-mptt",
    description=(
        "Utilities for implementing Modified Preorder Tree Traversal "
        "with your Django Models and working with trees of Model instances."
    ),
    version="0.12.0-pre",
    author="Craig de Stigter",
    author_email="craig.ds@gmail.com",
    url="https://github.com/django-mptt/django-mptt",
    license="MIT License",
    packages=find_packages(exclude=["tests", "tests.*"]),
    include_package_data=True,
    install_requires=[
        "Django>=1.11",
        "django-js-asset",
    ],
    python_requires=">=3.6",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Web Environment",
        "Framework :: Django",
        "Framework :: Django :: 2.2",
        "Framework :: Django :: 3.0",
        "Framework :: Django :: 3.1",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
        "Topic :: Utilities",
    ],
)
