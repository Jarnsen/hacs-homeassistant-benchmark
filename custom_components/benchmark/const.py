"""Constants for Home Assistant Performance Benchmark."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "benchmark"
NAME: Final = "Home Assistant Performance Benchmark"
INTEGRATION_VERSION: Final = "3.0.0"
PROTOCOL_VERSION: Final = "3.0.0"
RESULT_SCHEMA: Final = "ha_homeassistant_performance_result_v3"
WORLDLIST_SCHEMA: Final = "ha_homeassistant_performance_worldlist_v3"
ATTRIBUTION: Final = "Home Assistant Performance Benchmark by Jarnsen"

GITHUB_REPOSITORY: Final = "Jarnsen/hacs-homeassistant-benchmark"
GITHUB_REPOSITORY_URL: Final = f"https://github.com/{GITHUB_REPOSITORY}"
GITHUB_ISSUES_URL: Final = f"{GITHUB_REPOSITORY_URL}/issues/new"
PUBLIC_WORLDLIST_URL: Final = (
    "https://raw.githubusercontent.com/Jarnsen/"
    "hacs-homeassistant-benchmark/main/docs/worldlist.json"
)

STORAGE_VERSION: Final = 1
STORAGE_KEY_PREFIX: Final = DOMAIN
LEGACY_HISTORY_FILE: Final = ".benchmark_history.json"
LEGACY_META_FILE: Final = ".benchmark_meta.json"
LEGACY_RESTART_FILE: Final = ".benchmark_restart.json"

EXPORT_JSON_FILE: Final = "benchmark_export.json"
EXPORT_CSV_FILE: Final = "benchmark_export.csv"
WORLDLIST_EXPORT_FILE: Final = "benchmark_worldlist_export.json"

MAX_HISTORY_ENTRIES: Final = 100
MAX_LEGACY_HISTORY_ENTRIES: Final = 50
RESTART_PENDING_MAX_AGE_S: Final = 15 * 60

PROFILE_QUICK: Final = "quick"
PROFILE_STANDARD: Final = "standard"
PROFILE_EXTENDED: Final = "extended"
PROFILES: Final = (PROFILE_QUICK, PROFILE_STANDARD, PROFILE_EXTENDED)
PROFILE_ALIASES: Final = {
    "light": PROFILE_QUICK,
    "normal": PROFILE_STANDARD,
    "heavy": PROFILE_EXTENDED,
}

CONF_DEFAULT_PROFILE: Final = "default_profile"
CONF_NOTIFICATIONS: Final = "notifications"
DEFAULT_PROFILE: Final = PROFILE_STANDARD
DEFAULT_NOTIFICATIONS: Final = True

SERVICE_START: Final = "start"
SERVICE_RESTART_AND_RUN: Final = "restart_and_run"
SERVICE_EXPORT: Final = "export"
SERVICE_EXPORT_WORLDLIST: Final = "export_worldlist"
SERVICE_CREATE_RANKING_ISSUE: Final = "create_ranking_issue"
SERVICE_SETUP_DASHBOARD: Final = "setup_dashboard"
SERVICE_CREATE_ISSUE: Final = "create_issue"
REGISTERED_SERVICES: Final = (
    SERVICE_START,
    SERVICE_RESTART_AND_RUN,
    SERVICE_EXPORT,
    SERVICE_EXPORT_WORLDLIST,
    SERVICE_CREATE_RANKING_ISSUE,
    SERVICE_SETUP_DASHBOARD,
    SERVICE_CREATE_ISSUE,
)

INTERNAL_PROBE_SERVICE: Final = "internal_latency_probe"
INTERNAL_PROBE_EVENT: Final = f"{DOMAIN}_latency_probe"
INTERNAL_PROBE_DOMAIN: Final = "benchmark_probe"

STATUS_IDLE: Final = "idle"
STATUS_RUNNING: Final = "running"
STATUS_RESTARTING: Final = "restarting"
STATUS_ERROR: Final = "error"

CONFIDENCE_HIGH: Final = "high"
CONFIDENCE_MEDIUM: Final = "medium"
CONFIDENCE_LOW: Final = "low"
CONFIDENCE_UNKNOWN: Final = "unknown"
