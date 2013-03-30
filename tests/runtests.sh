#!/bin/sh
export PYTHONPATH="./"
export DJANGO_SETTINGS_MODULE='settings'

if [ `which django-admin.py` ] ; then
    export DJANGO_ADMIN=django-admin.py
else
    export DJANGO_ADMIN=django-admin
fi

export args="$@"
if [ -z "$args" ] ; then
    # avoid running the tests for django.contrib.* (they're in INSTALLED_APPS)
    export args=myapp
fi

$DJANGO_ADMIN test --traceback --settings=$DJANGO_SETTINGS_MODULE --pythonpath="../" "$args"
