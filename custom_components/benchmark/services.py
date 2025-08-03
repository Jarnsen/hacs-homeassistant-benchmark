import platform
import datetime
import psutil

def run_benchmark(hass):
    """Nur ein sehr einfacher Hardware-Test."""
    now = datetime.datetime.now().isoformat()
    cores = psutil.cpu_count(logical=False) or psutil.cpu_count()
    ram_mb = psutil.virtual_memory().total // (1024 * 1024)

    return {
        "timestamp": now,
        "hardware": {
            "cpu_cores": cores,
            "total_ram_mb": ram_mb
        }
    }
