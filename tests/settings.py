import os

DIRNAME = os.path.dirname(__file__)

DEBUG = True
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': 'mydatabase'
    }
}
# for django 1.1 compatibility
DATABASE_ENGINE = 'sqlite3'
DATABASE_NAME = 'test.db'

INSTALLED_APPS = (
    'mptt',
    'myapp',
)

# Required for Django 1.4+
STATIC_URL = '/static/'

# Required for Django 1.5+
SECRET_KEY = 'abc123'
