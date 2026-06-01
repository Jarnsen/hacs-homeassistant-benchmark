"""Constants for Home Assistant Benchmark."""

DOMAIN = "benchmark"
NAME = "Home Assistant Real World Benchmark"
INTEGRATION_VERSION = "2.1.7"
ATTRIBUTION = "Home Assistant Benchmark by Jarnsen"

GITHUB_REPOSITORY = "Jarnsen/hacs-homeassistant-benchmark"
GITHUB_REPOSITORY_URL = f"https://github.com/{GITHUB_REPOSITORY}"
GITHUB_ISSUES_URL = f"{GITHUB_REPOSITORY_URL}/issues/new"

DATA_FILE = ".benchmark_history.json"
META_FILE = ".benchmark_meta.json"
EXPORT_JSON_FILE = "benchmark_export.json"
EXPORT_CSV_FILE = "benchmark_export.csv"
WORLDLIST_EXPORT_FILE = "benchmark_worldlist_export.json"
RESTART_STATE_FILE = ".benchmark_restart.json"

DATA_ENTITIES = f"{DOMAIN}_entities"
DATA_HISTORY = f"{DOMAIN}_history"
DATA_RUNNING = f"{DOMAIN}_running"
DATA_PROGRESS = f"{DOMAIN}_progress"
DATA_PROGRESS_MESSAGE = f"{DOMAIN}_progress_message"
DATA_LAST_ERROR = f"{DOMAIN}_last_error"
DATA_LATEST = f"{DOMAIN}_latest"
DATA_LAST_EXPORT = f"{DOMAIN}_last_export"
DATA_LAST_WORLDLIST_EXPORT = f"{DOMAIN}_last_worldlist_export"
DATA_DASHBOARD_YAML = f"{DOMAIN}_dashboard_yaml"
DATA_ISSUE_URL = f"{DOMAIN}_issue_url"
DATA_RANKING_ISSUE_URL = f"{DOMAIN}_ranking_issue_url"
DATA_REPOSITORY_URL = f"{DOMAIN}_repository_url"

MAX_HISTORY_ENTRIES = 50
SCORE_WARNING_LIMIT = 3500

PROFILE_LIGHT = "light"
PROFILE_NORMAL = "normal"
PROFILE_HEAVY = "heavy"
PROFILES = (PROFILE_LIGHT, PROFILE_NORMAL, PROFILE_HEAVY)
