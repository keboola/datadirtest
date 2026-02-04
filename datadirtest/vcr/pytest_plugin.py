"""
Pytest plugin for VCR-enabled datadirtest.

This module provides pytest fixtures for running VCR-enabled
functional tests. To use, add to conftest.py:

    pytest_plugins = ["datadirtest.vcr.pytest_plugin"]

Or register manually:

    from datadirtest.vcr.pytest_plugin import pytest_configure

Example test:

    def test_component_extraction(vcr_test_runner, functional_test_case):
        result = vcr_test_runner.run_test(functional_test_case)
        assert result.success
"""

from pathlib import Path
from typing import List, Optional

import pytest


def pytest_addoption(parser):
    """Add VCR-related command line options."""
    group = parser.getgroup("vcr", "VCR recording/replay options")

    group.addoption(
        "--vcr-record",
        action="store_true",
        default=False,
        help="Record HTTP interactions (requires credentials)",
    )

    group.addoption(
        "--vcr-replay",
        action="store_true",
        default=False,
        help="Replay recorded interactions (fail if no cassettes)",
    )

    group.addoption(
        "--vcr-update",
        action="store_true",
        default=False,
        help="Update existing cassettes with new recordings",
    )

    group.addoption(
        "--no-vcr",
        action="store_true",
        default=False,
        help="Disable VCR completely",
    )

    group.addoption(
        "--vcr-freeze-time",
        type=str,
        default="2025-01-01T12:00:00",
        help="ISO timestamp to freeze time at (default: 2025-01-01T12:00:00)",
    )

    group.addoption(
        "--validate-snapshots",
        action="store_true",
        default=False,
        help="Validate outputs against hash-based snapshots",
    )

    group.addoption(
        "--functional-dir",
        type=str,
        default="tests/functional",
        help="Path to functional tests directory",
    )

    group.addoption(
        "--component-script",
        type=str,
        default="src/component.py",
        help="Path to component script",
    )


@pytest.fixture(scope="session")
def vcr_mode(request) -> str:
    """
    Get VCR mode from command line options.

    Returns:
        One of 'record', 'replay', 'auto', or 'disabled'
    """
    if request.config.getoption("--no-vcr"):
        return "disabled"
    elif request.config.getoption("--vcr-record") or request.config.getoption("--vcr-update"):
        return "record"
    elif request.config.getoption("--vcr-replay"):
        return "replay"
    else:
        return "auto"


@pytest.fixture(scope="session")
def vcr_freeze_time(request) -> Optional[str]:
    """Get freeze time from command line options."""
    freeze_time = request.config.getoption("--vcr-freeze-time")
    return freeze_time if freeze_time != "disable" else None


@pytest.fixture(scope="session")
def validate_snapshots(request) -> bool:
    """Get snapshot validation setting from command line options."""
    return request.config.getoption("--validate-snapshots")


@pytest.fixture(scope="session")
def functional_dir(request) -> Path:
    """Get functional tests directory from command line options."""
    return Path(request.config.getoption("--functional-dir")).absolute()


@pytest.fixture(scope="session")
def component_script(request) -> Path:
    """Get component script path from command line options."""
    return Path(request.config.getoption("--component-script")).absolute()


@pytest.fixture(scope="session")
def vcr_test_runner(
    vcr_mode,
    vcr_freeze_time,
    validate_snapshots,
    functional_dir,
    component_script,
):
    """
    Create a VCRDataDirTester configured from command line options.

    This fixture creates a ready-to-use tester instance that can
    run individual tests or full test suites.

    Example:
        def test_all_functional(vcr_test_runner):
            vcr_test_runner.run()  # Run all tests

        def test_specific(vcr_test_runner):
            vcr_test_runner.run_single("test_basic_extraction")
    """
    if vcr_mode == "disabled":
        from ..datadirtest import DataDirTester

        return DataDirTester(
            data_dir=str(functional_dir),
            component_script=str(component_script),
        )
    else:
        from . import VCRDataDirTester

        return VCRDataDirTester(
            data_dir=str(functional_dir),
            component_script=str(component_script),
            vcr_mode=vcr_mode,
            vcr_freeze_time=vcr_freeze_time,
            validate_snapshots=validate_snapshots,
        )


