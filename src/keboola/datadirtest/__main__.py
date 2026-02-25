"""
Main entry point for datadirtest CLI.

Usage:
    # Run tests (auto VCR mode - replay if cassettes exist)
    python -m datadirtest tests/functional src/component.py

    # Record cassettes (requires credentials)
    python -m datadirtest tests/functional src/component.py --record

    # Force replay mode (fail if no cassettes)
    python -m datadirtest tests/functional src/component.py --replay

    # Update existing cassettes
    python -m datadirtest tests/functional src/component.py --update-cassettes

    # Verbose output (show full diffs on failure)
    python -m datadirtest tests/functional src/component.py --verbose

    # Scaffold (all defaults — standard repo layout)
    python -m datadirtest scaffold

    # Explicit paths
    python -m datadirtest scaffold --definitions tests/setup/configs.json \
        --output tests/functional --component src/component.py

    # Without recording
    python -m datadirtest scaffold --no-record

    # With secrets file
    python -m datadirtest scaffold --secrets secrets.json

    # Run without VCR (original behavior)
    python -m datadirtest tests/functional src/component.py --no-vcr
"""

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

from .datadirtest import DataDirTester


def create_parser():
    """Create argument parser for CLI."""
    parser = argparse.ArgumentParser(
        description="Run functional tests for Keboola components",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Default test command (when no subcommand specified)
    parser.add_argument(
        "data_dir",
        nargs="?",
        default="./tests/functional",
        help="Path to functional tests directory (default: ./tests/functional)",
    )
    parser.add_argument(
        "component_script",
        nargs="?",
        default="./src/component.py",
        help="Path to component script (default: ./src/component.py)",
    )

    # VCR options
    vcr_group = parser.add_argument_group("VCR options")
    vcr_group.add_argument(
        "--record",
        action="store_true",
        help="Record HTTP interactions (requires credentials)",
    )
    vcr_group.add_argument(
        "--replay",
        action="store_true",
        help="Replay recorded interactions (fail if no cassettes)",
    )
    vcr_group.add_argument(
        "--update-cassettes",
        action="store_true",
        help="Update existing cassettes with new recordings",
    )
    vcr_group.add_argument(
        "--no-vcr",
        action="store_true",
        help="Disable VCR (use original DataDirTester behavior)",
    )
    vcr_group.add_argument(
        "--freeze-time",
        type=str,
        default=None,
        help="ISO timestamp to freeze time at (default: time of recording)",
    )

    # Validation options
    validation_group = parser.add_argument_group("Validation options")
    validation_group.add_argument(
        "--validate-snapshots",
        action="store_true",
        help="Validate outputs against hash-based snapshots",
    )
    validation_group.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output (show full diffs)",
    )

    # Test selection
    parser.add_argument(
        "--tests",
        type=str,
        help="Comma-separated list of test names to run",
    )

    # Scaffold subcommand
    scaffold_parser = subparsers.add_parser(
        "scaffold",
        help="Scaffold test folders from config definitions",
    )
    scaffold_parser.add_argument(
        "--definitions",
        "--definitions-file",
        dest="definitions_file",
        default="tests/setup/configs.json",
        required=False,
        help="JSON file with test definitions (default: tests/setup/configs.json)",
    )
    scaffold_parser.add_argument(
        "--output",
        "--output-dir",
        dest="output_dir",
        default="tests/functional",
        required=False,
        help="Output directory for test folders (default: tests/functional)",
    )
    scaffold_parser.add_argument(
        "--component",
        "--component-script",
        dest="component_script",
        default="src/component.py",
        required=False,
        help="Component script for recording (default: src/component.py)",
    )
    scaffold_parser.add_argument(
        "--input-files",
        dest="input_files_dir",
        default="tests/setup/input_files",
        required=False,
        help="Directory containing CSV files to auto-copy into scaffolded tests (default: tests/setup/input_files)",
    )
    scaffold_parser.add_argument(
        "--no-record",
        action="store_true",
        help="Only create folder structure, don't record cassettes",
    )
    scaffold_parser.add_argument(
        "--secrets",
        type=str,
        default=None,
        help="JSON file with real credentials to deep-merge at recording time",
    )
    scaffold_parser.add_argument(
        "--freeze-time",
        type=str,
        default=None,
        help="ISO timestamp to freeze time at during recording (default: time of recording)",
    )
    scaffold_parser.add_argument(
        "--chain-state",
        action="store_true",
        help="Forward out/state.json from each test to the next (for ERP token refresh)",
    )
    scaffold_parser.add_argument(
        "--regenerate",
        action="store_true",
        help="Delete all existing cassettes and re-record from live API",
    )
    scaffold_parser.add_argument(
        "--add-missing-cassettes",
        action="store_true",
        help="Only record cassettes for tests that don't have one yet",
    )

    # Snapshot subcommand
    snapshot_parser = subparsers.add_parser(
        "snapshot",
        help="Capture output snapshots for tests",
    )
    snapshot_parser.add_argument(
        "test_dir",
        help="Test directory to capture snapshot for",
    )
    snapshot_parser.add_argument(
        "--output-subdir",
        default="out",
        help="Subdirectory containing outputs (default: out)",
    )

    return parser


