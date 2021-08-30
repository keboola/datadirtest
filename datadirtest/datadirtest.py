import filecmp
import importlib.util
import logging
import os
import shutil
import sys
import tempfile
import unittest
from difflib import Differ
from importlib.abc import Loader
from os import path
from pathlib import Path
from runpy import run_path
from typing import List, Optional, Type


class TestDataDir(unittest.TestCase):
    """
    A test class that runs a component script to get a real output of a component and compares the output to the
    specified expected output of that component and its configuration
    """

    def __init__(self, data_dir: str, component_script: str, method_name: str = 'compare_source_and_expected',
                 context_parameters: Optional[dict] = None):
        """
        Args:
            method_name (str): name of the testing method to be run
            data_dir (str): file_path to directory which holds the component config, source, and expected directories
            component_script (str): file_path to component script that should be run
            context_parameters (dict): Optional context parameters injected from the DirTester runner.
        """
        super(TestDataDir, self).__init__(methodName=method_name)
        self.component_script = component_script
        self.orig_dir = data_dir
        self.expected_path = path.join(data_dir, 'expected')
        self.context_parameters = context_parameters

    def setUp(self):
        self.data_dir = self._create_temporary_copy()
        self._run_set_up_script()

    def _run_set_up_script(self):
        start_script_path = os.path.join(self.orig_dir, 'source', 'set_up.py')
        if os.path.exists(start_script_path):
            script = self._load_module_at_path(start_script_path)
            try:
                script.run(self)
            except AttributeError:
                raise NotImplementedError(
                    "The set_up.py file was found but it does not implement the run(context) method. Please add the "
                    "implementation")

    def tearDown(self) -> None:
        self._run_tear_down_script()
        shutil.rmtree(self.data_dir)

    @staticmethod
    def _load_module_at_path(run_script_path):
        spec = importlib.util.spec_from_file_location("custom_scripts", run_script_path)
        script = importlib.util.module_from_spec(spec)
        assert isinstance(spec.loader, Loader)
        spec.loader.exec_module(script)
        return script

    def _run_tear_down_script(self):
        end_script_path = os.path.join(self.orig_dir, 'source', 'tear_down.py')
        if os.path.exists(end_script_path):
            script = self._load_module_at_path(end_script_path)
            try:
                script.run(self)
            except AttributeError:
                raise NotImplementedError(
                    "The tear_down.py file was found but it does not implement the run(context) method. Please add the "
                    "implementation")

    def id(self):
        return path.basename(self.orig_dir)

    def shortDescription(self) -> Optional[str]:
        return path.basename(self.orig_dir)

    def _create_temporary_copy(self):
        temp_dir = tempfile.gettempdir()
        dst_path = path.join(temp_dir, 'test_data')
        if path.exists(dst_path):
            shutil.rmtree(dst_path)

        shutil.copytree(self.orig_dir, dst_path)
        return dst_path

    def run_component(self):
        """
        Runs a component script with a specified configuration
        """
        source_dir = path.join(self.data_dir, "source", "data")
        os.environ["KBC_DATADIR"] = source_dir
        run_path(self.component_script, run_name='__main__')

    def compare_source_and_expected(self):
        """
        Executes and compares source and expected directories based on the nested directory structure and files
        within them

        """
        logging.info(f"Running {self.component_script} with configuration from {self.data_dir}")
        self.run_component()

        files_expected_path, tables_expected_path = self.get_data_paths(self.data_dir, 'expected')
        files_real_path, tables_real_path = self.get_data_paths(self.data_dir, 'source')

        if path.exists(files_expected_path) or path.exists(files_real_path):
            self.assert_directory_structure_match(files_expected_path, files_real_path)
            self.assert_directory_files_contents_match(files_expected_path, files_real_path)
        if path.exists(tables_expected_path) or path.exists(tables_real_path):
            self.assert_directory_structure_match(tables_expected_path, tables_real_path)
            self.assert_directory_files_contents_match(tables_expected_path, tables_real_path)
        logging.info("Tests passed successfully ")

    @staticmethod
    def get_data_paths(data_dir: str, dir_type: str):
        """
        Uses the Keboola data structure to return paths to files and tables

        Args:
            data_dir: file_path of directory to get file and table paths from
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
            dir_path: file_path of directory to fetch files from

        Returns:
            list of files in the directory
        """
        files = []
        for sub_dir, dir_names, file_names in os.walk(dir_path):
            for filename in [f for f in file_names if not f.startswith(".")]:
                files.append(os.path.join(sub_dir, filename))
        return files

    def assert_directory_structure_match(self, expected_path: str, real_path: str):
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

    def assert_directory_files_contents_match(self, files_expected_path: str, files_real_path: str):
        """
        Tests whether files in two directories are the same.
        If not the error message prints out which files differ in each directory

        Args:
            files_expected_path:  Path holding expected files
            files_real_path: Path holding real/source files
        """
        file_paths = self.get_all_files_in_dir(files_expected_path)
        common_files = [file.replace(files_expected_path, "").strip("/").strip('\\') for file in file_paths]
        equal, mismatch, errors = filecmp.cmpfiles(files_expected_path, files_real_path, common_files, shallow=False)
        if mismatch:
            self._produce_file_diff(files_expected_path, files_real_path, mismatch)
        self.assertEqual(mismatch, [], f" Files : {mismatch} do not match")
        self.assertEqual(errors, [], f" Files : {errors} could not be compared")

    def _produce_file_diff(self, files_expected_path, files_real_path, mismatch):
        for f in mismatch:
            print(f'Diff of {f}, expected vs real: ')
            with open(os.path.join(files_expected_path, f)) as file_1, open(os.path.join(files_real_path, f)) as file_2:
                differ = Differ()

                for line in differ.compare(file_1.readlines(), file_2.readlines()):
                    print(line)


