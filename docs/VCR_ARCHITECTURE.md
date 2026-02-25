# VCR Integration Plan for Datadirtest

## Overview

Integrate VCR (Video Cassette Recording) into the `datadirtest` framework to enable:
1. **Recording mode**: Run tests with real credentials → record HTTP interactions as cassettes
2. **Replay mode**: Run tests without credentials → replay cassettes (CI-friendly)
3. **Scaffolding**: Generate test folder structure from a list of configs

---

## Architecture

### New Module Structure

```
datadirtest/
├── datadirtest/
│   ├── __init__.py              # Add VCRDataDirTester export
│   ├── datadirtest.py           # Existing (unchanged)
│   ├── vcr/                     # NEW: VCR submodule
│   │   ├── __init__.py          # Exports: VCRTestDataDir, VCRDataDirTester, Sanitizer
│   │   ├── recorder.py          # VCRRecorder class - handles recording/replay
│   │   ├── sanitizers.py        # BaseSanitizer + built-in sanitizers
│   │   ├── validator.py         # Hash-based output validation with diff
│   │   ├── scaffolder.py        # Test structure generator from configs
│   │   └── pytest_plugin.py     # Pytest fixtures (optional registration)
│   └── __main__.py              # Update CLI with VCR flags
```

### Cassette Storage (per test)

```
tests/functional/
└── test-name/
    └── source/
        └── data/
            ├── config.json           # Component config (with placeholders)
            ├── config.secrets.json   # Real credentials (gitignored)
            ├── cassettes/            # NEW: VCR recordings
            │   └── requests.json     # vcrpy cassette file
            └── output_snapshot.json  # NEW: Hash-based output validation
```

---

## Core Components

### 1. VCRRecorder (`vcr/recorder.py`)

Handles HTTP recording and replay using vcrpy.

```python
class VCRRecorder:
    """Records and replays HTTP interactions for component tests."""

    def __init__(
        self,
        cassette_dir: Path,
        secrets: dict = None,
        sanitizers: list[BaseSanitizer] = None,
        freeze_time_at: str = "2025-01-01T12:00:00"
    ):
        ...

    @classmethod
    def from_test_dir(cls, test_data_dir: Path, **kwargs) -> "VCRRecorder":
        """Create recorder from test directory structure."""
        ...

    def record(self, component_runner: Callable) -> None:
        """Record HTTP interactions while running component."""
        ...

    def replay(self, component_runner: Callable) -> None:
        """Replay recorded HTTP interactions."""
        ...

    def has_cassette(self) -> bool:
        """Check if cassette exists for replay."""
        ...
```

**Key Features:**
- Loads secrets from `config.secrets.json`, merges with `config.json`
- Always freezes time (configurable timestamp)
- Applies sanitizers before saving cassette
- Uses vcrpy with JSON cassette format

### 2. Sanitizers (`vcr/sanitizers.py`)

Pluggable sanitization system with overloadable hooks.

```python
class BaseSanitizer:
    """Base class for request/response sanitization."""

    def before_record_request(self, request) -> request:
        """Sanitize request before recording. Override in subclass."""
        return request

    def before_record_response(self, response) -> response:
        """Sanitize response before recording. Override in subclass."""
        return response


class TokenSanitizer(BaseSanitizer):
    """Replaces auth tokens with placeholder."""

    def __init__(self, tokens: list[str], replacement: str = "REDACTED"):
        ...


class HeaderSanitizer(BaseSanitizer):
    """Filters headers to whitelist only safe ones."""

    SAFE_HEADERS = ["content-type", "content-length"]
    ...


class CompositeSanitizer(BaseSanitizer):
    """Combines multiple sanitizers."""

    def __init__(self, sanitizers: list[BaseSanitizer]):
        ...
```

**Custom Sanitizer per Test:**
Tests can define custom sanitizers in `source/data/sanitizers.py`:

```python
# source/data/sanitizers.py
from datadirtest.vcr import BaseSanitizer

class CustomSanitizer(BaseSanitizer):
    def before_record_request(self, request):
        # Replace account IDs in URLs
        request.uri = request.uri.replace("act_123456", "act_REDACTED")
        return request

def get_sanitizers(config: dict) -> list[BaseSanitizer]:
    """Return sanitizers for this test."""
    return [CustomSanitizer()]
```

### 3. OutputValidator (`vcr/validator.py`)

