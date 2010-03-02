
import unittest
import os
TEST_DIR = os.path.dirname(__file__)
import doctest

class MpttTestCase(unittest.TestCase):

    def test_dummy(self):
        self.assertTrue(1==1)

    def test_run_doctest(self):
        doctest.testfile('doctests.txt')

