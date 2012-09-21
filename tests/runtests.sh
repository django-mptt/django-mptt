#!/bin/sh
export PYTHONPATH="./"
export DJANGO_SETTINGS_MODULE='settings'

if [ `which django-admin.py` ] ; then
    export DJANGO_ADMIN=django-admin.py
else
    export DJANGO_ADMIN=django-admin
fi

$DJANGO_ADMIN test --settings=$DJANGO_SETTINGS_MODULE --pythonpath="../" "$@"
