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

    tester = VCRDataDirTester(
        data_dir='tests/functional',
        component_script='src/component.py'
    )
    tester.run()
"""

# Re-export from keboola.vcr for backward compatibility
from keboola.vcr.recorder import CassetteMissingError, SecretsLoadError, VCRRecorder, VCRRecorderError
from keboola.vcr.sanitizers import (
    BaseSanitizer,
    BodyFieldSanitizer,
    CallbackSanitizer,
    CompositeSanitizer,
    ConfigSecretsSanitizer,
    DefaultSanitizer,
    HeaderSanitizer,
    QueryParamSanitizer,
    ResponseUrlSanitizer,
    TokenSanitizer,
    UrlPatternSanitizer,
    create_default_sanitizer,
)
from keboola.vcr.validator import (
    OutputSnapshot,
    ValidationDiff,
    ValidationResult,
    capture_output_snapshot,
    save_output_snapshot,
    validate_output_snapshot,
)

from .tester import VCRDataDirTester, VCRTestDataDir, get_test_cases

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
    "QueryParamSanitizer",
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
