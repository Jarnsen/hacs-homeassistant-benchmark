"""Tests for private storage, migration, and export helpers."""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path

from custom_components.benchmark import storage
from custom_components.benchmark.const import (
    LEGACY_HISTORY_FILE,
    LEGACY_META_FILE,
    LEGACY_RESTART_FILE,
)

from .helpers import benchmark_result


class FakeStore:
    """Small controllable replacement for Home Assistant Store."""

    loaded = None
    saved = None

    def __init__(self, *_args, **_kwargs) -> None:
        pass

    async def async_load(self):
        return self.loaded

    async def async_save(self, data) -> None:
        type(self).saved = data


def _write_text(path: Path, value: str) -> None:
    path.write_text(value, encoding="utf-8")


def _exists(path: Path) -> bool:
    return path.exists()


def test_default_and_json_helpers(tmp_path: Path) -> None:
    assert storage.default_stored_data() == {
        "history": [],
        "legacy_history": [],
        "pending_restart": None,
    }
    path = tmp_path / "data.json"
    storage.write_json(str(path), {"text": "ä", "number": 1})
    assert storage._read_json(str(path), {}) == {"text": "ä", "number": 1}
    assert storage._read_json(str(tmp_path / "missing.json"), ["default"]) == [
        "default"
    ]
    path.write_text("not json", encoding="utf-8")
    assert storage._read_json(str(path), None) is None


def test_remove_files_handles_missing_and_os_errors(
    tmp_path: Path, monkeypatch, caplog
) -> None:
    existing = tmp_path / "existing.json"
    existing.write_text("{}", encoding="utf-8")
    storage._remove_files([str(existing), str(tmp_path / "missing.json")])
    assert not existing.exists()

    def _raise_os_error(_self) -> None:
        raise OSError("read only")

    monkeypatch.setattr(Path, "unlink", _raise_os_error)
    with caplog.at_level(logging.WARNING):
        storage._remove_files([str(tmp_path / "locked.json")])
    assert "Could not remove migrated legacy file" in caplog.text


async def test_load_existing_store_sanitizes_lists(hass, monkeypatch) -> None:
    FakeStore.loaded = {
        "history": "invalid",
        "legacy_history": {"invalid": True},
        "pending_restart": {"profile": "quick"},
        "future_key": True,
    }
    FakeStore.saved = None
    monkeypatch.setattr(storage, "Store", FakeStore)

    store, data = await storage.async_load_store(hass, "entry")

    assert isinstance(store, FakeStore)
    assert data["history"] == []
    assert data["legacy_history"] == []
    assert data["pending_restart"] == {"profile": "quick"}
    assert data["future_key"] is True
    assert FakeStore.saved is None

    FakeStore.loaded = {"history": [], "legacy_history": []}
    _, valid = await storage.async_load_store(hass, "valid-entry")
    assert valid["history"] == []
    assert valid["legacy_history"] == []


async def test_load_store_migrates_legacy_files(hass, monkeypatch) -> None:
    FakeStore.loaded = None
    FakeStore.saved = None
    monkeypatch.setattr(storage, "Store", FakeStore)
    history_path = Path(hass.config.path(LEGACY_HISTORY_FILE))
    restart_path = Path(hass.config.path(LEGACY_RESTART_FILE))
    meta_path = Path(hass.config.path(LEGACY_META_FILE))
    await hass.async_add_executor_job(
        _write_text,
        history_path,
        json.dumps([{"score": index} for index in range(60)]),
    )
    await hass.async_add_executor_job(
        _write_text,
        restart_path,
        json.dumps({"state": "pending", "started_at": 123.5, "profile": "normal"}),
    )
    await hass.async_add_executor_job(_write_text, meta_path, "{}")

    _, data = await storage.async_load_store(hass, "legacy")

    assert len(data["legacy_history"]) == 50
    assert data["legacy_history"][0] == {"score": 10}
    assert data["pending_restart"] == {
        "requested_at": 123.5,
        "profile": "normal",
        "migrated_from_v2": True,
    }
    assert FakeStore.saved == data
    assert not await hass.async_add_executor_job(_exists, history_path)
    assert not await hass.async_add_executor_job(_exists, restart_path)
    assert not await hass.async_add_executor_job(_exists, meta_path)


async def test_load_store_ignores_invalid_legacy_shapes(hass, monkeypatch) -> None:
    FakeStore.loaded = None
    FakeStore.saved = None
    monkeypatch.setattr(storage, "Store", FakeStore)
    await hass.async_add_executor_job(
        _write_text,
        Path(hass.config.path(LEGACY_HISTORY_FILE)),
        "{}",
    )
    await hass.async_add_executor_job(
        _write_text,
        Path(hass.config.path(LEGACY_RESTART_FILE)),
        json.dumps({"state": "finished", "started_at": "invalid"}),
    )

    _, data = await storage.async_load_store(hass, "invalid-legacy")

    assert data == storage.default_stored_data()
    assert FakeStore.saved == data


def test_write_csv_contains_flat_result(tmp_path: Path) -> None:
    path = tmp_path / "export.csv"
    result = benchmark_result()
    storage.write_csv(str(path), [result, {}])

    with path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    assert rows[0]["ha_performance_score"] == "8000"
    assert rows[0]["event_loop_idle_p95_ms"] == "1.0"
    assert rows[0]["restart_recovery_time_s"] == ""
    assert rows[0]["cpu_model"] == "Test CPU"
    assert rows[1]["profile"] == ""
