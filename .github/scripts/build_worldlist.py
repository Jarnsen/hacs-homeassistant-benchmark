"""Build the public v3 worldlist from validated GitHub issue payloads."""

from __future__ import annotations

import importlib.util
import json
import math
import os
import re
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

REPO = os.environ["GITHUB_REPOSITORY"]
TOKEN = os.environ["GITHUB_TOKEN"]
API_ROOT = f"https://api.github.com/repos/{REPO}/issues"
RESULT_SCHEMA = "ha_homeassistant_performance_result_v3"
WORLDLIST_SCHEMA = "ha_homeassistant_performance_worldlist_v3"
PROTOCOL_VERSION = "3.0.0"
SCORE_VERSION = "ha_score_v3"
MAX_PAGES = 10
PER_PAGE = 100
EXPECTED_STANDARD_PROTOCOL = {
    "timer_interval_ms": 20,
    "sample_counts": {
        "event_loop_idle": 300,
        "event_loop_loaded": 300,
        "state_machine": 300,
        "event_bus": 300,
        "service_calls": 200,
        "template_render": 300,
    },
    "controlled_load": {
        "batch_size": 5,
        "batch_period_ms": 20,
        "target_service_calls_s": 250,
        "state_updates": False,
    },
}


def _load_scoring() -> ModuleType:
    path = Path("custom_components/benchmark/scoring.py")
    spec = importlib.util.spec_from_file_location("benchmark_scoring", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load scoring module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SCORING = _load_scoring()


def request_json(url: str) -> list[dict[str, Any]]:
    """Request one GitHub API page."""
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "ha-performance-worldlist-builder",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.loads(response.read().decode("utf-8"))
    if not isinstance(result, list):
        raise TypeError("GitHub issues API returned an unexpected document")
    return result


def ranking_issues() -> list[dict[str, Any]]:
    """Fetch open ranking issues with bounded pagination."""
    issues: list[dict[str, Any]] = []
    for page in range(1, MAX_PAGES + 1):
        query = urllib.parse.urlencode(
            {
                "state": "open",
                "labels": "ranking",
                "per_page": PER_PAGE,
                "page": page,
            }
        )
        batch = request_json(f"{API_ROOT}?{query}")
        issues.extend(issue for issue in batch if "pull_request" not in issue)
        if len(batch) < PER_PAGE:
            break
    return issues


def json_blocks(body: str) -> list[dict[str, Any]]:
    """Return all valid JSON code blocks from an issue body."""
    blocks: list[dict[str, Any]] = []
    for match in re.finditer(r"```json\s*([\s\S]*?)```", body or "", re.IGNORECASE):
        try:
            document = json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            continue
        if isinstance(document, dict):
            blocks.append(document)
    return blocks


def _finite_number(value: Any) -> int | float | None:
    if not isinstance(value, int | float):
        return None
    parsed = float(value)
    if not math.isfinite(parsed):
        return None
    return int(parsed) if parsed.is_integer() else parsed


def _safe_text(value: Any, maximum: int = 100) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.replace("|", "/").split())
    return cleaned[:maximum] or None


def _system_value(system: dict[str, Any], key: str) -> Any:
    value = system.get(key)
    if isinstance(value, str):
        return _safe_text(value)
    return _finite_number(value)


