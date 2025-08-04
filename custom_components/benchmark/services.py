# custom_components/benchmark/services.py

import os
import time
import datetime
import platform
import psutil
import subprocess
import re
import asyncio

from importlib.metadata import version, PackageNotFoundError
from homeassistant.helpers.template import Template
from homeassistant.helpers import device_registry

from .const import DATA_FILE

def run_benchmark_sync(hass) -> dict:
    now = time.time()
    proc = psutil.Process(os.getpid())

    # Versionen
    try:
        core_ver = version("homeassistant")
    except PackageNotFoundError:
        core_ver = None
    fe = hass.config_entries.async_entries("frontend")
    frontend_ver = fe[0].version if fe else None
    sup = hass.data.get("supervisor")
    sup_ver = getattr(sup, "version", None) if sup else None

    # Zeiten fürs Boot-Profil
    start = hass.data.get("benchmark_start_time", now)
    ready = hass.data.get("benchmark_ha_ready", now)
    boot_profile = round(ready - start, 1)
    ha_uptime = round(now - ready, 1)
    os_boot = psutil.boot_time()
    os_uptime = round(now - os_boot)

    hw = {
        "install_method":    "Home Assistant OS" if sup_ver else "Container/Other",
        "ha_core":           core_ver,
        "ha_frontend":       frontend_ver,
        "ha_supervisor":     sup_ver,
        "boot_profile_s":    boot_profile,
        "architecture":      platform.machine(),
        "os_system":         platform.system(),
        "os_version":        platform.version(),
        "os_uptime_s":       os_uptime,
        "process_mem_mb":    round(proc.memory_info().rss / (1024**2), 1),
        "process_threads":   proc.num_threads(),
        "cpu_cores":         psutil.cpu_count(logical=False) or psutil.cpu_count(),
        "cpu_usage_percent": psutil.cpu_percent(interval=1),
        "total_ram_mb":      psutil.virtual_memory().total // (1024**2),
        "storage_type":      _detect_storage("/"),
        "virtualization":    _detect_virt(),
        "ha_entities":       len(hass.states.async_all()),
        "ha_devices":        len(device_registry.async_get(hass).devices),
        "ha_integrations":   len(hass.config_entries.async_entries()),
        "ha_uptime_s":       ha_uptime,
    }

    results = {}
    # CPU-Stress
    t0 = time.time()
    while time.time() - t0 < 3:
        pass
    results["cpu_stress_avg_freq_mhz"] = psutil.cpu_freq().current

    # Disk I/O (50 MB)
    tmp = "/tmp/benchmark.tmp"
    w0 = time.perf_counter()
    with open(tmp, "wb") as f:
        f.write(b"0" * 50_000_000)
    results["disk_write_ms"] = (time.perf_counter() - w0) * 1000
    r0 = time.perf_counter()
    with open(tmp, "rb") as f:
        f.read()
    results["disk_read_ms"] = (time.perf_counter() - r0) * 1000
    try: os.remove(tmp)
    except: pass

    # Template-Render
    tpl = Template("{{ 'x'*1000 }}", hass)
    tr0 = time.perf_counter(); tpl.async_render({})
    results["template_render_ms"] = (time.perf_counter() - tr0) * 1000

    # Frontend-Render entfällt im Score
    results["frontend_render_ms"] = None

    timestamp = datetime.datetime.now().isoformat()
    return {"timestamp": timestamp, "hardware": hw, "results": results}


