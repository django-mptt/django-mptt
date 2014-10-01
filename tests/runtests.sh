#!/bin/sh
set -e
export PYTHONPATH="./"
export DJANGO_SETTINGS_MODULE='settings'

if [ `which django-admin.py` ] ; then
    export DJANGO_ADMIN=`which django-admin.py`
else
    export DJANGO_ADMIN=`which django-admin`
fi

if [ `which coverage` ] ; then
    export COVERAGE='coverage run'
else
    export COVERAGE=''
fi

export args="$@"
if [ -z "$args" ] ; then
    # avoid running the tests for django.contrib.* (they're in INSTALLED_APPS)
    export args=myapp
fi

$COVERAGE $DJANGO_ADMIN test --traceback --settings=$DJANGO_SETTINGS_MODULE --verbosity 2 --pythonpath="../" "$args"

if [ `which coverage` ] ; then
    coverage report
fi