def get_vcr_mode(args):
    """Determine VCR mode from CLI arguments."""
    if args.record or args.update_cassettes:
        return "record"
    elif args.replay:
        return "replay"
    else:
        return "auto"


def run_tests(args):
    """Run functional tests with optional VCR support."""
    data_dir = Path(args.data_dir).absolute().as_posix()
    component_script = Path(args.component_script).absolute().as_posix()

    # Parse selected tests
    selected_tests = None
    if args.tests:
        selected_tests = [t.strip() for t in args.tests.split(",")]

    if args.no_vcr:
        # Use original DataDirTester without VCR
        tester = DataDirTester(
            data_dir=data_dir,
            component_script=component_script,
            selected_tests=selected_tests,
        )
    else:
        # Use VCR-enabled tester
        try:
            from .vcr import VCRDataDirTester

            vcr_mode = get_vcr_mode(args)
            freeze_time = None if args.freeze_time == "disable" else args.freeze_time

            tester = VCRDataDirTester(
                data_dir=data_dir,
                component_script=component_script,
                selected_tests=selected_tests,
                vcr_mode=vcr_mode,
                vcr_freeze_time=freeze_time,
                validate_snapshots=args.validate_snapshots,
                verbose=args.verbose,
            )
        except ImportError as e:
            print(f"Warning: VCR dependencies not available ({e}), using standard tester")
            tester = DataDirTester(
                data_dir=data_dir,
                component_script=component_script,
                selected_tests=selected_tests,
            )

    tester.run()


def _copy_input_files(created_paths, input_files_dir):
    """Copy input CSV files into scaffolded test directories based on config.json storage mappings."""
    if not input_files_dir.exists():
        return

    for test_dir in created_paths:
        config_path = test_dir / "source" / "data" / "config.json"
        if not config_path.exists():
            continue

        try:
            config = json.loads(config_path.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        storage = config.get("storage", {})

        # Copy table input files
        for entry in storage.get("input", {}).get("tables", []):
            dest = entry.get("destination", "")
            if not dest:
                continue
            src = input_files_dir / dest
            if src.exists():
                target_dir = test_dir / "source" / "data" / "in" / "tables"
                target_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, target_dir / dest)
                print(f"  Copied {src} -> {target_dir / dest}")

        # Copy file input files
        for entry in storage.get("input", {}).get("files", []):
            dest = entry.get("destination", "")
            if not dest:
                continue
            src = input_files_dir / dest
            if src.exists():
                target_dir = test_dir / "source" / "data" / "in" / "files"
                target_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, target_dir / dest)
                print(f"  Copied {src} -> {target_dir / dest}")


def run_scaffold(args):
    """Scaffold test folders from definitions file."""
    try:
        from keboola.vcr.scaffolder import TestScaffolder
    except ImportError as e:
        print(f"Error: Scaffolder dependencies not available: {e}")
        sys.exit(1)

    definitions_file = Path(args.definitions_file)
    output_dir = Path(args.output_dir)
    component_script = Path(args.component_script)

    if not args.no_record and not component_script.exists():
        print(f"Error: component script not found: {component_script}")
        sys.exit(1)

    scaffolder = TestScaffolder()
    if args.freeze_time == "disable":
        freeze_time = None
    elif args.freeze_time is None:
        freeze_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    else:
        freeze_time = args.freeze_time
    secrets_file = Path(args.secrets) if args.secrets else None

    created_paths = scaffolder.scaffold_from_json(
        definitions_file=definitions_file,
        output_dir=output_dir,
        component_script=component_script,
        record=not args.no_record,
        freeze_time_at=freeze_time,
        secrets_file=secrets_file,
        chain_state=args.chain_state,
        regenerate=args.regenerate,
        add_missing=args.add_missing_cassettes,
    )

    print(f"Created {len(created_paths)} test folders:")
    for p in created_paths:
        print(f"  - {p}")

    _copy_input_files(created_paths, Path(args.input_files_dir))


def run_snapshot(args):
    """Capture output snapshot for a test."""
    try:
        from keboola.vcr.validator import save_output_snapshot
    except ImportError as e:
        print(f"Error: VCR dependencies not available: {e}")
        sys.exit(1)

    test_dir = Path(args.test_dir)
    data_dir = test_dir / "source" / "data"

    if not data_dir.exists():
        print(f"Error: Data directory not found: {data_dir}")
        sys.exit(1)

    snapshot_path = save_output_snapshot(
        test_data_dir=data_dir,
        output_subdir=args.output_subdir,
    )

    print(f"Saved snapshot to: {snapshot_path}")


def main():
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if args.command == "scaffold":
        run_scaffold(args)
    elif args.command == "snapshot":
        run_snapshot(args)
    else:
        # Default: run tests
        run_tests(args)


if __name__ == "__main__":
    main()
