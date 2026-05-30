# custom_components/benchmark/services.py

from __future__ import annotations

import datetime
import getpass
import os
import platform
import re
import statistics
import subprocess
import tempfile
import time
from importlib.metadata import PackageNotFoundError, version
from typing import Any

import psutil
from homeassistant.helpers import device_registry
from homeassistant.helpers.template import Template

BENCHMARK_STATE_ENTITY = "benchmark.throughput"


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    index = max(0, min(len(values) - 1, round((len(values) - 1) * percentile)))
    return sorted(values)[index]


def _safe_positive(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _normalize_higher_is_better(value: Any, target: float) -> float:
    parsed = _safe_positive(value)
    if parsed is None:
        return 0.0
    return min(parsed / target, 1.0)


def _normalize_lower_is_better(value: Any, target: float) -> float:
    parsed = _safe_positive(value)
    if parsed is None:
        return 0.0
    return min(target / parsed, 1.0)


def run_benchmark_sync(hass) -> dict[str, Any]:
    now = time.time()
    proc = psutil.Process(os.getpid())

    try:
        core_ver = version("homeassistant")
    except PackageNotFoundError:
        core_ver = None

    frontend_entries = hass.config_entries.async_entries("frontend")
    frontend_ver = frontend_entries[0].version if frontend_entries else None
    supervisor = hass.data.get("supervisor")
    supervisor_ver = getattr(supervisor, "version", None) if supervisor else None

    start = hass.data.get("benchmark_start_time", now)
    ready = hass.data.get("benchmark_ha_ready", now)
    boot_profile = max(round(ready - start, 1), 0)
    ha_uptime = max(round(now - ready, 1), 0)
    os_uptime = max(round(now - psutil.boot_time()), 0)

    hw = {
        "install_method": "Home Assistant OS" if supervisor_ver else "Container/Other",
        "ha_core": core_ver,
        "ha_frontend": frontend_ver,
        "ha_supervisor": supervisor_ver,
        "boot_profile_s": boot_profile,
        "architecture": platform.machine(),
        "os_system": platform.system(),
        "os_version": platform.version(),
        "os_uptime_s": os_uptime,
        "system_user": _get_system_user(),
        "process_mem_mb": round(proc.memory_info().rss / (1024**2), 1),
        "process_threads": proc.num_threads(),
        "cpu_cores": psutil.cpu_count(logical=False) or psutil.cpu_count(),
        "cpu_usage_percent": psutil.cpu_percent(interval=1),
        "total_ram_mb": psutil.virtual_memory().total // (1024**2),
        "storage_type": _detect_storage("/"),
        "virtualization": _detect_virt(),
        "ha_entities": len(hass.states.async_all()),
        "ha_devices": len(device_registry.async_get(hass).devices),
        "ha_integrations": len(hass.config_entries.async_entries()),
        "ha_uptime_s": ha_uptime,
    }

    results: dict[str, Any] = {}

    results.update(_measure_cpu())
    results.update(_measure_disk_io())
    results["template_render_ms"] = _measure_template_render(hass)

    timestamp = datetime.datetime.now(datetime.UTC).isoformat()
    return {"timestamp": timestamp, "hardware": hw, "results": results}


async def run_benchmark_async(hass) -> dict[str, Any]:
    out: dict[str, Any] = {}

    state_count = 1000
    sc0 = time.perf_counter()
    for i in range(state_count):
        hass.states.async_set(BENCHMARK_STATE_ENTITY, i)
    await hass.async_block_till_done()
    state_elapsed = time.perf_counter() - sc0
    out["state_tp_ops_s"] = state_count / state_elapsed if state_elapsed > 0 else None

    out.update(await _measure_eventbus(hass))
    out.update(await _measure_service_calls(hass))
    out.update(await _measure_loop_latency(hass))

    return out


async def _measure_eventbus(hass) -> dict[str, Any]:
    eventbus_values: list[float] = []
    for _ in range(100):
        future = hass.loop.create_future()
        start = hass.loop.time()

        def _listener(event, fut=future, started=start):
            if not fut.done():
                fut.set_result((hass.loop.time() - started) * 1000)

        hass.bus.async_listen_once("benchmark.eventbus_test", _listener)
        hass.bus.fire("benchmark.eventbus_test")
        eventbus_values.append(await future)

    automation_values: list[float] = []
    for _ in range(50):
        future = hass.loop.create_future()
        start = hass.loop.time()

        def _listener(event, fut=future, started=start):
            if not fut.done():
                fut.set_result((hass.loop.time() - started) * 1000)

        hass.bus.async_listen_once("benchmark.automation_like_test", _listener)
        hass.bus.fire("benchmark.automation_like_test")
        automation_values.append(await future)

    return {
        "eventbus_p50_ms": _percentile(eventbus_values, 0.50),
        "eventbus_p95_ms": _percentile(eventbus_values, 0.95),
        "automation_p95_ms": _percentile(automation_values, 0.95),
    }


async def _measure_service_calls(hass) -> dict[str, Any]:
    service_values: list[float] = []

    for _ in range(10):
        start = time.perf_counter()
        await hass.services.async_call("homeassistant", "update_entity", {"entity_id": BENCHMARK_STATE_ENTITY}, blocking=True)
        service_values.append((time.perf_counter() - start) * 1000)

    return {
        "service_call_avg_ms": statistics.fmean(service_values) if service_values else None,
        "service_call_p95_ms": _percentile(service_values, 0.95),
    }


async def _measure_loop_latency(hass) -> dict[str, Any]:
    values: list[float] = []
    for _ in range(100):
        future = hass.loop.create_future()
        start = hass.loop.time()
        hass.loop.call_soon(lambda fut=future: fut.set_result(hass.loop.time()))
        values.append(((await future) - start) * 1000)

    return {"loop_latency_p95_ms": _percentile(values, 0.95)}


def _measure_cpu() -> dict[str, Any]:
    start_wall = time.perf_counter()
    start_cpu = time.process_time()
    counter = 0
    while time.perf_counter() - start_wall < 1.5:
        counter += 1

    cpu_freq = psutil.cpu_freq()
    elapsed_wall = time.perf_counter() - start_wall
    elapsed_cpu = time.process_time() - start_cpu

    return {
        "cpu_loop_ops_s": counter / elapsed_wall if elapsed_wall > 0 else None,
        "cpu_process_time_s": elapsed_cpu,
        "cpu_stress_avg_freq_mhz": cpu_freq.current if cpu_freq else None,
    }


def _measure_disk_io() -> dict[str, Any]:
    size_bytes = 25_000_000
    chunk = b"0" * 1_000_000
    tmp_path = None

    try:
        with tempfile.NamedTemporaryFile(prefix="ha_benchmark_", suffix=".tmp", delete=False) as tmp:
            tmp_path = tmp.name
            write_start = time.perf_counter()
            for _ in range(size_bytes // len(chunk)):
                tmp.write(chunk)
            tmp.flush()
            os.fsync(tmp.fileno())
            write_ms = (time.perf_counter() - write_start) * 1000

        read_start = time.perf_counter()
        with open(tmp_path, "rb") as fp:
            while fp.read(1024 * 1024):
                pass
        read_ms = (time.perf_counter() - read_start) * 1000

        return {
            "disk_test_size_mb": round(size_bytes / 1_000_000, 1),
            "disk_write_ms": write_ms,
            "disk_read_ms": read_ms,
            "disk_write_mb_s": (size_bytes / 1_000_000) / (write_ms / 1000) if write_ms > 0 else None,
            "disk_read_mb_s": (size_bytes / 1_000_000) / (read_ms / 1000) if read_ms > 0 else None,
        }
    finally:
        if tmp_path:
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def _measure_template_render(hass) -> float | None:
    template = Template("{{ ('x' * 10000) | length }}", hass)
    start = time.perf_counter()
    template.async_render(parse_result=False)
    return (time.perf_counter() - start) * 1000


def compute_score(results: dict[str, Any], hw: dict[str, Any]) -> int:
    norm_state = _normalize_higher_is_better(results.get("state_tp_ops_s"), 2000)
    norm_cpu = _normalize_higher_is_better(results.get("cpu_loop_ops_s"), 25_000_000)
    norm_disk_write = _normalize_higher_is_better(results.get("disk_write_mb_s"), 250)
    norm_disk_read = _normalize_higher_is_better(results.get("disk_read_mb_s"), 500)
    norm_bus = _normalize_lower_is_better(results.get("eventbus_p95_ms"), 50)
    norm_auto = _normalize_lower_is_better(results.get("automation_p95_ms"), 50)
    norm_svc = _normalize_lower_is_better(results.get("service_call_p95_ms"), 100)
    norm_loop = _normalize_lower_is_better(results.get("loop_latency_p95_ms"), 10)
    norm_tpl = _normalize_lower_is_better(results.get("template_render_ms"), 100)
    norm_boot = _normalize_lower_is_better(hw.get("boot_profile_s"), 30)

    pre_score = (
        0.22 * norm_state
        + 0.12 * norm_cpu
        + 0.08 * norm_disk_write
        + 0.08 * norm_disk_read
        + 0.14 * norm_bus
        + 0.08 * norm_auto
        + 0.10 * norm_svc
        + 0.10 * norm_loop
        + 0.05 * norm_tpl
        + 0.03 * norm_boot
    )

    return max(0, min(10000, int(pre_score * 10000)))


def _detect_virt() -> str:
    try:
        out = subprocess.run(
            ["systemd-detect-virt"],
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        ).stdout.strip().lower()
        if out and out != "none":
            return out
    except (OSError, subprocess.SubprocessError):
        pass

    try:
        with open("/proc/cpuinfo", encoding="utf-8", errors="ignore") as fp:
            if "hypervisor" in fp.read().lower():
                return "virtual-machine"
    except OSError:
        pass

    return "none"


def _detect_storage(mount: str) -> str:
    try:
        part = next(p.device for p in psutil.disk_partitions() if p.mountpoint == mount)
        block = re.sub(r"\d+$", "", os.path.basename(part))
        block = re.sub(r"p$", "", block)
        rotational_path = f"/sys/block/{block}/queue/rotational"
        model_path = f"/sys/block/{block}/device/model"

        with open(rotational_path, encoding="utf-8") as fp:
            rotational = fp.read().strip() == "1"

        model = ""
        if os.path.exists(model_path):
            with open(model_path, encoding="utf-8", errors="ignore") as fp:
                model = fp.read().strip()

        storage = "HDD" if rotational else "SSD/NVMe/Flash"
        if "mmc" in block.lower():
            storage = "SD/eMMC"
        elif "nvme" in block.lower():
            storage = "NVMe"

        return f"{storage} ({model})" if model else storage
    except (OSError, StopIteration):
        return "unknown"


def _get_system_user() -> str | None:
    try:
        return getpass.getuser()
    except Exception:  # noqa: BLE001
        return None