class DataDirTester:
    """
        Object that executes functional tests of the Keboola Connection components.

        The `DataDirTester` looks for the `component.py` script and executes it against the specified source folders,
        the `component.py` should expect the data folder path in the environment variable `KBC_DATADIR`.

        Each test is specified by a folder containing following folder structure:

        - `source` - contains data folder that would be on the input of the component
        - `expected` - contains data folder that is result of the execution against the `source` folder.
        Include only folder that contain some files, e.g. `expected/files/out/file.json`
    """

    def __init__(self, data_dir: str = Path('./tests/functional').absolute().as_posix(),
                 component_script: str = Path('./src/component.py').absolute().as_posix(),
                 test_data_dir_class: Type[TestDataDir] = TestDataDir,
                 context_parameters: Optional[dict] = None):
        """

        Args:
            data_dir (str): file_path to directory that holds functional test directories. By default this is
            ./functional
            component_script (str): file_path to the component script. By default this is ../src/component.py
            context_parameters (dict): dictionary with optional parameters that will be passed to each Test instance.
            Usefull when overriding the TestDataDirClass to add custom functionality
            test_data_dir_class (Type[TestDataDir]): Class extending datadirtest.TestDataDir class with additional
            functionality. It will be used for each test in the suit.


        """
        self._data_dir = data_dir
        self._component_script = component_script
        self._context_parameters = context_parameters or {}
        self.__test_class = test_data_dir_class

    def run(self):
        """
            Runs functional tests specified in the provided folder based on the source/expected datadirs.
        """
        testing_dirs = self._get_testing_dirs(self._data_dir)
        dir_test_suite = self._build_dir_test_suite(testing_dirs)
        test_runner = unittest.TextTestRunner(verbosity=3)
        result = test_runner.run(dir_test_suite)
        if not result.wasSuccessful():
            raise AssertionError(f'Functional test suite failed. {result.errors}')

    @staticmethod
    def _get_testing_dirs(data_dir: str) -> List:
        """
        Gets directories within a directory that do not start with an underscore

        Args:
            data_dir: directory which holds directories

        Returns:
            list of paths inside directory
        """
        return [os.path.join(data_dir, o) for o in os.listdir(data_dir) if
                os.path.isdir(os.path.join(data_dir, o)) and not o.startswith('_')]

    def _build_dir_test_suite(self, testing_dirs):
        """
        Creates a test suite for a directory, each test is added using addTest to pass through parameters

        Args:
            testing_dirs: directories that holds data for the test

        Returns:
            Unittest Suite containing all functional tests

        """
        suite = unittest.TestSuite()
        for testing_dir in testing_dirs:
            suite.addTest(self.__test_class(method_name='compare_source_and_expected',
                                            data_dir=testing_dir,
                                            component_script=self._component_script,
                                            context_parameters=self._context_parameters))
        return suite


if __name__ == "__main__":
    data_dir_path = sys.argv[1]
    data_dir_tester = DataDirTester(data_dir_path)

    if len(sys.argv) == 3:
        script_path = sys.argv[2]
        data_dir_tester = DataDirTester(data_dir_path, component_script=script_path)

    data_dir_tester.run()
