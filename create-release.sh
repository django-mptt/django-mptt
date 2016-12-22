#!/bin/bash -ex

# Clean environment, to avoid https://github.com/django-mptt/django-mptt/issues/513
python ./setup.py clean
rm -rf ./*.egg-info

python setup.py sdist bdist_wheel register upload
