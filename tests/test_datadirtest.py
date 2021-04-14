import os
import unittest

from datadirtest import datadirtest


class TestComponent(unittest.TestCase):

    def setUp(self) -> None:
        self.mock_datadirtest = datadirtest.TestDataDir('compare_source_and_expected', '', '')
        self.test_datadirs = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                          'resources')

    def test_nested_different_content_fails(self):
        expected = os.path.join(self.test_datadirs, 'foldered_diff', 'expected')
        source = os.path.join(self.test_datadirs, 'foldered_diff', 'source')
        with self.assertRaises(AssertionError):
            self.mock_datadirtest.test_compare_files(expected, source)


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
