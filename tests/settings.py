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

SECRET_KEY = "One needs SECRET_KEY to be able to run tests"
