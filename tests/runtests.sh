#!/bin/sh
export PYTHONPATH="./"
export DJANGO_SETTINGS_MODULE='settings'

django-admin.py test --settings=$DJANGO_SETTINGS_MODULE --pythonpath="../" "$@"
