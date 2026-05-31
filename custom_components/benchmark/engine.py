"""Benchmark engine for Home Assistant Benchmark."""

from __future__ import annotations

import datetime as dt
import math
import os
import platform
import statistics
import tempfile
import time
from dataclasses import dataclass
from typing import Any

import psutil
from homeassistant.core import HomeAssistant
from homeassistant.helpers.template import Template


@dataclass(frozen=True)
class BenchmarkProfile:
    name: str
    cpu_duration_s: float
    disk_size_mb: int
    template_runs: int
    runs: int


PROFILES_MAP: dict[str, BenchmarkProfile] = {
    "light": BenchmarkProfile("light", 0.6, 10, 30, 3),
    "normal": BenchmarkProfile("normal", 1.2, 25, 80, 5),
    "heavy": BenchmarkProfile("heavy", 2.5, 75, 200, 7),
}


def profile_from_name(profile: str | None) -> BenchmarkProfile:
    return PROFILES_MAP.get(profile or "normal", PROFILES_MAP["normal"])


def median_without_outliers(values: list[float]) -> float | None:
    clean = [v for v in values if isinstance(v, int | float) and math.isfinite(v) and v >= 0]
    if not clean:
        return None
    if len(clean) < 4:
        return float(statistics.median(clean))
    q1, _, q3 = statistics.quantiles(clean, n=4, method="inclusive")
    iqr = q3 - q1
    low = q1 - 1.5 * iqr
    high = q3 + 1.5 * iqr
    filtered = [v for v in clean if low <= v <= high]
    return float(statistics.median(filtered or clean))


