"""Unit tests for keboola.datadirtest.vcr.tester — DB VCR integration."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from keboola.datadirtest.vcr import DBAdapter, OracleDBAdapter, VCRDataDirTester, VCRTestDataDir
from keboola.datadirtest.vcr.tester import _load_vcr_sanitizers_from_script

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeAdapter(DBAdapter):
    """Minimal concrete DBAdapter for testing (no real driver needed)."""

    @property
    def driver_name(self) -> str:
        return "fake"

    def patch_for_record(self, interaction_log):
        pass

    def patch_for_replay(self, interactions):
        pass

    def unpatch(self):
        pass


def _make_test_dir(tmp_path: Path) -> Path:
    """Create the minimal directory structure expected by TestDataDir.

    _create_temporary_copy copies orig_dir → /tmp/.../test_data, then
    _apply_env_variables opens source_config_path = test_data/source/data/config.json.
    So config.json must live at source/data/config.json inside the original dir.
    """
    test_dir = tmp_path / "test_case"
    (test_dir / "source" / "data" / "in").mkdir(parents=True)
    (test_dir / "source" / "data" / "out").mkdir(parents=True)
    (test_dir / "source" / "data" / "config.json").write_text("{}")
    (test_dir / "expected" / "data" / "out" / "tables").mkdir(parents=True)
    (test_dir / "expected" / "data" / "out" / "files").mkdir(parents=True)
    return test_dir


def _make_vcr_test_data_dir(tmp_path: Path, db_adapter=None):
    """Return a VCRTestDataDir with VCR recorder mocked out."""
    test_dir = _make_test_dir(tmp_path)
    script = str(tmp_path / "src" / "component.py")

    with (
        patch("keboola.datadirtest.vcr.tester.VCRRecorder.from_test_dir") as mock_recorder,
        patch("keboola.datadirtest.vcr.tester._load_vcr_sanitizers_from_script", return_value=[]),
    ):
        mock_recorder.return_value = MagicMock()
        instance = VCRTestDataDir(
            data_dir=str(test_dir),
            component_script=script,
            db_adapter=db_adapter,
        )
        instance._recorder_call_args = mock_recorder.call_args  # ty: ignore[unresolved-attribute]

    return instance


def _make_tester(tmp_path: Path, db_adapter=None) -> VCRDataDirTester:
    """Return a VCRDataDirTester with DataDirTester.__init__ bypassed."""
    func_dir = tmp_path / "functional"
    func_dir.mkdir(exist_ok=True)
    script = str(tmp_path / "component.py")

    with patch("keboola.datadirtest.datadirtest.DataDirTester.__init__", return_value=None):
        tester = VCRDataDirTester(
            data_dir=str(func_dir),
            component_script=script,
            db_adapter=db_adapter,
        )

    # Attributes normally set by DataDirTester.__init__
    tester._component_script = script
    tester._context_parameters = {"db_adapter": db_adapter}
    tester._artifact_current_destination = "runs"
    tester._save_output = False
    tester._test_class = VCRTestDataDir
    return tester


# ---------------------------------------------------------------------------
# Imports — DBAdapter and OracleDBAdapter re-exported from datadirtest.vcr
# ---------------------------------------------------------------------------


class TestDBAdapterImports:
    def test_dbadapter_importable_from_datadirtest_vcr(self):
        assert DBAdapter is not None

    def test_oracledbadapter_importable_from_datadirtest_vcr(self):
        assert OracleDBAdapter is not None

    def test_fake_adapter_is_dbadapter(self):
        assert isinstance(_FakeAdapter(), DBAdapter)


# ---------------------------------------------------------------------------
# VCRTestDataDir._setup_vcr — db_adapter flows to VCRRecorder.from_test_dir
# ---------------------------------------------------------------------------


class TestVCRTestDataDirSetupVCR:
    def _make_and_setup(self, tmp_path, db_adapter=None):
        """Instantiate VCRTestDataDir and explicitly call setUp() (unittest runner does not)."""
        test_dir = _make_test_dir(tmp_path)
        with (
            patch("keboola.datadirtest.vcr.tester.VCRRecorder.from_test_dir") as mock_recorder,
            patch("keboola.datadirtest.vcr.tester._load_vcr_sanitizers_from_script", return_value=[]),
        ):
            mock_recorder.return_value = MagicMock()
            instance = VCRTestDataDir(
                data_dir=str(test_dir),
                component_script=str(tmp_path / "src" / "component.py"),
                db_adapter=db_adapter,
            )
            # setUp() calls _setup_vcr() which calls VCRRecorder.from_test_dir.
            # Must be called inside the patch context.
            instance.setUp()
            call_kwargs = mock_recorder.call_args[1]
        return instance, call_kwargs

    def test_db_adapter_passed_as_db_adapters_list(self, tmp_path):
        adapter = _FakeAdapter()
        _, kwargs = self._make_and_setup(tmp_path, db_adapter=adapter)
        assert kwargs["db_adapters"] == [adapter]

    def test_no_db_adapter_passes_empty_list(self, tmp_path):
        _, kwargs = self._make_and_setup(tmp_path, db_adapter=None)
        assert kwargs["db_adapters"] == []

    def test_log_normalizer_always_injected(self, tmp_path):
        _, kwargs = self._make_and_setup(tmp_path)
        assert "log_normalizers" in kwargs
        assert len(kwargs["log_normalizers"]) == 1

    def test_db_adapter_stored_on_instance(self, tmp_path):
        adapter = _FakeAdapter()
        instance = _make_vcr_test_data_dir(tmp_path, db_adapter=adapter)
        assert instance.db_adapter is adapter

    def test_no_db_adapter_stored_as_none(self, tmp_path):
        instance = _make_vcr_test_data_dir(tmp_path, db_adapter=None)
        assert instance.db_adapter is None


# ---------------------------------------------------------------------------
# VCRDataDirTester — db_adapter stored and put in vcr_context
# ---------------------------------------------------------------------------


class TestVCRDataDirTesterInit:
    def test_db_adapter_stored_on_tester(self, tmp_path):
        adapter = _FakeAdapter()
        tester = _make_tester(tmp_path, db_adapter=adapter)
        assert tester.db_adapter is adapter

    def test_no_db_adapter_defaults_to_none(self, tmp_path):
        tester = _make_tester(tmp_path)
        assert tester.db_adapter is None


# ---------------------------------------------------------------------------
# _build_dir_test_suite — chained path: db_adapter in _extra_test_kwargs
# ---------------------------------------------------------------------------


class TestBuildDirTestSuite:
    def test_chained_test_gets_db_adapter_in_kwargs(self, tmp_path):
        """The chained path must forward db_adapter so it reaches VCRTestDataDir
        via TestChainedDatadirTest._extra_test_kwargs."""
        adapter = _FakeAdapter()
        tester = _make_tester(tmp_path, db_adapter=adapter)

        # A chained dir has subdirectories but no top-level 'source'
        chained_dir = tmp_path / "chained"
        (chained_dir / "step1").mkdir(parents=True)

        captured_kwargs: dict = {}

        def capturing_init(self_inner, *args, **kwargs):
            captured_kwargs.update(kwargs)
            self_inner._extra_test_kwargs = kwargs

        # TestChainedDatadirTest is imported locally inside _build_dir_test_suite
        # from ..datadirtest, so patch it at the source module.
        with patch("keboola.datadirtest.datadirtest.TestChainedDatadirTest.__init__", capturing_init):
            tester._build_dir_test_suite([str(chained_dir)])

        assert "db_adapter" in captured_kwargs
        assert captured_kwargs["db_adapter"] is adapter

    def test_chained_test_none_db_adapter_passed_explicitly(self, tmp_path):
        """Baseline: db_adapter=None is still passed explicitly (not missing)."""
        tester = _make_tester(tmp_path, db_adapter=None)

        chained_dir = tmp_path / "chained2"
        (chained_dir / "step1").mkdir(parents=True)

        captured_kwargs: dict = {}

        def capturing_init(self_inner, *args, **kwargs):
            captured_kwargs.update(kwargs)
            self_inner._extra_test_kwargs = kwargs

        with patch("keboola.datadirtest.datadirtest.TestChainedDatadirTest.__init__", capturing_init):
            tester._build_dir_test_suite([str(chained_dir)])

        assert "db_adapter" in captured_kwargs
        assert captured_kwargs["db_adapter"] is None

    def test_non_chained_test_gets_db_adapter(self, tmp_path):
        """Non-chained path must pass db_adapter as an explicit kwarg."""
        adapter = _FakeAdapter()
        tester = _make_tester(tmp_path, db_adapter=adapter)

        # A normal test dir has a 'source' subdirectory
        normal_dir = tmp_path / "normal_test"
        (normal_dir / "source" / "data" / "in").mkdir(parents=True)
        (normal_dir / "source" / "data" / "out").mkdir(parents=True)
        (normal_dir / "source" / "data" / "config.json").write_text("{}")
        (normal_dir / "expected" / "data" / "out" / "tables").mkdir(parents=True)
        (normal_dir / "expected" / "data" / "out" / "files").mkdir(parents=True)

        captured_kwargs: dict = {}

        def capturing_init(self_inner, *args, **kwargs):
            captured_kwargs.update(kwargs)
            self_inner.db_adapter = kwargs.get("db_adapter")

        with patch.object(VCRTestDataDir, "__init__", capturing_init):
            tester._build_dir_test_suite([str(normal_dir)])

        assert "db_adapter" in captured_kwargs
        assert captured_kwargs["db_adapter"] is adapter


# ---------------------------------------------------------------------------
# run_component — SDK VCR suppression: debug log on ImportError
# ---------------------------------------------------------------------------


class TestRunComponentImportError:
    def test_import_error_emits_debug_not_warning(self, tmp_path, caplog):
        """When keboola.component is absent, a DEBUG log is emitted (not warning/error)."""
        import logging

        instance = _make_vcr_test_data_dir(tmp_path)
        instance._run_component_with_vcr = lambda: None  # no-op

        # Remove keboola.component.base from sys.modules so the import fails
        saved = sys.modules.pop("keboola.component.base", None)
        saved_parent = sys.modules.pop("keboola.component", None)
        try:
            with caplog.at_level(logging.DEBUG, logger="keboola.datadirtest.vcr.tester"):
                instance.run_component()
        finally:
            if saved is not None:
                sys.modules["keboola.component.base"] = saved
            if saved_parent is not None:
                sys.modules["keboola.component"] = saved_parent

        debug_messages = [r.message for r in caplog.records if r.levelno == logging.DEBUG]
        assert any("keboola.component" in m or "suppression" in m for m in debug_messages)


# ---------------------------------------------------------------------------
# _load_vcr_sanitizers_from_script — returns empty list on failure/missing
# ---------------------------------------------------------------------------


class TestLoadVCRSanitizers:
    def test_returns_empty_list_for_nonexistent_script(self, tmp_path):
        result = _load_vcr_sanitizers_from_script(str(tmp_path / "missing.py"))
        assert result == []

    def test_returns_empty_list_for_script_without_vcr_sanitizers(self, tmp_path):
        script = tmp_path / "component.py"
        script.write_text("x = 1\n")
        result = _load_vcr_sanitizers_from_script(str(script))
        assert result == []

    def test_returns_sanitizers_when_defined(self, tmp_path):
        script = tmp_path / "component.py"
        script.write_text("VCR_SANITIZERS = ['fake_sanitizer']\n")
        result = _load_vcr_sanitizers_from_script(str(script))
        assert result == ["fake_sanitizer"]
