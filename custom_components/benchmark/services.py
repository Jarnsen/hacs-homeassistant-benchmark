import os
import time
import uuid
import platform
import datetime
import psutil
import asyncio
import subprocess
import re
from aiohttp import ClientSession
from .const import CONF_SHOW_UUID

def run_benchmark(hass, entry):
    opts = entry.options
    res = {
        "benchmark_id": str(uuid.uuid4()),
        "timestamp": datetime.datetime.now().isoformat(),
        "ha_version": hass.core.version,
        "test_suite_version": "2025.1.0"
    }

    # Hardware‐Infos
    info = platform.uname()
    res["hardware"] = {
        "model": info.node,
        "cpu_arch": info.machine,
        "cpu_cores": psutil.cpu_count(),
        "total_ram_mb": psutil.virtual_memory().total // 1024 // 1024,
        "storage_type": "unknown"
    }

    metrics = {}

    # 1) CPU‐Stresstest (10 s Busy‐Loop)
    end = time.time() + 10
    while time.time() < end:
        pass
    metrics["cpu_stress_avg_freq_mhz"] = psutil.cpu_freq().current

    # 2) Disk I/O (100 MB Write + Read)
    path = hass.config.path("benchmark.tmp")
    t0 = time.perf_counter()
    with open(path, "wb") as f:
        f.write(b"0" * 100_000_000)
    metrics["disk_io_write_ms"] = (time.perf_counter() - t0) * 1000

    t1 = time.perf_counter()
    with open(path, "rb") as f:
        f.read()
    metrics["disk_io_read_ms"] = (time.perf_counter() - t1) * 1000
    try:
        os.remove(path)
    except:
        pass

    # 3) Event‐Bus Latenz (1 000 Events)
    lat = []
    for i in range(1000):
        t0 = time.perf_counter()
        hass.bus.fire("benchmark.event", {"seq": i})
        lat.append((time.perf_counter() - t0) * 1000)
    lat.sort()
    metrics["eventbus_p50_ms"] = lat[int(0.50 * len(lat))]
    metrics["eventbus_p95_ms"] = lat[int(0.95 * len(lat))]
    metrics["eventbus_p99_ms"] = lat[int(0.99 * len(lat))]

    # 4) API‐Roundtrip (100× GET /api/states)
    async def _api_test():
        times = []
        url = f"http://{hass.config.host}:{hass.config.port}/api/states"
        async with ClientSession() as session:
            for _ in range(100):
                t0 = time.perf_counter()
                await session.get(url)
                times.append((time.perf_counter() - t0) * 1000)
        return times

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    api_times = loop.run_until_complete(_api_test())
    metrics["api_roundtrip_avg_ms"] = sum(api_times) / len(api_times)
    metrics["api_roundtrip_max_ms"] = max(api_times)

    # 5) Netzwerk‐Ping (50× 8.8.8.8)
    out = subprocess.run(["ping", "-c", "50", "8.8.8.8"], capture_output=True).stdout.decode()
    vals = list(map(float, re.findall(r"time=(\d+\.\d+)", out)))
    metrics["ping_avg_ms"] = sum(vals) / len(vals)
    metrics["ping_p95_ms"] = sorted(vals)[int(0.95 * len(vals))]

    # UUID ggf. ausblenden
    if not opts.get(CONF_SHOW_UUID):
        res.pop("benchmark_id", None)

    res["results"] = metrics
    return res
