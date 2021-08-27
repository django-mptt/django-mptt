#!/bin/bash -ex

# Clean environment, to avoid https://github.com/django-mptt/django-mptt/issues/513
python3 ./setup.py clean
rm -rf ./*.egg-info

python3 setup.py sdist bdist_wheel