Hash-based validation with diff output on failure.

```python
class OutputSnapshot:
    """Captures and validates output state."""

    def capture(self, output_dir: Path) -> dict:
        """Capture snapshot of outputs (hashes + metadata)."""
        return {
            "tables": {
                "main.csv": {
                    "hash": "sha256:abc123...",
                    "row_count": 150,
                    "columns": ["id", "name", "value"],
                    "size_bytes": 4096
                }
            },
            "files": {...}
        }

    def validate(self, output_dir: Path, expected: dict, verbose: bool = False) -> ValidationResult:
        """Validate outputs against snapshot."""
        ...


class ValidationResult:
    success: bool
    summary: str           # "2 files changed, 1 file added"
    file_diffs: dict       # {filename: unified_diff} - populated if verbose

    def format_output(self, verbose: bool = False) -> str:
        """Format validation result for display."""
        ...
```

**Validation Modes:**
- Default: File-level summary ("main.csv: hash mismatch, 150→175 rows")
- Verbose (`--verbose`): Full unified diff of changed files

### 4. Scaffolder (`vcr/scaffolder.py`)

Generates test folder structure from configs.

```python
class TestScaffolder:
    """Creates test folder structure from config definitions."""

    def scaffold_from_json(
        self,
        definitions_file: Path,  # JSON with list of test configs
        output_dir: Path,        # tests/functional/
        component_script: Path,  # src/component.py
        record: bool = True      # Run component and record cassettes
    ) -> list[Path]:
        """
        Create test folders from definitions.

        definitions_file format:
        [
            {
                "name": "test_basic_extraction",
                "config": {"parameters": {...}, "authorization": {...}},
                "description": "Basic extraction test"
            },
            ...
        ]
        """
        ...
```

**Scaffolding Workflow:**
1. Read definitions JSON
2. For each test config:
   - Create folder structure: `test_name/source/data/`, `test_name/expected/data/out/`
   - Write `config.json` (with secrets placeholders)
   - Write `config.secrets.json` (with real credentials)
   - If `record=True`: Run component, record cassette, capture output snapshot
   - Copy outputs to `expected/data/out/`

### 5. VCRTestDataDir (`vcr/__init__.py`)

Extended test class with VCR support.

```python
class VCRTestDataDir(TestDataDir):
    """TestDataDir with VCR recording/replay support."""

    def __init__(self, *args, vcr_mode: str = "auto", **kwargs):
        """
        Args:
            vcr_mode: "record", "replay", or "auto"
                - record: Always record (requires credentials)
                - replay: Always replay (fails if no cassette)
                - auto: Replay if cassette exists, skip if not
        """
        super().__init__(*args, **kwargs)
        self.vcr_mode = vcr_mode
        self.vcr_recorder = None

    def setUp(self):
        super().setUp()
        self._setup_vcr()

    def _setup_vcr(self):
        """Initialize VCR recorder with test-specific config."""
        cassette_dir = self.source_data_dir / "cassettes"
        secrets_file = self.source_data_dir / "config.secrets.json"

        # Load custom sanitizers if defined
        sanitizers = self._load_custom_sanitizers()

        self.vcr_recorder = VCRRecorder(
            cassette_dir=cassette_dir,
            secrets=self._load_secrets(secrets_file),
            sanitizers=sanitizers
        )

    def run_component(self):
        """Run component with VCR wrapping."""
        if self.vcr_mode == "record":
            self.vcr_recorder.record(super().run_component)
        elif self.vcr_mode == "replay":
            self.vcr_recorder.replay(super().run_component)
        else:  # auto
            if self.vcr_recorder.has_cassette():
                self.vcr_recorder.replay(super().run_component)
            else:
                # No cassette, run without VCR (requires real credentials)
                super().run_component()
```

### 6. VCRDataDirTester

Extended tester with VCR CLI support.

```python
class VCRDataDirTester(DataDirTester):
    """DataDirTester with VCR support."""

    def __init__(
        self,
        *args,
        vcr_mode: str = "auto",
        validate_snapshots: bool = True,
        verbose: bool = False,
        **kwargs
    ):
        kwargs.setdefault("test_data_dir_class", VCRTestDataDir)
        super().__init__(*args, **kwargs)
        self.vcr_mode = vcr_mode
        self.validate_snapshots = validate_snapshots
        self.verbose = verbose
```

