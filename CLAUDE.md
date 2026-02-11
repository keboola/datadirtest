# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**datadirtest** is a functional testing framework for Keboola components. It runs a component script against test input data, captures output files/tables, and compares them against expected results. The VCR module (on `feature/vcr-testing` branch) adds HTTP recording/replay for deterministic, credential-free CI testing.

## Commands

```bash
# Install with all dev dependencies (uses uv)
uv pip install -e ".[dev]"

# Run unit tests
pytest tests/

# Run a single test
pytest tests/test_datadirtest.py::TestDataDirTesting::test_name

# Lint
ruff check datadirtest/

# Run functional tests via CLI
python -m datadirtest tests/functional src/component.py
python -m datadirtest tests/functional src/component.py --record    # record VCR cassettes
python -m datadirtest tests/functional src/component.py --replay    # replay mode

# Scaffold new test structure
python -m datadirtest scaffold definitions.json tests/functional src/component.py
```

## Architecture

### Core (`datadirtest/datadirtest.py`)

- **TestDataDir** (unittest.TestCase) — Single functional test. Copies test data to temp dir, runs component script (expects `KBC_DATADIR` env var), compares output against `expected/`.
- **TestChainedDatadirTest** — Runs sequential tests passing `state.json` between them. Tests execute alphabetically (prefix with `01_`, `02_`, etc.).
- **DataDirTester** — Discovers tests in a directory, auto-detects chained vs. single tests, wraps them in unittest.TestSuite and runs them.

### VCR Module (`datadirtest/vcr/`)

Optional (requires `vcrpy`, `freezegun`). Gracefully degrades if not installed.

- **VCRRecorder** (`recorder.py`) — Wraps vcrpy. Records HTTP to `source/data/cassettes/requests.json`. Freezes time via freezegun (default: `2025-01-01T12:00:00`). Loads secrets from `config.secrets.json` and merges into config during recording.
- **VCRTestDataDir** (`__init__.py`) — Extends TestDataDir with VCR. Modes: `record`, `replay`, `auto`.
- **VCRDataDirTester** (`__init__.py`) — Extends DataDirTester, wires VCR parameters to all test instances.
- **Sanitizers** (`sanitizers.py`) — Pluggable system for redacting secrets from cassettes. `BaseSanitizer` ABC with `before_record_request`/`before_record_response` hooks. Built-in: `TokenSanitizer`, `HeaderSanitizer`, `UrlPatternSanitizer`, `BodyFieldSanitizer`, `QueryParameterTokenSanitizer`, `CallbackSanitizer`, `CompositeSanitizer`. Factory: `create_default_sanitizer(secrets)`.
- **OutputSnapshot** (`validator.py`) — SHA256-based hash validation of outputs. Captures file hashes + CSV metadata (row count, columns). Compares against `output_snapshot.json`.
- **TestScaffolder** (`scaffolder.py`) — Generates test folder structure from JSON definitions.
- **pytest plugin** (`pytest_plugin.py`) — Registered as `datadirtest_vcr` entry point. Adds CLI options (`--vcr-record`, `--vcr-replay`, `--no-vcr`, `--freeze-time`, `--validate-snapshots`) and fixtures (`vcr_mode`, `vcr_recorder`, `tester`, `vcr_test_result`).

### CLI (`datadirtest/__main__.py`)

Subcommands: `test` (default), `scaffold`, `snapshot`.

## Test Data Directory Structure

```
tests/functional/test-name/
├── source/data/
│   ├── config.json                 # Component config (supports {{env.VAR}} and {{secret.KEY}} placeholders)
│   ├── config.secrets.json         # Real credentials (gitignored), merged during VCR recording
│   ├── set_up.py / post_run.py / tear_down.py  # Optional lifecycle scripts with run(context: TestDataDir)
│   ├── cassettes/requests.json     # VCR recording
│   ├── output_snapshot.json        # Hash-based validation
│   └── in/files/ , in/tables/
└── expected/data/out/
    ├── files/
    └── tables/
```

## Code Style

- Line length: 120 (ruff and flake8)
- Python 3.8+ compatibility required
- No mandatory runtime dependencies — optional features behind extras (`[vcr]`, `[pytest]`)
