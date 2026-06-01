from __future__ import annotations

import json
import os
import re
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

REPO = os.environ["GITHUB_REPOSITORY"]
TOKEN = os.environ["GITHUB_TOKEN"]
API = f"https://api.github.com/repos/{REPO}/issues?state=open&labels=ranking&per_page=100"


def request_json(url: str) -> list[dict]:
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def section(body: str, name: str) -> str | None:
    pattern = re.compile(rf"^###\s+{re.escape(name)}\s*\n([\s\S]*?)(?=^###\s+|\Z)", re.I | re.M)
    match = pattern.search(body or "")
    if not match:
        return None
    value = match.group(1).strip()
    if value.lower() == "_no response_":
        return None
    return value


def number(value):
    if value is None:
        return None
    cleaned = re.sub(r"[^0-9.,-]", "", str(value)).replace(",", ".")
    try:
        return float(cleaned) if "." in cleaned else int(cleaned)
    except ValueError:
        return None


def json_block(body: str) -> dict | None:
    for match in re.finditer(r"```json\s*([\s\S]*?)```", body or "", re.I):
        text = match.group(1).strip()
        if not text or "PASTE_EXPORT_HERE" in text:
            continue
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            continue
    return None


def entry_from_issue(issue: dict) -> dict | None:
    body = issue.get("body") or ""
    export = json_block(body)
    if export:
        benchmark = export.get("benchmark", {})
        system = export.get("system_class", {})
        load = export.get("home_assistant_load", {})
        results = export.get("results", {})
        score = number(benchmark.get("score"))
        if score is None:
            return None
        return {
            "rank": None,
            "score": int(score),
            "issue_number": issue["number"],
            "issue_url": issue["html_url"],
            "submitted_at": issue["created_at"],
            "updated_at": issue["updated_at"],
            "benchmark_version": benchmark.get("version"),
            "benchmark_timestamp": benchmark.get("timestamp"),
            "load_class": load.get("load_class"),
            "entity_count": number(load.get("entity_count")),
            "architecture": system.get("architecture"),
            "os": system.get("os"),
            "python_version": system.get("python_version"),
            "cpu_cores_logical": number(system.get("cpu_cores_logical")),
            "cpu_cores_physical": number(system.get("cpu_cores_physical")),
            "ram_total_mb": number(system.get("ram_total_mb")),
            "disk_total_mb": number(system.get("disk_total_mb")),
            "disk_free_mb": number(system.get("disk_free_mb")),
            "cpu_ops_s": number(results.get("cpu_ops_s")),
            "disk_write_mb_s": number(results.get("disk_write_mb_s")),
            "disk_read_mb_s": number(results.get("disk_read_mb_s")),
            "template_render_ms": number(results.get("template_render_ms")),
            "restart_time_s": number(results.get("restart_time_s")),
            "source": "issue_export_json",
        }

    score = number(section(body, "Score"))
    if score is None:
        return None
    return {
        "rank": None,
        "score": int(score),
        "issue_number": issue["number"],
        "issue_url": issue["html_url"],
        "submitted_at": issue["created_at"],
        "updated_at": issue["updated_at"],
        "benchmark_version": None,
        "benchmark_timestamp": None,
        "load_class": section(body, "Load class"),
        "entity_count": number(section(body, "Entity count")),
        "architecture": section(body, "Architecture"),
        "os": None,
        "python_version": None,
        "cpu_cores_logical": number(section(body, "CPU cores")),
        "cpu_cores_physical": None,
        "ram_total_mb": number(section(body, "RAM MB")),
        "disk_total_mb": None,
        "disk_free_mb": None,
        "cpu_ops_s": None,
        "disk_write_mb_s": None,
        "disk_read_mb_s": None,
        "template_render_ms": None,
        "restart_time_s": None,
        "source": "issue_form_fields",
    }


def main() -> None:
    updated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    issues = [issue for issue in request_json(API) if "pull_request" not in issue]
    entries = [entry for issue in issues if (entry := entry_from_issue(issue))]
    entries.sort(key=lambda item: item["score"], reverse=True)
    for index, entry in enumerate(entries, start=1):
        entry["rank"] = index

    output = {
        "schema": "ha_real_world_benchmark_public_worldlist_v1",
        "updated_at": updated_at,
        "source": "github_issues",
        "issue_label": "ranking",
        "count": len(entries),
        "entries": entries,
    }

    docs = Path("docs")
    docs.mkdir(exist_ok=True)
    (docs / "worldlist.json").write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "# Home Assistant Real World Benchmark Worldlist",
        "",
        f"Updated: {updated_at}",
        f"Entries: {len(entries)}",
        "",
        "| Rank | Score | Load Class | Entities | Architecture | CPU Cores | RAM MB | Issue |",
        "|---:|---:|---|---:|---|---:|---:|---|",
    ]
    for entry in entries:
        lines.append(
            f"| {entry['rank']} | {entry['score']} | {entry.get('load_class') or ''} | "
            f"{entry.get('entity_count') or ''} | {entry.get('architecture') or ''} | "
            f"{entry.get('cpu_cores_logical') or ''} | {entry.get('ram_total_mb') or ''} | "
            f"[#{entry['issue_number']}]({entry['issue_url']}) |"
        )
    lines.append("")
    lines.append("This file is generated automatically from open GitHub issues labeled `ranking`.")
    (docs / "worldlist.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
