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

$COVERAGE $DJANGO_ADMIN test --traceback --settings=$DJANGO_SETTINGS_MODULE --verbosity 2 --pythonpath="../" "$@"

if [ `which coverage` ] ; then
    coverage report
fi
