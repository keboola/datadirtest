import sys
import unittest
import os
import logging
from os import path
from typing import List
from runpy import run_path
import filecmp


class DataDirTester:
    """
    A class that manages functional testing by creating unittest test suites for each functional test directory and
    running these tests.
    """

    def __init__(self, data_dir: str, component_script: str = "src/component.py"):
        """
        Args:
            data_dir: path to directory that holds functional test directories
            component_script: path to the component script
        """
        self.data_dir = data_dir
        self.component_script = component_script

    def run(self):
        """
        Gathers functional test directories and creates a test suite for each one of them, then runs them.
        """
        testing_dirs = self.get_testing_dirs(self.data_dir)
        for testing_dir in testing_dirs:
            dir_test_suite = self.get_dir_test_suite(testing_dir)
            test_runner = unittest.TextTestRunner(verbosity=3)
            test_runner.run(dir_test_suite)

    @staticmethod
    def get_testing_dirs(data_dir: str) -> List:
        """
        Gets directories within a directory that do not start with an underscore

        Args:
            data_dir: directory which holds directories

        Returns:
            list of paths inside directory
        """
        return [os.path.join(data_dir, o) for o in os.listdir(data_dir) if
                os.path.isdir(os.path.join(data_dir, o)) and not o.startswith('_')]

    def get_dir_test_suite(self, test_data_dir: str):
        """
        Creates a test suite for a directory, each test is added using addTest to pass through parameters

        Args:
            test_data_dir: directory that holds data for the test
            component_script: path to the component script

        Returns:
            Unittest Suite containing all functional tests

        """
        suite = unittest.TestSuite()
        suite.addTest(TestDataDir(method_name='compare_source_and_expected',
                                  data_dir=test_data_dir,
                                  component_script=self.component_script))
        return suite


class TestDataDir(unittest.TestCase):
    """
    A test class that runs a component script to get a real output of a component and compares the output to the
    specified expected output of that component and its configuration
    """

    def __init__(self, method_name: str, data_dir: str, component_script: str):
        """
        Args:
            method_name: name of the testing method to be run
            data_dir: path to directory which holds the component config, source, and expected directories
            component_script: path to component script that should be run
        """
        super(TestDataDir, self).__init__(methodName=method_name)
        self.component_script = component_script
        self.data_dir = data_dir

    def setUp(self):
        logging.info(f"Running {self.component_script} with configuration from {self.data_dir}")
        self.run_component()

    def run_component(self):
        """
        Runs a component script with a specified configuration
        """
        source_dir = path.join(self.data_dir, "/source/data/")
        run_path(self.component_script, init_globals=dict(os.environ, KBC_DATADIR=source_dir), run_name='__main__')

    def compare_source_and_expected(self):
        """
        Compares source and expected directories based on the nested directory structure and files within them

        """

        files_expected_path, tables_expected_path = self.get_data_paths(self.data_dir, 'expected')
        files_real_path, tables_real_path = self.get_data_paths(self.data_dir, 'source')

        if path.exists(files_expected_path) or path.exists(files_real_path):
            self.test_compare_dirs(files_expected_path, files_real_path)
            self.test_compare_files(files_expected_path, files_real_path)
        if path.exists(tables_expected_path) or path.exists(tables_real_path):
            self.test_compare_dirs(tables_expected_path, tables_real_path)
            self.test_compare_files(tables_expected_path, tables_real_path)
        logging.info("Tests passed success")

    @staticmethod
    def get_data_paths(data_dir: str, dir_type: str):
        """
        Uses the Keboola data structure to return paths to files and tables

        Args:
            data_dir: path of directory to get file and table paths from
            dir_type: type of directory source or expected

        Returns:
            paths to files and tables
        """
        files_expected_path = path.join(data_dir, dir_type, 'data', 'out', 'files')
        tables_expected_path = path.join(data_dir, dir_type, 'data', 'out', 'tables')
        return files_expected_path, tables_expected_path

    @staticmethod
    def get_all_files_in_dir(dir_path: str):
        """
        Gets all non-hidden files from a directory and its subdirectory

        Args:
            dir_path: path of directory to fetch files from

        Returns:
            list of files in the directory
        """
        files = []
        for sub_dir, dir_names, file_names in os.walk(dir_path):
            for filename in [f for f in file_names if not f.startswith(".")]:
                files.append(os.path.join(sub_dir, filename))
        return files

    def test_compare_dirs(self, expected_path: str, real_path: str):
        """
        Tests whether directory structures of two directories are the same.
        If not the error message prints out which files differ in each directory

        Args:
            expected_path: Path holding the directory of expected files
            real_path: Path holding the directory of real/source files
        """
        compared_dir = filecmp.dircmp(expected_path, real_path)

        left = [file for file in compared_dir.left_only if not file.startswith('.')]
        right = [file for file in compared_dir.right_only if not file.startswith('.')]

        self.assertEqual(left, [], f" Files : {left} exists only in expected output and not in actual output")
        self.assertEqual(right, [], f" Files : {right} exists only in actual output and not in expected output")

    def test_compare_files(self, files_expected_path: str, files_real_path: str):
        """
        Tests whether files in two directories are the same.
        If not the error message prints out which files differ in each directory

        Args:
            files_expected_path:  Path holding expected files
            files_real_path: Path holding real/source files
        """
        f = self.get_all_files_in_dir(files_expected_path)
        f = [file.replace(files_expected_path, "").strip("/") for file in f]
        equal, mismatch, errors = filecmp.cmpfiles(files_expected_path, files_real_path, f, shallow=False)
        self.assertEqual(mismatch, [], f" Files : {mismatch} do not match")
        self.assertEqual(errors, [], f" Files : {errors} could not be compared")


if __name__ == "__main__":
    data_dir_path = sys.argv[1]
    data_dir_tester = DataDirTester(data_dir_path)

    if len(sys.argv) == 3:
        component_script = sys.argv[2]
        data_dir_tester = DataDirTester(data_dir_path, component_script=component_script)

    data_dir_tester.run()
