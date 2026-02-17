"""
VCR integration for datadirtest.

This module provides VCR (Video Cassette Recording) functionality for
recording and replaying HTTP interactions in component tests.

Core VCR functionality (recorder, sanitizers, validator, scaffolder) lives
in the ``keboola.vcr`` package.  This module re-exports those symbols for
backward compatibility and adds the datadirtest-specific test runner classes
(VCRTestDataDir, VCRDataDirTester) that integrate VCR with DataDirTester.

Example usage:
    from datadirtest.vcr import VCRDataDirTester

    # Run tests with VCR replay (default, CI-friendly)
    tester = VCRDataDirTester(
        data_dir='tests/functional',
        component_script='src/component.py'
    )
    tester.run()

    # Record cassettes (requires real credentials)
    tester = VCRDataDirTester(
        data_dir='tests/functional',
        component_script='src/component.py',
        vcr_mode='record'
    )
    tester.run()
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Literal, Optional, Type

from ..datadirtest import DataDirTester, TestDataDir

# Re-export from keboola.vcr for backward compatibility
from keboola.vcr.recorder import VCRRecorder, VCRRecorderError, CassetteMissingError, SecretsLoadError
from keboola.vcr.sanitizers import (
    BaseSanitizer,
    DefaultSanitizer,
    TokenSanitizer,
    HeaderSanitizer,
    UrlPatternSanitizer,
    BodyFieldSanitizer,
    QueryParameterTokenSanitizer,
    ResponseUrlSanitizer,
    CallbackSanitizer,
    CompositeSanitizer,
    ConfigSecretsSanitizer,
    create_default_sanitizer,
)
from keboola.vcr.validator import (
    OutputSnapshot,
    ValidationResult,
    ValidationDiff,
    capture_output_snapshot,
    save_output_snapshot,
    validate_output_snapshot,
)

logger = logging.getLogger(__name__)


class VCRTestDataDir(TestDataDir):
    """
    TestDataDir with VCR recording/replay support.

    This class extends TestDataDir to wrap component execution with
    VCR for recording or replaying HTTP interactions.

    Modes:
        - 'record': Always record HTTP interactions (requires credentials)
        - 'replay': Always replay recorded interactions (fails if no cassette)
        - 'auto': Replay if cassette exists, skip VCR wrapping if not

    Example:
        test = VCRTestDataDir(
            data_dir='tests/functional/test_api',
            component_script='src/component.py',
            vcr_mode='auto'
        )
    """

    def __init__(
        self,
        data_dir: str,
        component_script: str,
        method_name: str = "compare_source_and_expected",
        context_parameters: Optional[dict] = None,
        last_state_override: dict = None,
        artefacts_path: str = None,
        artifact_current_destination: Literal["custom", "runs"] = "runs",
        save_output: bool = False,
        vcr_mode: Literal["record", "replay", "auto"] = "auto",
        vcr_freeze_time: Optional[str] = "auto",
        vcr_sanitizers: Optional[List[BaseSanitizer]] = None,
        validate_snapshot: bool = False,
        verbose: bool = False,
    ):
        """
        Initialize VCR test data directory.

        Args:
            data_dir: Path to directory with test data
            component_script: Path to component script to run
            method_name: Test method name
            context_parameters: Optional context parameters
            last_state_override: Optional state override
            artefacts_path: Optional artifacts path
            artifact_current_destination: Artifact destination type
            save_output: Whether to save output
            vcr_mode: VCR mode - 'record', 'replay', or 'auto'
            vcr_freeze_time: ISO timestamp to freeze time at ('auto' to read from cassette, None to disable)
            vcr_sanitizers: Custom sanitizers for VCR recordings
            validate_snapshot: Whether to validate outputs against snapshot
            verbose: Enable verbose output (full diffs)
        """
        super().__init__(
            data_dir=data_dir,
            component_script=component_script,
            method_name=method_name,
            context_parameters=context_parameters,
            last_state_override=last_state_override,
            artefacts_path=artefacts_path,
            artifact_current_destination=artifact_current_destination,
            save_output=save_output,
        )

        self.vcr_mode = vcr_mode
        self.vcr_freeze_time = vcr_freeze_time
        self.vcr_sanitizers = vcr_sanitizers
        self.validate_snapshot = validate_snapshot
        self.verbose = verbose
        self.vcr_recorder: Optional[VCRRecorder] = None

    def setUp(self):
        """Set up test including VCR recorder initialization."""
        super().setUp()
        self._setup_vcr()

    def _setup_vcr(self):
        """Initialize VCR recorder with test-specific config."""
        try:
            self.vcr_recorder = VCRRecorder.from_test_dir(
                test_data_dir=Path(self.source_data_dir),
                freeze_time_at=self.vcr_freeze_time,
                sanitizers=self.vcr_sanitizers,
            )
        except ImportError as e:
            logger.warning(f"VCR dependencies not installed: {e}")
            self.vcr_recorder = None
        except Exception as e:
            logger.warning(f"Failed to initialize VCR recorder: {e}")
            self.vcr_recorder = None

    def _merge_secrets_into_config(self):
        """Merge secrets from config.secrets.json into the working config."""
        secrets_path = Path(self.source_data_dir) / "config.secrets.json"
        if not secrets_path.exists():
            return

        try:
            with open(secrets_path, "r") as f:
                secrets = json.load(f)

            with open(self.source_config_path, "r") as f:
                config = json.load(f)

            # Deep merge secrets into config
            merged = self._deep_merge(config, secrets)

            with open(self.source_config_path, "w") as f:
                json.dump(merged, f, indent=2)

            logger.debug(f"Merged secrets into config for {self.id()}")
        except Exception as e:
            logger.warning(f"Failed to merge secrets: {e}")

    @staticmethod
    def _deep_merge(base: Dict, override: Dict) -> Dict:
        """Deep merge two dictionaries, with override taking precedence."""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = VCRTestDataDir._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def run_component(self):
        """Run component with VCR wrapping based on mode."""
        # Merge secrets before running if we're recording
        if self.vcr_mode == "record":
            self._merge_secrets_into_config()

        if self.vcr_recorder is None:
            # VCR not available, run without it
            logger.warning("Running without VCR (dependencies not available)")
            super().run_component()
            return

        if self.vcr_mode == "record":
            self._merge_secrets_into_config()
            self.vcr_recorder.record(super().run_component)
        elif self.vcr_mode == "replay":
            self.vcr_recorder.replay(super().run_component)
        else:  # auto
            if self.vcr_recorder.has_cassette():
                self.vcr_recorder.replay(super().run_component)
            else:
                # No cassette, check if secrets exist to record
                secrets_path = Path(self.source_data_dir) / "config.secrets.json"
                if secrets_path.exists():
                    self._merge_secrets_into_config()
                    self.vcr_recorder.record(super().run_component)
                else:
                    # No cassette and no secrets, run without VCR
                    logger.info(f"No cassette and no secrets for {self.id()}, running without VCR")
                    super().run_component()

    def compare_source_and_expected(self):
        """
        Execute and compare with optional snapshot validation.

        This extends the base comparison to optionally validate
        outputs against a hash-based snapshot.
        """
        # Run the standard comparison
        super().compare_source_and_expected()

        # Optionally validate against snapshot
        if self.validate_snapshot:
            self._validate_snapshot()

    def _validate_snapshot(self):
        """Validate outputs against snapshot if it exists."""
        snapshot_path = Path(self.source_data_dir) / "output_snapshot.json"
        if not snapshot_path.exists():
            logger.debug(f"No snapshot file for {self.id()}, skipping snapshot validation")
            return

        result = validate_output_snapshot(
            test_data_dir=Path(self.source_data_dir),
            expected_dir=Path(self.expected_path) / "data" / "out" if self.expected_path else None,
            verbose=self.verbose,
        )

        if not result.success:
            self.fail(result.format_output(verbose=self.verbose))


class VCRDataDirTester(DataDirTester):
    """
    DataDirTester with VCR support.

    This class extends DataDirTester to provide VCR recording/replay
    capabilities for all tests in a functional test directory.

    Example:
        # Run with automatic VCR (replay if cassettes exist)
        tester = VCRDataDirTester(
            data_dir='tests/functional',
            component_script='src/component.py'
        )
        tester.run()

        # Record new cassettes
        tester = VCRDataDirTester(
            data_dir='tests/functional',
            component_script='src/component.py',
            vcr_mode='record'
        )
        tester.run()
    """

    def __init__(
        self,
        data_dir: str = Path("./tests/functional").absolute().as_posix(),
        component_script: str = Path("./src/component.py").absolute().as_posix(),
        test_data_dir_class: Type[TestDataDir] = None,
        context_parameters: Optional[dict] = None,
        artifact_current_destination: Literal["custom", "runs"] = "runs",
        save_output: bool = False,
        selected_tests: Optional[List[str]] = None,
        vcr_mode: Literal["record", "replay", "auto"] = "auto",
        vcr_freeze_time: Optional[str] = "auto",
        vcr_sanitizers: Optional[List[BaseSanitizer]] = None,
        validate_snapshots: bool = False,
        verbose: bool = False,
    ):
        """
        Initialize VCR data directory tester.

        Args:
            data_dir: Path to functional tests directory
            component_script: Path to component script
            test_data_dir_class: Custom test class (defaults to VCRTestDataDir)
            context_parameters: Optional context parameters
            artifact_current_destination: Artifact destination type
            save_output: Whether to save output
            selected_tests: List of specific tests to run
            vcr_mode: VCR mode - 'record', 'replay', or 'auto'
            vcr_freeze_time: ISO timestamp to freeze time at ('auto' to read from cassette, None to disable)
            vcr_sanitizers: Custom sanitizers for VCR recordings
            validate_snapshots: Whether to validate outputs against snapshots
            verbose: Enable verbose output
        """
        # Use VCRTestDataDir by default
        if test_data_dir_class is None:
            test_data_dir_class = VCRTestDataDir

        # Store VCR-specific params to pass to test instances
        self.vcr_mode = vcr_mode
        self.vcr_freeze_time = vcr_freeze_time
        self.vcr_sanitizers = vcr_sanitizers
        self.validate_snapshots = validate_snapshots
        self.verbose = verbose

        # Build context parameters with VCR settings
        vcr_context = {
            "vcr_mode": vcr_mode,
            "vcr_freeze_time": vcr_freeze_time,
            "vcr_sanitizers": vcr_sanitizers,
            "validate_snapshot": validate_snapshots,
            "verbose": verbose,
        }

        if context_parameters:
            context_parameters = {**context_parameters, **vcr_context}
        else:
            context_parameters = vcr_context

        super().__init__(
            data_dir=data_dir,
            component_script=component_script,
            test_data_dir_class=test_data_dir_class,
            context_parameters=context_parameters,
            artifact_current_destination=artifact_current_destination,
            save_output=save_output,
            selected_tests=selected_tests,
        )

    def _build_dir_test_suite(self, testing_dirs):
        """
        Create test suite with VCR-enabled test instances.

        Overrides parent to pass VCR parameters to test instances.
        """
        import unittest

        suite = unittest.TestSuite()

        for testing_dir in testing_dirs:
            if self._is_chained_test(testing_dir):
                # Chained tests use the parent class for now
                from ..datadirtest import TestChainedDatadirTest

                test = TestChainedDatadirTest(
                    data_dir=testing_dir,
                    component_script=self._component_script,
                    context_parameters=self._context_parameters,
                    test_data_dir_class=self._DataDirTester__test_class,
                    artifact_current_destination=self._artifact_current_destination,
                    save_output=self._save_output,
                )
            else:
                # Create VCR-enabled test
                test = self._DataDirTester__test_class(
                    method_name="compare_source_and_expected",
                    data_dir=testing_dir,
                    component_script=self._component_script,
                    context_parameters=self._context_parameters,
                    save_output=self._save_output,
                    vcr_mode=self.vcr_mode,
                    vcr_freeze_time=self.vcr_freeze_time,
                    vcr_sanitizers=self.vcr_sanitizers,
                    validate_snapshot=self.validate_snapshots,
                    verbose=self.verbose,
                )

            suite.addTest(test)

        return suite


def get_test_cases(functional_dir: str) -> List[str]:
    """Discover VCR test case names in a functional test directory.

    Returns sorted list of directory names that contain a cassette file,
    suitable for use with pytest.mark.parametrize.

    Args:
        functional_dir: Path to the functional tests directory.
    """
    func_path = Path(functional_dir)
    if not func_path.exists():
        return []
    return [
        d.name
        for d in sorted(func_path.iterdir())
        if d.is_dir()
        and not d.name.startswith("_")
        and (d / "source" / "data" / "cassettes").exists()
    ]


# Re-export for convenience
__all__ = [
    # Main classes
    "VCRTestDataDir",
    "VCRDataDirTester",
    "VCRRecorder",
    # Sanitizers (re-exported from keboola.vcr)
    "BaseSanitizer",
    "DefaultSanitizer",
    "TokenSanitizer",
    "HeaderSanitizer",
    "UrlPatternSanitizer",
    "BodyFieldSanitizer",
    "QueryParameterTokenSanitizer",
    "ResponseUrlSanitizer",
    "CallbackSanitizer",
    "CompositeSanitizer",
    "ConfigSecretsSanitizer",
    "create_default_sanitizer",
    # Validation (re-exported from keboola.vcr)
    "OutputSnapshot",
    "ValidationResult",
    "ValidationDiff",
    "capture_output_snapshot",
    "save_output_snapshot",
    "validate_output_snapshot",
    # Discovery
    "get_test_cases",
    # Exceptions
    "VCRRecorderError",
    "CassetteMissingError",
    "SecretsLoadError",
]
