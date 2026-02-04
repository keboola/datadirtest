"""
Test scaffolder for creating test folder structures.

This module provides functionality to generate test folder structures
from configuration definitions, optionally recording HTTP cassettes.
"""

import json
import logging
import os
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ScaffolderError(Exception):
    """Base exception for scaffolder errors."""

    pass


class TestScaffolder:
    """
    Creates test folder structure from config definitions.

    This class generates the standard datadirtest folder structure
    from a JSON file containing test definitions. It can optionally
    run the component and record HTTP cassettes for each test.

    Example definitions file:
        [
            {
                "name": "test_basic_extraction",
                "config": {
                    "parameters": {"endpoint": "/api/data"},
                    "authorization": {"token": "{{secret.token}}"}
                },
                "secrets": {"token": "real_api_key"},
                "description": "Basic extraction test"
            }
        ]
    """

    SECRET_PLACEHOLDER_PATTERN = re.compile(r"\{\{secret\.([^}]+)\}\}")

    def __init__(self):
        """Initialize test scaffolder."""
        pass

    def scaffold_from_json(
        self,
        definitions_file: Path,
        output_dir: Path,
        component_script: Optional[Path] = None,
        record: bool = True,
        freeze_time_at: Optional[str] = "2025-01-01T12:00:00",
    ) -> List[Path]:
        """
        Create test folders from definitions file.

        Args:
            definitions_file: JSON file with list of test configs
            output_dir: Directory to create test folders in
            component_script: Path to component script (required if record=True)
            record: Whether to run component and record cassettes
            freeze_time_at: ISO timestamp for time freezing during recording

        Returns:
            List of created test folder paths

        Raises:
            ScaffolderError: If definitions file is invalid or recording fails
        """
        definitions_file = Path(definitions_file)
        output_dir = Path(output_dir)

        if not definitions_file.exists():
            raise ScaffolderError(f"Definitions file not found: {definitions_file}")

        try:
            with open(definitions_file, "r") as f:
                definitions = json.load(f)
        except json.JSONDecodeError as e:
            raise ScaffolderError(f"Invalid JSON in definitions file: {e}")

        if not isinstance(definitions, list):
            raise ScaffolderError("Definitions file must contain a JSON array")

        if record and component_script is None:
            raise ScaffolderError("component_script is required when record=True")

        created_paths = []
        for definition in definitions:
            test_path = self._scaffold_single_test(
                definition=definition,
                output_dir=output_dir,
                component_script=component_script,
                record=record,
                freeze_time_at=freeze_time_at,
            )
            created_paths.append(test_path)

        return created_paths

    def scaffold_from_dict(
        self,
        definition: Dict[str, Any],
        output_dir: Path,
        component_script: Optional[Path] = None,
        record: bool = True,
        freeze_time_at: Optional[str] = "2025-01-01T12:00:00",
    ) -> Path:
        """
        Create a single test folder from a definition dict.

        Args:
            definition: Test definition dictionary
            output_dir: Directory to create test folder in
            component_script: Path to component script
            record: Whether to run component and record cassette
            freeze_time_at: ISO timestamp for time freezing

        Returns:
            Path to created test folder
        """
        return self._scaffold_single_test(
            definition=definition,
            output_dir=Path(output_dir),
            component_script=Path(component_script) if component_script else None,
            record=record,
            freeze_time_at=freeze_time_at,
        )

    def _scaffold_single_test(
        self,
        definition: Dict[str, Any],
        output_dir: Path,
        component_script: Optional[Path],
        record: bool,
        freeze_time_at: Optional[str],
    ) -> Path:
        """Create folder structure for a single test."""
        # Validate definition
        if "name" not in definition:
            raise ScaffolderError("Test definition missing required 'name' field")
        if "config" not in definition:
            raise ScaffolderError(f"Test '{definition['name']}' missing required 'config' field")

        test_name = definition["name"]
        config = definition["config"]
        secrets = definition.get("secrets", {})
        _ = definition.get("description", "")  # Reserved for future use

        # Create directory structure
        test_dir = output_dir / test_name
        source_data_dir = test_dir / "source" / "data"
        expected_out_dir = test_dir / "expected" / "data" / "out"

        # Create directories
        source_data_dir.mkdir(parents=True, exist_ok=True)
        (source_data_dir / "in").mkdir(exist_ok=True)
        (source_data_dir / "out" / "tables").mkdir(parents=True, exist_ok=True)
        (source_data_dir / "out" / "files").mkdir(parents=True, exist_ok=True)
        expected_out_dir.mkdir(parents=True, exist_ok=True)
        (expected_out_dir / "tables").mkdir(exist_ok=True)
        (expected_out_dir / "files").mkdir(exist_ok=True)

        # Create config.json with placeholders
        config_with_placeholders = self._replace_secrets_with_placeholders(config, secrets)
        with open(source_data_dir / "config.json", "w") as f:
            json.dump(config_with_placeholders, f, indent=2)

        # Create config.secrets.json if there are secrets
        if secrets:
            with open(source_data_dir / "config.secrets.json", "w") as f:
                json.dump(secrets, f, indent=2)

        # Create empty input state
        with open(source_data_dir / "in" / "state.json", "w") as f:
            json.dump({}, f)

        logger.info(f"Created test folder structure: {test_dir}")

        # Record cassette if requested
        if record and component_script:
            self._record_test(
                test_dir=test_dir,
                source_data_dir=source_data_dir,
                expected_out_dir=expected_out_dir,
                component_script=component_script,
                config=config,
                freeze_time_at=freeze_time_at,
            )

        return test_dir

    def _replace_secrets_with_placeholders(
        self,
        config: Dict[str, Any],
        secrets: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Replace secret values in config with placeholders.

        Looks for values matching secrets and replaces them with
        {{secret.key}} placeholders.
        """
        if not secrets:
            return config

        def replace_in_value(value: Any, secrets: Dict[str, Any]) -> Any:
            if isinstance(value, str):
                # Check if this value matches any secret
                for secret_key, secret_value in secrets.items():
                    if isinstance(secret_value, str) and value == secret_value:
                        return f"{{{{secret.{secret_key}}}}}"
                return value
            elif isinstance(value, dict):
                return {k: replace_in_value(v, secrets) for k, v in value.items()}
            elif isinstance(value, list):
                return [replace_in_value(item, secrets) for item in value]
            else:
                return value

        return replace_in_value(config, secrets)

    def _record_test(
        self,
        test_dir: Path,
        source_data_dir: Path,
        expected_out_dir: Path,
        component_script: Path,
        config: Dict[str, Any],
        freeze_time_at: Optional[str],
    ) -> None:
        """Run component and record cassette."""
        from .recorder import VCRRecorder
        from .validator import save_output_snapshot

        # Write full config (with real secrets) for recording
        with open(source_data_dir / "config.json", "w") as f:
            json.dump(config, f, indent=2)

        # Create recorder
        recorder = VCRRecorder.from_test_dir(
            test_data_dir=source_data_dir,
            freeze_time_at=freeze_time_at,
        )

        # Run component with recording
        def run_component():
            from runpy import run_path

            os.environ["KBC_DATADIR"] = str(source_data_dir)
            run_path(str(component_script), run_name="__main__")

        try:
            recorder.record(run_component)
            logger.info(f"Recorded cassette for {test_dir.name}")
        except Exception as e:
            logger.error(f"Failed to record cassette for {test_dir.name}: {e}")
            raise ScaffolderError(f"Recording failed for {test_dir.name}: {e}")

        # Copy outputs to expected folder
        source_out = source_data_dir / "out"
        if source_out.exists():
            for subdir in ["tables", "files"]:
                src = source_out / subdir
                dst = expected_out_dir / subdir
                if src.exists():
                    for item in src.iterdir():
                        if item.is_file():
                            shutil.copy2(item, dst / item.name)

        # Capture output snapshot
        try:
            save_output_snapshot(source_data_dir, output_subdir="out")
            logger.info(f"Saved output snapshot for {test_dir.name}")
        except Exception as e:
            logger.warning(f"Failed to save snapshot for {test_dir.name}: {e}")

        # Restore config with placeholders
        secrets_path = source_data_dir / "config.secrets.json"
        if secrets_path.exists():
            with open(secrets_path, "r") as f:
                secrets = json.load(f)
            config_with_placeholders = self._replace_secrets_with_placeholders(config, secrets)
            with open(source_data_dir / "config.json", "w") as f:
                json.dump(config_with_placeholders, f, indent=2)


def scaffold_tests(
    definitions: List[Dict[str, Any]],
    output_dir: Path,
    component_script: Optional[Path] = None,
    record: bool = True,
    freeze_time_at: Optional[str] = "2025-01-01T12:00:00",
) -> List[Path]:
    """
    Convenience function to scaffold multiple tests.

    Args:
        definitions: List of test definition dictionaries
        output_dir: Directory to create test folders in
        component_script: Path to component script
        record: Whether to run component and record cassettes
        freeze_time_at: ISO timestamp for time freezing

    Returns:
        List of created test folder paths
    """
    scaffolder = TestScaffolder()
    created_paths = []

    for definition in definitions:
        path = scaffolder.scaffold_from_dict(
            definition=definition,
            output_dir=output_dir,
            component_script=component_script,
            record=record,
            freeze_time_at=freeze_time_at,
        )
        created_paths.append(path)

    return created_paths
