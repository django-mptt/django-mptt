#!/bin/sh

export PYTHONPATH="../:."

django-admin test --settings=settings
