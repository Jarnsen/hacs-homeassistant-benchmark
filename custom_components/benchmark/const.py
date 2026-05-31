"""Constants for Home Assistant Benchmark."""

DOMAIN = "benchmark"
NAME = "Home Assistant Benchmark"
INTEGRATION_VERSION = "2.1.0"
ATTRIBUTION = "Home Assistant Benchmark by Jarnsen"

DATA_FILE = ".benchmark_history.json"
META_FILE = ".benchmark_meta.json"
EXPORT_JSON_FILE = "benchmark_export.json"
EXPORT_CSV_FILE = "benchmark_export.csv"
RESTART_STATE_FILE = ".benchmark_restart.json"

DATA_ENTITIES = f"{DOMAIN}_entities"
DATA_RUNNING = f"{DOMAIN}_running"
DATA_PROGRESS = f"{DOMAIN}_progress"
DATA_PROGRESS_MESSAGE = f"{DOMAIN}_progress_message"
DATA_LAST_ERROR = f"{DOMAIN}_last_error"
DATA_LATEST = f"{DOMAIN}_latest"
DATA_LAST_EXPORT = f"{DOMAIN}_last_export"
DATA_DASHBOARD_YAML = f"{DOMAIN}_dashboard_yaml"

MAX_HISTORY_ENTRIES = 50
SCORE_WARNING_LIMIT = 3500

PROFILE_LIGHT = "light"
PROFILE_NORMAL = "normal"
PROFILE_HEAVY = "heavy"
PROFILES = (PROFILE_LIGHT, PROFILE_NORMAL, PROFILE_HEAVY)