def normalize_high(value: Any, target: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    if parsed <= 0:
        return 0.0
    return max(0.0, min(parsed / target, 1.0))


def normalize_low(value: Any, target: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    if parsed <= 0:
        return 0.0
    return max(0.0, min(target / parsed, 1.0))


def collect_system_info(hass: HomeAssistant) -> dict[str, Any]:
    process = psutil.Process(os.getpid())
    disk = psutil.disk_usage(hass.config.path())
    return {
        "ha_version": getattr(hass, "version", None),
        "python_version": platform.python_version(),
        "architecture": platform.machine(),
        "os": f"{platform.system()} {platform.release()}",
        "cpu_cores_physical": psutil.cpu_count(logical=False),
        "cpu_cores_logical": psutil.cpu_count(logical=True),
        "ram_total_mb": round(psutil.virtual_memory().total / 1024 / 1024),
        "disk_total_mb": round(disk.total / 1024 / 1024),
        "disk_free_mb": round(disk.free / 1024 / 1024),
        "process_memory_mb": round(process.memory_info().rss / 1024 / 1024, 1),
        "process_threads": process.num_threads(),
        "entity_count": len(hass.states.async_all()),
    }


def run_cpu_benchmark(profile: BenchmarkProfile) -> dict[str, Any]:
    values: list[float] = []
    for _ in range(profile.runs):
        start = time.perf_counter()
        deadline = start + profile.cpu_duration_s
        value = 0
        operations = 0
        while time.perf_counter() < deadline:
            value = (value * 1664525 + 1013904223) & 0xFFFFFFFF
            operations += 1
        elapsed = time.perf_counter() - start
        values.append(operations / elapsed if elapsed > 0 else 0)
    return {
        "cpu_ops_s": median_without_outliers(values),
        "cpu_runs": values,
        "cpu_outlier_method": "IQR 1.5 + median",
    }


def run_disk_benchmark(config_path: str, profile: BenchmarkProfile) -> dict[str, Any]:
    write_values: list[float] = []
    read_values: list[float] = []
    size_bytes = profile.disk_size_mb * 1024 * 1024
    chunk = b"0" * 1024 * 1024
    for _ in range(profile.runs):
        tmp_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(prefix="ha_benchmark_", suffix=".tmp", dir=config_path, delete=False) as tmp:
                tmp_name = tmp.name
                written = 0
                start = time.perf_counter()
                while written < size_bytes:
                    amount = min(len(chunk), size_bytes - written)
                    tmp.write(chunk[:amount])
                    written += amount
                tmp.flush()
                os.fsync(tmp.fileno())
                elapsed = time.perf_counter() - start
                write_values.append((size_bytes / 1024 / 1024) / elapsed if elapsed > 0 else 0)
            read_bytes = 0
            start = time.perf_counter()
            with open(tmp_name, "rb") as fp:
                while data := fp.read(1024 * 1024):
                    read_bytes += len(data)
            elapsed = time.perf_counter() - start
            read_values.append((read_bytes / 1024 / 1024) / elapsed if elapsed > 0 else 0)
        finally:
            if tmp_name:
                try:
                    os.remove(tmp_name)
                except OSError:
                    pass
    return {
        "disk_test_size_mb": profile.disk_size_mb,
        "disk_write_mb_s": median_without_outliers(write_values),
        "disk_read_mb_s": median_without_outliers(read_values),
        "disk_write_runs": write_values,
        "disk_read_runs": read_values,
        "disk_outlier_method": "IQR 1.5 + median",
    }


def run_template_benchmark(hass: HomeAssistant, profile: BenchmarkProfile) -> dict[str, Any]:
    values: list[float] = []
    template = Template("{{ range(0, 500) | list | sum }}", hass)
    for _ in range(profile.template_runs):
        start = time.perf_counter()
        template.async_render(parse_result=False)
        values.append((time.perf_counter() - start) * 1000)
    return {
        "template_render_ms": median_without_outliers(values),
        "template_runs": values,
        "template_outlier_method": "IQR 1.5 + median",
    }


def compute_score(results: dict[str, Any]) -> tuple[int, str, dict[str, float]]:
    normalized = {
        "cpu": normalize_high(results.get("cpu_ops_s"), 18_000_000),
        "disk_write": normalize_high(results.get("disk_write_mb_s"), 220),
        "disk_read": normalize_high(results.get("disk_read_mb_s"), 420),
        "template": normalize_low(results.get("template_render_ms"), 2.5),
        "restart": normalize_low(results.get("restart_time_s"), 55),
    }
    weights = {"cpu": 0.35, "disk_write": 0.20, "disk_read": 0.20, "template": 0.15, "restart": 0.10}
    value = sum(normalized[key] * weights[key] for key in weights)
    score = int(max(0, min(10000, round(value * 10000))))
    formula = "score = 10000 * (0.35*cpu + 0.20*disk_write + 0.20*disk_read + 0.15*template + 0.10*restart)"
    return score, formula, normalized


async def run_benchmark(hass: HomeAssistant, profile_name: str, restart_time_s: float | None, progress_callback) -> dict[str, Any]:
    profile = profile_from_name(profile_name)
    await progress_callback(5, f"Profil {profile.name} vorbereitet")
    system = collect_system_info(hass)
    await progress_callback(20, "CPU Benchmark läuft")
    cpu = await hass.async_add_executor_job(run_cpu_benchmark, profile)
    await progress_callback(50, "Disk I/O Benchmark läuft")
    disk = await hass.async_add_executor_job(run_disk_benchmark, hass.config.path(), profile)
    await progress_callback(75, "Template Benchmark läuft")
    template = await hass.async_add_executor_job(run_template_benchmark, hass, profile)
    await progress_callback(90, "Score wird berechnet")
    results = {**cpu, **disk, **template, "restart_time_s": restart_time_s}
    score, formula, normalized = compute_score(results)
    results["benchmark_score"] = score
    results["scoring_formula"] = formula
    results["scoring_normalized"] = normalized
    results["scoring_weights"] = {"cpu": 0.35, "disk_write": 0.20, "disk_read": 0.20, "template": 0.15, "restart": 0.10}
    return {
        "timestamp": dt.datetime.now(dt.UTC).isoformat(),
        "profile": profile.name,
        "system": system,
        "results": results,
    }
