import os
import json
import datetime
import platform
import psutil

from homeassistant.core import HomeAssistant

DOMAIN = "benchmark"
DATA_FILE = ".benchmark_history.json"

def _ensure_file(path: str) -> None:
    """Legen Sie die History-Datei an, falls nicht vorhanden."""
    if not os.path.exists(path):
        with open(path, "w") as fp:
            json.dump([], fp)

def _append_history(path: str, entry: dict) -> None:
    """Füge einen Eintrag zur History-Datei hinzu."""
    try:
        data = json.load(open(path))
    except Exception:
        data = []
    data.append(entry)
    with open(path, "w") as fp:
        json.dump(data, fp)

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Registriere den benchmark.start Dienst."""
    history_path = hass.config.path(DATA_FILE)

    # Stelle sicher, dass die Datei existiert (im Executor)
    await hass.async_add_executor_job(_ensure_file, history_path)

    async def handle_start(call):
        """Fahre den simplen Hardware-Test durch und speichere das Ergebnis."""
        # 1) Timestamp
        ts = datetime.datetime.now().isoformat()
        # 2) CPU-Cores (physisch, sonst logisch)
        cores = psutil.cpu_count(logical=False) or psutil.cpu_count()
        # 3) Gesamt-RAM in MB
        ram_mb = psutil.virtual_memory().total // (1024 * 1024)
        # 4) (Optional) weitere Tests hier einfügen...

        result = {
            "timestamp": ts,
            "hardware": {
                "cpu_cores": cores,
                "total_ram_mb": ram_mb,
                "platform": platform.platform()
            }
        }

        # Speichere in der History (im Executor)
        await hass.async_add_executor_job(_append_history, history_path, result)

        # Optional: Event feuern, auf das Automationen lauschen könnten
        hass.bus.async_fire(f"{DOMAIN}_completed", result)

    # Dienst registrieren
    hass.services.async_register(DOMAIN, "start", handle_start)

    return True
