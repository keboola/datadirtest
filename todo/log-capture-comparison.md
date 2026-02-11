# Plan: Add Log Capture and Comparison to VCR Tests

## Context

VCR tests currently compare only output **files** (CSVs, manifests). There's no way to verify a component's **log output** or **exit code**. This is a practical problem: configs that fail with `UserException` (exit 1) vs `ApplicationError` (exit 2) produce different platform-visible logs, but the test framework can't distinguish them. Component-meta already has a manual `_SafeVCRTestDataDir` mixin that catches `SystemExit` as boilerplate — this feature formalizes and eliminates that pattern.

**Goal:** Capture component logs and exit code during VCR recording, store them as `logs.json` alongside cassettes, and compare them during replay — same log output the user would see on the platform.

## Design

### Storage: `logs.json` alongside `requests.json`

```
cassettes/
    requests.json     # HTTP interactions (existing)
    logs.json         # Component logs + exit code (NEW)
```

```json
{
  "exit_code": 1,
  "logs": [
    {"level": "INFO", "logger": "src.component", "message": "Starting extraction..."},
    {"level": "ERROR", "logger": "src.component", "message": "UserException: missing field 'account_id'"}
  ]
}
```

### Log capture mechanism

Attach a `LogCaptureHandler` to the root logger before running the component. Filter out framework noise (`vcr`, `urllib3`, `freezegun`, `datadirtest`). Catch `SystemExit` from `exit(1)`/`exit(2)` and record the exit code instead of letting it propagate.

### Comparison with normalizers (scrubbing)

Full message comparison by default. Dynamic values (timestamps, UUIDs, numeric counts) are scrubbed via **log normalizers** — regex-based patterns applied before comparison. Works the same way as VCR sanitizers: there are built-in defaults, and tests can provide custom normalizers.

**Built-in normalizers** (always applied):
- ISO timestamps → `<TIMESTAMP>`
- UUIDs → `<UUID>`
- Epoch timestamps (10+ digits) → `<EPOCH>`

**Custom normalizers**: Per-test overridable via the same pattern as VCR sanitizers (pass a list of `(pattern, replacement)` tuples).

### SystemExit handling

`run_with_log_capture()` catches `SystemExit`, records the exit code, and does NOT re-raise. This lets the test continue to output file comparison. During replay, exit code is compared exactly. This eliminates the `_SafeVCRTestDataDir` boilerplate from component-meta.

## Changes

**Repo:** `datadirtest`
**Branch:** `feature/vcr-testing`

### 1. New file: `datadirtest/vcr/log_capture.py`

Self-contained module with no dependencies on other VCR modules.

**Classes/functions:**

```python
# --- Data classes ---

@dataclass
class CapturedLog:
    level: str          # e.g., "INFO", "ERROR"
    logger_name: str    # e.g., "src.component"
    message: str        # The formatted log message

@dataclass
class ComponentRunResult:
    exit_code: Optional[int]    # None = clean exit, 1 = UserException, 2 = AppError
    logs: List[CapturedLog]

    def to_dict() -> dict       # Serialize to JSON-compatible dict
    @classmethod
    def from_dict(data) -> ...  # Deserialize

@dataclass
class LogComparisonResult:
    success: bool
    exit_code_match: bool
    message_diffs: List[str]    # Per-line diffs
    summary: str                # Human-readable summary

    def format_output(verbose: bool) -> str

# --- Log capture ---

DEFAULT_IGNORED_LOGGERS = frozenset({"vcr", "urllib3", "freezegun", "datadirtest", "filelock"})

class LogCaptureHandler(logging.Handler):
    """Captures log records to a list, filtering ignored loggers."""
    def __init__(self, ignored_loggers=DEFAULT_IGNORED_LOGGERS)
    def emit(self, record: LogRecord)

# --- Normalizers (scrubbing) ---

DEFAULT_NORMALIZERS = [
    (r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}[\w:.+-]*", "<TIMESTAMP>"),
    (r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "<UUID>"),
    (r"\b\d{10,13}\b", "<EPOCH>"),
]

def normalize_message(message: str, normalizers: List[Tuple[str, str]]) -> str:
    """Apply regex normalizers to a message."""

# --- Log sanitization (secrets) ---

class LogSanitizer:
    """Replaces secret values in log messages (reuses secret values from VCR secrets dict)."""
    def __init__(self, secrets: Dict[str, Any])
    def sanitize(self, result: ComponentRunResult) -> ComponentRunResult

# --- Core functions ---

def run_with_log_capture(
    component_runner: Callable,
    ignored_loggers: Optional[Set[str]] = None,
) -> ComponentRunResult:
    """Run component while capturing logs and catching SystemExit."""

def save_logs(result: ComponentRunResult, logs_path: Path) -> None
def load_logs(logs_path: Path) -> ComponentRunResult

def compare_logs(
    recorded: ComponentRunResult,
    replayed: ComponentRunResult,
    normalizers: Optional[List[Tuple[str, str]]] = None,
) -> LogComparisonResult:
    """Compare recorded vs replayed: exit code exact, messages normalized then compared."""
```

