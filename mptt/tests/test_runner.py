import os, sys
os.environ['DJANGO_SETTINGS_MODULE'] = 'mptt.tests.settings'

from django.test.simple import run_tests as django_test_runner

# necessary for "python setup.py test"
test_dir = os.path.dirname(__file__)
sys.path.insert(0, test_dir)
#sys.path.insert(0, os.path.abspath('./..'))

def run_tests(test_labels=('mptt',), verbosity=1, interactive=True,
        extra_tests=[]):
    results = django_test_runner(test_labels, verbosity, interactive,
        extra_tests)
    sys.exit(results)

if __name__ == '__main__':
    run_tests()