@pytest.fixture
def functional_test_dirs(functional_dir) -> List[Path]:
    """
    Get list of functional test directories.

    Returns list of paths to test directories (excluding those
    starting with underscore).
    """
    if not functional_dir.exists():
        return []

    return sorted([d for d in functional_dir.iterdir() if d.is_dir() and not d.name.startswith("_")])


def pytest_generate_tests(metafunc):
    """
    Generate parametrized tests for functional test cases.

    If a test function accepts 'functional_test_case' parameter,
    this hook generates a test for each test directory.
    """
    if "functional_test_case" in metafunc.fixturenames:
        functional_dir = Path(metafunc.config.getoption("--functional-dir")).absolute()

        if functional_dir.exists():
            test_dirs = [d.name for d in functional_dir.iterdir() if d.is_dir() and not d.name.startswith("_")]
            metafunc.parametrize("functional_test_case", sorted(test_dirs))


@pytest.fixture
def vcr_test_case(
    request,
    vcr_mode,
    vcr_freeze_time,
    validate_snapshots,
    functional_dir,
    component_script,
    functional_test_case,
):
    """
    Create a VCRTestDataDir instance for a single test case.

    This fixture is designed to be used with parametrized tests:

        def test_functional(vcr_test_case):
            vcr_test_case.setUp()
            try:
                vcr_test_case.compare_source_and_expected()
            finally:
                vcr_test_case.tearDown()
    """
    test_dir = functional_dir / functional_test_case

    if vcr_mode == "disabled":
        from ..datadirtest import TestDataDir

        return TestDataDir(
            data_dir=str(test_dir),
            component_script=str(component_script),
        )
    else:
        from . import VCRTestDataDir

        return VCRTestDataDir(
            data_dir=str(test_dir),
            component_script=str(component_script),
            vcr_mode=vcr_mode,
            vcr_freeze_time=vcr_freeze_time,
            validate_snapshot=validate_snapshots,
        )


class VCRTestResult:
    """Result of a VCR test run."""

    def __init__(self, success: bool, message: str = "", test_name: str = ""):
        self.success = success
        self.message = message
        self.test_name = test_name

    def __bool__(self):
        return self.success


@pytest.fixture
def run_vcr_test(vcr_test_runner):
    """
    Fixture that provides a function to run individual VCR tests.

    Example:
        def test_specific_case(run_vcr_test):
            result = run_vcr_test("test_basic_extraction")
            assert result.success, result.message
    """

    def _run_test(test_name: str) -> VCRTestResult:
        import io
        import unittest

        # Create a test suite with just the specified test
        from . import VCRTestDataDir

        functional_dir = vcr_test_runner._data_dir
        test_dir = Path(functional_dir) / test_name

        if not test_dir.exists():
            return VCRTestResult(
                success=False,
                message=f"Test directory not found: {test_dir}",
                test_name=test_name,
            )

        test = VCRTestDataDir(
            data_dir=str(test_dir),
            component_script=vcr_test_runner._component_script,
            vcr_mode=vcr_test_runner.vcr_mode,
            vcr_freeze_time=vcr_test_runner.vcr_freeze_time,
            validate_snapshot=vcr_test_runner.validate_snapshots,
            verbose=vcr_test_runner.verbose,
        )

        # Run the test
        suite = unittest.TestSuite([test])
        stream = io.StringIO()
        runner = unittest.TextTestRunner(stream=stream, verbosity=2)
        result = runner.run(suite)

        if result.wasSuccessful():
            return VCRTestResult(
                success=True,
                message="Test passed",
                test_name=test_name,
            )
        else:
            errors = result.errors + result.failures
            error_msg = "\n".join(str(e) for e in errors)
            return VCRTestResult(
                success=False,
                message=error_msg,
                test_name=test_name,
            )

    return _run_test


# Register the plugin
def pytest_configure(config):
    """Register the VCR marker."""
    config.addinivalue_line(
        "markers",
        "vcr: mark test as using VCR recording/replay",
    )
