"""Repository metadata consistency tests."""

from __future__ import annotations

import json
from pathlib import Path

from custom_components.benchmark.const import INTEGRATION_VERSION
from custom_components.benchmark.dashboard import build_dashboard_yaml


def test_manifest_and_hacs_metadata() -> None:
    manifest = json.loads(
        Path("custom_components/benchmark/manifest.json").read_text(encoding="utf-8")
    )
    hacs = json.loads(Path("hacs.json").read_text(encoding="utf-8"))
    assert manifest["version"] == INTEGRATION_VERSION
    assert manifest["config_flow"] is True
    assert manifest["single_config_entry"] is True
    assert hacs["name"] == manifest["name"]


def test_translation_keys_match() -> None:
    root = Path("custom_components/benchmark")
    strings = json.loads((root / "strings.json").read_text(encoding="utf-8"))
    for language in ("en", "de"):
        translated = json.loads(
            (root / "translations" / f"{language}.json").read_text(encoding="utf-8")
        )
        assert translated.keys() == strings.keys()
        assert (
            translated["entity"]["sensor"].keys() == strings["entity"]["sensor"].keys()
        )
        assert (
            translated["entity"]["button"].keys() == strings["entity"]["button"].keys()
        )


def test_dashboard_example_matches_generated_yaml() -> None:
    example = Path("lovelace/example_dashboard.yaml").read_text(encoding="utf-8")
    assert example.strip() == build_dashboard_yaml().strip()
