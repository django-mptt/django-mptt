#!/bin/sh
set -e
export PYTHONPATH="./"
export DJANGO_SETTINGS_MODULE='settings'

if [ `which coverage` ] ; then
    export COVERAGE='coverage run'
else
    export COVERAGE='python'
fi

$COVERAGE -m django test --traceback --settings=$DJANGO_SETTINGS_MODULE --verbosity 2 --pythonpath="../" "$@"

if [ `which coverage` ] ; then
    coverage report
fi