def _validate_identity(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected_values = {
        "schema": RESULT_SCHEMA,
        "protocol_version": PROTOCOL_VERSION,
        "score_version": SCORE_VERSION,
        "profile": "standard",
        "protocol": EXPECTED_STANDARD_PROTOCOL,
    }
    messages = {
        "schema": "unsupported schema",
        "protocol_version": "unsupported protocol version",
        "score_version": "unsupported score version",
        "profile": "only the standard profile is rankable",
        "protocol": "unexpected standard protocol definition",
    }
    errors.extend(
        messages[key]
        for key, expected in expected_values.items()
        if payload.get(key) != expected
    )
    result_id = payload.get("result_id")
    if not isinstance(result_id, str) or not re.fullmatch(
        r"[0-9a-f]{32}",
        result_id,
    ):
        errors.append("invalid result id")
    return errors


def _validate_run_metadata(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    validity = payload.get("validity")
    if not isinstance(validity, dict):
        errors.append("missing validity metadata")
    elif not validity.get("ranking_eligible", False):
        errors.append("payload is not ranking eligible")
    elif validity.get("confidence") not in {"high", "medium", "low"}:
        errors.append("invalid confidence classification")
    duration = payload.get("duration_s")
    if (
        not isinstance(duration, int | float)
        or isinstance(duration, bool)
        or not math.isfinite(float(duration))
        or not 1 <= float(duration) <= 900
    ):
        errors.append("invalid benchmark duration")
    return errors


def validate_payload(payload: dict[str, Any]) -> list[str]:
    """Validate protocol identity, samples, and bounded latency values."""
    errors = _validate_identity(payload)
    measurements = payload.get("measurements")
    if not isinstance(measurements, dict):
        errors.append("missing measurements")
        return errors
    errors.extend(
        SCORING.validate_measurements(
            measurements,
            require_standard_samples=True,
        )
    )
    for section in SCORING.REQUIRED_MEASUREMENTS:
        data = measurements.get(section, {})
        if isinstance(data, dict):
            for key in ("p50_ms", "p95_ms", "p99_ms", "max_ms"):
                value = data.get(key)
                if (
                    isinstance(value, int | float)
                    and math.isfinite(float(value))
                    and float(value) > 60_000
                ):
                    errors.append(f"out-of-range latency: {section}.{key}")
    errors.extend(_validate_run_metadata(payload))
    return errors


def entry_from_issue(issue: dict[str, Any]) -> dict[str, Any] | None:
    """Validate an issue and create a server-scored public entry."""
    payload = next(
        (
            block
            for block in json_blocks(issue.get("body") or "")
            if block.get("schema") == RESULT_SCHEMA
        ),
        None,
    )
    if payload is None or validate_payload(payload):
        return None

    measurements = payload["measurements"]
    computed = SCORING.compute_scores(measurements)
    system = payload.get("system")
    if not isinstance(system, dict):
        system = {}
    validity = payload.get("validity", {})
    secondary = payload.get("secondary", {})
    reported_score = payload.get("scores", {}).get("ha_performance_score")
    warnings = validity.get("warnings")
    if not isinstance(warnings, list):
        warnings = []

    return {
        "rank": None,
        "result_id": payload["result_id"],
        "score": computed["ha_performance_score"],
        "core_score": computed["ha_core_score"],
        "fluidity_score": computed["fluidity_score"],
        "score_version": computed["score_version"],
        "reported_score_matches": reported_score == computed["ha_performance_score"],
        "issue_number": issue["number"],
        "issue_url": issue["html_url"],
        "submitted_at": issue["created_at"],
        "updated_at": issue["updated_at"],
        "benchmark_timestamp": payload.get("timestamp"),
        "protocol_version": payload.get("protocol_version"),
        "profile": payload.get("profile"),
        "confidence": _safe_text(validity.get("confidence"), 20),
        "warnings": [
            _safe_text(value, 80) for value in warnings if _safe_text(value, 80)
        ],
        "home_assistant_version": _system_value(
            system,
            "home_assistant_version",
        ),
        "installation_type": _system_value(system, "installation_type"),
        "entity_count": _system_value(system, "entity_count"),
        "device_count": _system_value(system, "device_count"),
        "config_entry_count": _system_value(system, "config_entry_count"),
        "architecture": _system_value(system, "architecture"),
        "cpu_model": _system_value(system, "cpu_model"),
        "device_model": _system_value(system, "device_model"),
        "operating_system": _system_value(system, "operating_system"),
        "cpu_cores_logical": _system_value(system, "cpu_cores_logical"),
        "ram_total_mb": _system_value(system, "ram_total_mb"),
        "restart_recovery_time_s": _finite_number(
            secondary.get("restart_recovery_time_s")
            if isinstance(secondary, dict)
            else None
        ),
        "p95_ms": {
            section: measurements[section]["p95_ms"]
            for section in SCORING.REQUIRED_MEASUREMENTS
        },
    }


def _markdown(entries: list[dict[str, Any]], updated_at: str) -> str:
    lines = [
        "# Home Assistant Performance Benchmark Worldlist",
        "",
        f"Updated: {updated_at}",
        f"Validated entries: {len(entries)}",
        "",
        (
            "Scores are recalculated by GitHub from protocol v3 measurements. "
            "Hardware is metadata only and never contributes directly to the score."
        ),
        "",
        (
            "| Rank | HA Score | Core | Fluidity | Confidence | HA Version | "
            "Entities | System | Architecture | Issue |"
        ),
        "|---:|---:|---:|---:|---|---|---:|---|---|---|",
    ]
    lines.extend(
        (
            f"| {entry['rank']} | {entry['score']} | {entry['core_score']} | "
            f"{entry['fluidity_score']} | {entry.get('confidence') or ''} | "
            f"{entry.get('home_assistant_version') or ''} | "
            f"{entry.get('entity_count') or ''} | "
            f"{entry.get('device_model') or entry.get('cpu_model') or ''} | "
            f"{entry.get('architecture') or ''} | "
            f"[#{entry['issue_number']}]({entry['issue_url']}) |"
        )
        for entry in entries
    )
    lines.extend(
        [
            "",
            (
                "Only open issues labeled `ranking` with a valid standard-profile "
                "v3 payload are included."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    """Build JSON and Markdown outputs."""
    updated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    issues = sorted(
        ranking_issues(),
        key=lambda issue: issue.get("updated_at", ""),
        reverse=True,
    )
    entries: list[dict[str, Any]] = []
    seen_result_ids: set[str] = set()
    for issue in issues:
        entry = entry_from_issue(issue)
        if entry is None or entry["result_id"] in seen_result_ids:
            continue
        seen_result_ids.add(entry["result_id"])
        entries.append(entry)

    entries.sort(
        key=lambda item: (
            item["score"],
            item["core_score"],
            item["fluidity_score"],
        ),
        reverse=True,
    )
    for index, entry in enumerate(entries, start=1):
        entry["rank"] = index

    output = {
        "schema": WORLDLIST_SCHEMA,
        "protocol_version": PROTOCOL_VERSION,
        "score_version": SCORE_VERSION,
        "protocol": EXPECTED_STANDARD_PROTOCOL,
        "updated_at": updated_at,
        "source": "validated_github_issues",
        "issue_label": "ranking",
        "count": len(entries),
        "entries": entries,
    }

    docs = Path("docs")
    docs.mkdir(exist_ok=True)
    (docs / "worldlist.json").write_text(
        json.dumps(output, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    (docs / "worldlist.md").write_text(
        _markdown(entries, updated_at),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
