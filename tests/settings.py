from __future__ import unicode_literals
import os

DIRNAME = os.path.dirname(__file__)

DEBUG = True
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': 'mydatabase'
    }
}

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'mptt',
    'myapp',
)

# Required for Django 1.4+
STATIC_URL = '/static/'

# Required for Django 1.5+
SECRET_KEY = 'abc123'