---

## CLI Interface

Update `__main__.py` to support VCR operations.

```bash
# Run tests with VCR replay (default in CI)
python -m datadirtest tests/functional src/component.py

# Record cassettes (requires credentials)
python -m datadirtest tests/functional src/component.py --record

# Update existing cassettes
python -m datadirtest tests/functional src/component.py --update-cassettes

# Verbose output (show full diffs on validation failure)
python -m datadirtest tests/functional src/component.py --verbose

# Scaffold new tests from definitions
python -m datadirtest scaffold test_definitions.json tests/functional src/component.py

# Scaffold without recording (just create structure)
python -m datadirtest scaffold test_definitions.json tests/functional --no-record
```

---

## Pytest Integration

Optional pytest fixtures in `vcr/pytest_plugin.py`.

```python
# conftest.py
pytest_plugins = ["datadirtest.vcr.pytest_plugin"]

# test_functional.py
def test_component_vcr(vcr_test_runner, test_case):
    result = vcr_test_runner.run(test_case)
    assert result.success
```

**Fixtures Provided:**
- `vcr_test_runner` - Ready-to-use VCRDataDirTester
- `vcr_mode` - Current mode (from CLI/env)
- `functional_tests` - Parametrized test cases from tests/functional/

---

## File Changes Summary

| File | Action | Description |
|------|--------|-------------|
| `datadirtest/vcr/__init__.py` | CREATE | Exports VCRTestDataDir, VCRDataDirTester, sanitizers |
| `datadirtest/vcr/recorder.py` | CREATE | VCRRecorder class (~150 lines) |
| `datadirtest/vcr/sanitizers.py` | CREATE | Sanitizer classes (~100 lines) |
| `datadirtest/vcr/validator.py` | CREATE | OutputSnapshot, ValidationResult (~120 lines) |
| `datadirtest/vcr/scaffolder.py` | CREATE | TestScaffolder (~80 lines) |
| `datadirtest/vcr/pytest_plugin.py` | CREATE | Pytest fixtures (~50 lines) |
| `datadirtest/__init__.py` | MODIFY | Add VCR exports |
| `datadirtest/__main__.py` | MODIFY | Add CLI flags for VCR |
| `setup.py` | MODIFY | Add dependencies: vcrpy, freezegun |
| `README.md` | MODIFY | Add VCR documentation section |

---

## Dependencies

Add to `setup.py`:
```python
install_requires=[
    "pathlib",
    "vcrpy>=4.0.0",
    "freezegun>=1.0.0",
]

extras_require={
    "pytest": ["pytest>=7.0.0"],
}
```

---

## Test Structure Example

After implementation, a test with VCR looks like:

```
tests/functional/
└── test_api_extraction/
    ├── source/
    │   └── data/
    │       ├── config.json              # {"parameters": {"token": "{{secret.token}}"}}
    │       ├── config.secrets.json      # {"token": "real_api_key"} (gitignored)
    │       ├── cassettes/
    │       │   └── requests.json        # Recorded HTTP interactions
    │       ├── output_snapshot.json     # Hash-based output validation
    │       └── sanitizers.py            # Optional custom sanitizers
    └── expected/
        └── data/
            └── out/
                └── tables/
                    └── main.csv         # Expected output
```

---

## Verification Plan

1. **Unit tests** for each new module:
   - `tests/test_vcr_recorder.py`
   - `tests/test_vcr_sanitizers.py`
   - `tests/test_vcr_validator.py`
   - `tests/test_vcr_scaffolder.py`

2. **Integration tests**:
   - Create sample test with mock HTTP server
   - Test record → replay cycle
   - Test scaffolding workflow
   - Test validation with intentional diff

3. **Manual testing**:
   - Test with a real Keboola component (e.g., simple REST extractor)
   - Verify CI behavior (auto-replay without credentials)

---

## Implementation Order

1. **Phase 1**: Core VCR (`recorder.py`, `sanitizers.py`)
2. **Phase 2**: Validation (`validator.py`)
3. **Phase 3**: Integration (`VCRTestDataDir`, `VCRDataDirTester`)
4. **Phase 4**: CLI updates (`__main__.py`)
5. **Phase 5**: Scaffolding (`scaffolder.py`)
6. **Phase 6**: Pytest plugin (`pytest_plugin.py`)
7. **Phase 7**: Documentation and tests