### 2. Modify `datadirtest/vcr/recorder.py`

**New constructor parameters:**
```python
def __init__(
    self,
    ...,
    capture_logs: bool = True,
    log_normalizers: Optional[List[Tuple[str, str]]] = None,
    ignored_loggers: Optional[Set[str]] = None,
):
```

New instance attributes:
```python
self.capture_logs = capture_logs
self.log_normalizers = log_normalizers
self.ignored_loggers = ignored_loggers
self.logs_path = self.cassette_dir / "logs.json"
self.last_run_result: Optional[ComponentRunResult] = None
self.last_log_comparison: Optional[LogComparisonResult] = None
```

**Modify `record()`** — wrap `component_runner` with log capture:
```python
def record(self, component_runner):
    ...
    def wrapped_runner():
        if self.capture_logs:
            result = run_with_log_capture(component_runner, self.ignored_loggers)
            # Sanitize secrets from log messages
            if self.secrets:
                sanitizer = LogSanitizer(self.secrets)
                result = sanitizer.sanitize(result)
            self.last_run_result = result
            save_logs(result, self.logs_path)
        else:
            component_runner()

    # Use wrapped_runner instead of component_runner in freeze_time/vcr contexts
    ...
```

**Modify `replay()`** — capture logs and compare against stored:
```python
def replay(self, component_runner):
    ...
    def wrapped_runner():
        if self.capture_logs:
            result = run_with_log_capture(component_runner, self.ignored_loggers)
            self.last_run_result = result
            # Compare with recorded logs if they exist
            if self.logs_path.exists():
                recorded = load_logs(self.logs_path)
                self.last_log_comparison = compare_logs(
                    recorded, result, normalizers=self.log_normalizers
                )
        else:
            component_runner()

    # Use wrapped_runner instead of component_runner in freeze_time/vcr contexts
    ...
```

### 3. Modify `datadirtest/vcr/__init__.py`

**VCRTestDataDir** — new parameters:
```python
def __init__(
    self,
    ...,
    capture_logs: bool = True,
    log_normalizers: Optional[List[tuple]] = None,
    assert_log_comparison: bool = True,
):
```

Pass `capture_logs` and `log_normalizers` through `_setup_vcr()` to `VCRRecorder.from_test_dir()`.

**Add assertion in `run_component()`** — after replay, check log comparison:
```python
def run_component(self):
    # ... existing mode logic (record/replay/auto) ...

    # After replay, assert log comparison
    if (self.assert_log_comparison
            and self.vcr_recorder
            and self.vcr_recorder.last_log_comparison
            and not self.vcr_recorder.last_log_comparison.success):
        self.fail(self.vcr_recorder.last_log_comparison.format_output(verbose=self.verbose))
```

**VCRDataDirTester** — same new parameters, wired through `__init__` and `_build_dir_test_suite()`.

### 4. Update `__init__.py` exports

Add to `__all__`: `ComponentRunResult`, `LogComparisonResult`, `run_with_log_capture`, `compare_logs`

## Critical files

| File | Action |
|------|--------|
| `datadirtest/vcr/log_capture.py` | **NEW** — log capture handler, comparison, normalizers, sanitizer |
| `datadirtest/vcr/recorder.py` | Modify `__init__`, `record()`, `replay()` to integrate log capture |
| `datadirtest/vcr/__init__.py` | Wire parameters through VCRTestDataDir/VCRDataDirTester, add assertion |

## Backward compatibility

- Tests without `logs.json` → log comparison silently skipped
- `capture_logs=True` by default → new cassettes automatically get `logs.json`
- `assert_log_comparison=True` by default → mismatches fail the test
- Existing `_SafeVCRTestDataDir` mixin in component-meta can drop its `run_component()` override since SystemExit is now caught internally

## Verification

1. **Unit test**: Call `run_with_log_capture()` with a function that logs and calls `exit(1)` — verify exit_code=1 and logs captured
2. **Round-trip test**: `save_logs()` then `load_logs()` — verify identical
3. **Comparison test**: Create two `ComponentRunResult`s with matching/differing content — verify `compare_logs()` detects correctly
4. **Normalizer test**: Messages with timestamps/UUIDs normalize before comparison
5. **Integration**: Re-record a component-meta test cassette → verify `logs.json` created. Replay → verify comparison passes
6. **component-meta**: Run `uv run pytest tests/test_datadir.py -v` — existing tests without `logs.json` still pass (backward compat)