async def run_benchmark_async(hass) -> dict:
    out = {}

    # State-TP
    sc0 = time.perf_counter()
    for i in range(1000):
        hass.states.async_set("benchmark.tp", i)
    await hass.async_block_till_done()
    out["state_tp_ops_s"] = 1000 / (time.perf_counter() - sc0)

    # EventBus-P95
    ev = []
    for _ in range(100):
        fut = hass.loop.create_future(); start = hass.loop.time()
        hass.bus.async_listen_once("benchmark.test_ev",
            lambda e,fut=fut,start=start: fut.set_result(hass.loop.time()-start))
        hass.bus.fire("benchmark.test_ev"); ev.append((await fut)*1000)
    out["eventbus_p95_ms"] = sorted(ev)[94]

    # Automation-P95
    at = []
    for _ in range(50):
        fut = hass.loop.create_future(); start = hass.loop.time()
        hass.bus.async_listen_once("benchmark.automate_test",
            lambda e,fut=fut,start=start: fut.set_result(hass.loop.time()-start))
        hass.bus.fire("benchmark.automate_test"); at.append((await fut)*1000)
    out["automation_p95_ms"] = sorted(at)[int(0.95*len(at))]

    # Service-Call
    svc = []
    for _ in range(10):
        t0 = time.perf_counter()
        await hass.services.async_call("homeassistant","check_config",{},blocking=True)
        svc.append((time.perf_counter()-t0)*1000)
    out["service_call_avg_ms"] = sum(svc)/len(svc)
    out["service_call_p95_ms"] = sorted(svc)[int(0.95*len(svc))]

    # Recorder-Commit
    rc = []
    for i in range(50):
        fut = hass.loop.create_future()
        evn = f"benchmark.recorder_{i}"
        hass.bus.async_listen_once(evn, lambda e,fut=fut: fut.set_result(True))
        hass.bus.fire(evn); start = time.perf_counter()
        await fut; rc.append((time.perf_counter()-start)*1000)
    out["recorder_commit_ms"] = sum(rc)/len(rc)

    # Loop-Latency P95
    ll = []
    for _ in range(100):
        fut = hass.loop.create_future(); t0 = hass.loop.time()
        hass.loop.call_soon(lambda fut=fut: fut.set_result(hass.loop.time()))
        ll.append((await fut - t0)*1000)
    out["loop_latency_p95_ms"] = sorted(ll)[94]

    return out


def compute_score(results: dict, hw: dict) -> int:
    """
    Score 0–10000 (pure HA-Performance):
      State-TP, EventBus, Automation, Service, Recorder, Loop, Template, Boot
    """
    # Normierung 0–1
    norm_state = min(results["state_tp_ops_s"] / 2000, 1.0)
    norm_bus   = min(50   / results["eventbus_p95_ms"],    1.0)
    norm_auto  = min(50   / results["automation_p95_ms"],  1.0)
    norm_svc   = min(100  / results["service_call_p95_ms"],1.0)
    norm_rec   = min(100  / results["recorder_commit_ms"], 1.0)
    norm_loop  = min(10   / results["loop_latency_p95_ms"],1.0)
    norm_tpl   = min(100  / results["template_render_ms"], 1.0)
    norm_boot  = min(30   / hw["boot_profile_s"],          1.0)

    # Gewichte (sum=1.0)
    pre_score = (
        0.25*norm_state +
        0.15*norm_bus   +
        0.10*norm_auto  +
        0.10*norm_svc   +
        0.10*norm_rec   +
        0.10*norm_loop  +
        0.10*norm_tpl   +
        0.05*norm_boot
    )

    # Auf 0–10000 skalieren
    return int(pre_score * 10000)


def _detect_virt() -> str:
    try:
        out = subprocess.run(["systemd-detect-virt"], capture_output=True, text=True).stdout.strip().lower()
        if out and out != "none":
            return out
    except:
        pass
    try:
        if "hypervisor" in open("/proc/cpuinfo").read():
            return "virtual-machine"
    except:
        pass
    return "none"


def _detect_storage(mount: str) -> str:
    try:
        part = next(p.device for p in psutil.disk_partitions() if p.mountpoint == mount)
        blk = re.sub(r"\d+$", "", os.path.basename(part))
        rota = open(f"/sys/block/{blk}/queue/rotational").read().strip() == "1"
        model_path = f"/sys/block/{blk}/device/model"
        model = open(model_path).read().strip() if os.path.exists(model_path) else ""
        s = "HDD" if rota else "SSD"
        if model:
            s += f" ({model})"
        return s
    except:
        return "unknown"
