import os
import sys
import unittest
from contextlib import contextmanager
from io import StringIO
from typing import Optional

from datadirtest import DataDirTester, TestDataDir


@contextmanager
def captured_output():
    new_out, new_err = StringIO(), StringIO()
    old_out, old_err = sys.stdout, sys.stderr
    try:
        sys.stdout, sys.stderr = new_out, new_err
        yield sys.stdout, sys.stderr
    finally:
        sys.stdout, sys.stderr = old_out, old_err


class TestComponent(unittest.TestCase):

    def setUp(self) -> None:
        self.test_datadirs = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                          'resources')

        self.test_datadirs_passing = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                                  'resources_passing')
        self.test_datadirs_passing_env = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                                      'resources_passing_env_variables')

        self.test_datadirs_chained = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                                  'chained_tests')

        self.mock_datadirtest = TestDataDir(os.path.join(self.test_datadirs_passing, 'passing_scripts'), '')

    def test_nested_different_content_fails(self):
        expected = os.path.join(self.test_datadirs, 'foldered_diff', 'expected')
        source = os.path.join(self.test_datadirs, 'foldered_diff', 'source')
        with self.assertRaises(AssertionError):
            self.mock_datadirtest.assert_directory_files_contents_match(expected, source)

    def test_error_in_suite(self):
        tester = DataDirTester(self.test_datadirs, os.path.join(self.test_datadirs, 'script.py'))

        with self.assertRaises(AssertionError):
            tester.run()

    def test_passing_with_scripts(self):
        tester = DataDirTester(self.test_datadirs_passing, os.path.join(self.test_datadirs_passing, 'script.py'))
        with captured_output() as (out, err):
            tester.run()
        output = out.getvalue().strip()
        self.assertEqual(output, 'setUp\nfile created\npostRun\ntearDown\nsetUp\nfile created\npostRun\ntearDown'"")

    def test_passing_with_env(self):
        tester = DataDirTester(self.test_datadirs_passing_env,
                               os.path.join(self.test_datadirs_passing_env, 'script.py'))
        os.environ['bool2_col'] = 'bool_bool2'
        os.environ['time_col'] = 'time_submitted'
        with captured_output() as (out, err):
            tester.run()
        output = out.getvalue().strip()
        self.assertEqual(output, 'setUp\nfile created\ntearDown')

    def test_chained_tests(self):
        tester = DataDirTester(self.test_datadirs_chained, os.path.join(self.test_datadirs_chained, 'script.py'))
        with captured_output() as (out, err):
            tester.run()

    def test_context_parameters(self):
        class CustomDatadirTest(TestDataDir):

            def __init__(self, data_dir: str, component_script: str, method_name: str = 'compare_source_and_expected',
                         context_parameters: Optional[dict] = None):
                super().__init__(data_dir, component_script, 'test_method', context_parameters)

            def test_method(self):
                print(self.context_parameters['custom_parameter'])

        injected_value = 'injected_parameter'
        tester = DataDirTester(self.test_datadirs, os.path.join(self.test_datadirs, 'script.py'),
                               test_data_dir_class=CustomDatadirTest,
                               context_parameters={'custom_parameter': injected_value})

        with captured_output() as (out, err):
            tester.run()

        output = out.getvalue().strip()
        self.assertEqual(output, injected_value)


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
