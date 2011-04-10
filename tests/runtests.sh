#!/bin/sh
export PYTHONPATH="./"
export DJANGO_SETTINGS_MODULE='settings'

django-admin test --pythonpath="../"
