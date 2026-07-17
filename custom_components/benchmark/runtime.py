"""Runtime model and benchmark orchestration."""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
import time
import urllib.parse
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_DEFAULT_PROFILE,
    CONF_NOTIFICATIONS,
    CONFIDENCE_UNKNOWN,
    DEFAULT_NOTIFICATIONS,
    DEFAULT_PROFILE,
    DOMAIN,
    EXPORT_CSV_FILE,
    EXPORT_JSON_FILE,
    GITHUB_ISSUES_URL,
    GITHUB_REPOSITORY_URL,
    INTEGRATION_VERSION,
    MAX_HISTORY_ENTRIES,
    NAME,
    PROFILE_STANDARD,
    PUBLIC_WORLDLIST_URL,
    RESTART_PENDING_MAX_AGE_S,
    RESULT_SCHEMA,
    STATUS_ERROR,
    STATUS_IDLE,
    STATUS_RESTARTING,
    STATUS_RUNNING,
    WORLDLIST_EXPORT_FILE,
)
from .dashboard import build_dashboard_yaml
from .engine import canonical_profile, run_benchmark
from .storage import write_csv, write_json

_LOGGER = logging.getLogger(__name__)

type BenchmarkConfigEntry = ConfigEntry["BenchmarkRuntime"]


class BenchmarkRuntime:
    """Own the runtime state for one config entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: BenchmarkConfigEntry,
        store: Store[dict[str, Any]],
        stored: dict[str, Any],
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.store = store
        self.history: list[dict[str, Any]] = [
            item
            for item in stored.get("history", [])
            if isinstance(item, dict) and item.get("schema") == RESULT_SCHEMA
        ][-MAX_HISTORY_ENTRIES:]
        self.legacy_history: list[dict[str, Any]] = [
            item for item in stored.get("legacy_history", []) if isinstance(item, dict)
        ]
        pending = stored.get("pending_restart")
        self.pending_restart: dict[str, Any] | None = (
            pending if isinstance(pending, dict) else None
        )
        self.running = False
        self.status = STATUS_IDLE
        self.progress = 0
        self.progress_message = "Ready"
        self.last_error: str | None = None
        self.last_export: dict[str, str] | None = None
        self.last_worldlist_export: str | None = None
        self._lock = asyncio.Lock()
        self.coordinator: DataUpdateCoordinator[dict[str, Any]] = DataUpdateCoordinator(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
        )
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=NAME,
            manufacturer="Jarnsen",
            model="Home Assistant responsiveness benchmark",
            sw_version=INTEGRATION_VERSION,
            configuration_url=GITHUB_REPOSITORY_URL,
        )
        self.coordinator.async_set_updated_data(self.snapshot())

    @property
    def latest(self) -> dict[str, Any] | None:
        """Return the newest v3 result."""
        return self.history[-1] if self.history else None

    @property
    def default_profile(self) -> str:
        """Return the configured default profile."""
        return canonical_profile(
            self.entry.options.get(CONF_DEFAULT_PROFILE, DEFAULT_PROFILE)
        )

    @property
    def notifications_enabled(self) -> bool:
        """Return whether completion notifications are enabled."""
        return bool(
            self.entry.options.get(
                CONF_NOTIFICATIONS,
                DEFAULT_NOTIFICATIONS,
            )
        )

    def snapshot(self) -> dict[str, Any]:
        """Return the small in-memory state exposed to entities."""
        latest = self.latest
        scores = latest.get("scores", {}) if latest else {}
        validity = latest.get("validity", {}) if latest else {}
        measurements = latest.get("measurements", {}) if latest else {}
        system = latest.get("system", {}) if latest else {}
        secondary = latest.get("secondary", {}) if latest else {}
        best_score = max(
            (
                int(item.get("scores", {}).get("ha_performance_score", 0))
                for item in self.history
            ),
            default=None,
        )
        return {
            "running": self.running,
            "status": self.status,
            "progress": self.progress,
            "progress_message": self.progress_message,
            "last_error": self.last_error,
            "latest": latest,
            "scores": scores,
            "validity": validity,
            "measurements": measurements,
            "system": system,
            "secondary": secondary,
            "history_count": len(self.history),
            "legacy_history_count": len(self.legacy_history),
            "local_best_score": best_score,
            "last_export": self.last_export,
            "last_worldlist_export": self.last_worldlist_export,
            "repository_url": GITHUB_REPOSITORY_URL,
            "worldlist_url": PUBLIC_WORLDLIST_URL,
            "confidence": validity.get(
                "confidence",
                CONFIDENCE_UNKNOWN,
            ),
        }

    @callback
    def publish(self) -> None:
        """Publish runtime data to all coordinator entities."""
        self.coordinator.async_set_updated_data(self.snapshot())

    async def _save(self) -> None:
        await self.store.async_save(
            {
                "history": self.history[-MAX_HISTORY_ENTRIES:],
                "legacy_history": self.legacy_history,
                "pending_restart": self.pending_restart,
            }
        )

    async def _set_progress(self, value: int, message: str) -> None:
        self.progress = max(0, min(100, int(value)))
        self.progress_message = message
        self.publish()

    async def _notify(
        self,
        title: str,
        message: str,
        *,
        force: bool = False,
    ) -> None:
        if not force and not self.notifications_enabled:
            return
        try:
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": title,
                    "message": message,
                    "notification_id": (f"{DOMAIN}_{title.lower().replace(' ', '_')}"),
                },
                blocking=False,
            )
        except Exception:  # Notifications must never invalidate a result.
            _LOGGER.warning(
                "Could not create benchmark notification: %s",
                title,
                exc_info=True,
            )

    async def async_run(
        self,
        profile: str | None = None,
        *,
        restart_recovery_time_s: float | None = None,
    ) -> dict[str, Any]:
        """Run and persist a benchmark."""
        selected_profile = canonical_profile(profile or self.default_profile)
        if self._lock.locked():
            raise HomeAssistantError("A benchmark is already running")

        async with self._lock:
            self.running = True
            self.status = STATUS_RUNNING
            self.last_error = None
            await self._set_progress(1, f"Starting {selected_profile} profile")
            try:
                result = await run_benchmark(
                    self.hass,
                    selected_profile,
                    restart_recovery_time_s,
                    self._set_progress,
                )
                self.history.append(result)
                self.history = self.history[-MAX_HISTORY_ENTRIES:]
                await self._save()
                await self._set_progress(100, "Benchmark completed")
                score = result["scores"]["ha_performance_score"]
                confidence = result["validity"]["confidence"]
                await self._notify(
                    "Benchmark completed",
                    (
                        f"HA Performance Score: **{score} / 10,000**  \n"
                        f"Core: {result['scores']['ha_core_score']} · "
                        f"Fluidity: {result['scores']['fluidity_score']} · "
                        f"Confidence: {confidence}"
                    ),
                )
                _LOGGER.info(
                    (
                        "Benchmark completed: profile=%s score=%s "
                        "confidence=%s duration_s=%s"
                    ),
                    selected_profile,
                    score,
                    confidence,
                    result["duration_s"],
                )
            except asyncio.CancelledError:
                self.last_error = "Benchmark cancelled"
                self.status = STATUS_ERROR
                await self._set_progress(0, "Benchmark cancelled")
                raise
            except Exception as err:
                self.last_error = str(err)
                self.status = STATUS_ERROR
                await self._set_progress(0, "Benchmark failed")
                _LOGGER.exception("Benchmark failed")
                await self._notify(
                    "Benchmark failed",
                    str(err),
                    force=True,
                )
                raise HomeAssistantError(f"Benchmark failed: {err}") from err
            else:
                return result
            finally:
                self.running = False
                if self.status != STATUS_ERROR:
                    self.status = STATUS_IDLE
                self.publish()

    async def async_prepare_restart(
        self,
        profile: str | None = None,
    ) -> None:
        """Persist a restart request and restart Home Assistant."""
        if self._lock.locked():
            raise HomeAssistantError("A benchmark is already running")
        selected_profile = canonical_profile(profile or self.default_profile)
        self.pending_restart = {
            "requested_at": time.time(),
            "profile": selected_profile,
        }
        self.status = STATUS_RESTARTING
        self.progress = 0
        self.progress_message = "Waiting for Home Assistant restart"
        await self._save()
        self.publish()
        await self._notify(
            "Restart benchmark",
            (
                "Home Assistant will restart now. The benchmark resumes "
                "automatically after startup."
            ),
            force=True,
        )
        try:
            await self.hass.services.async_call(
                "homeassistant",
                "restart",
                {},
                blocking=False,
            )
        except Exception as err:
            self.pending_restart = None
            self.status = STATUS_ERROR
            self.last_error = f"Could not restart Home Assistant: {err}"
            await self._save()
            self.publish()
            raise HomeAssistantError(self.last_error) from err

    async def async_resume_pending_restart(self) -> None:
        """Resume a pending restart benchmark after Home Assistant startup."""
        pending = self.pending_restart
        if not pending:
            return
        requested_at = pending.get("requested_at")
        profile = pending.get("profile", PROFILE_STANDARD)
        self.pending_restart = None
        await self._save()
        if not isinstance(requested_at, int | float):
            return
        elapsed = max(0.0, time.time() - float(requested_at))
        if elapsed > RESTART_PENDING_MAX_AGE_S:
            self.last_error = "Stale restart benchmark request discarded"
            self.status = STATUS_ERROR
            self.publish()
            await self._notify(
                "Restart benchmark cancelled",
                "The saved restart request was older than 15 minutes.",
                force=True,
            )
            return
        await self.async_run(
            str(profile),
            restart_recovery_time_s=round(elapsed, 3),
        )

    def build_worldlist_payload(self) -> dict[str, Any]:
        """Build a privacy-reduced payload for public comparison."""
        latest = self.latest
        if latest is None:
            raise HomeAssistantError("Run a benchmark before exporting")
        system = latest.get("system", {})
        return {
            "schema": latest["schema"],
            "result_id": latest["result_id"],
            "timestamp": latest["timestamp"],
            "protocol_version": latest["protocol_version"],
            "score_version": latest["score_version"],
            "protocol": latest.get("protocol", {}),
            "profile": latest["profile"],
            "duration_s": latest["duration_s"],
            "scores": latest["scores"],
            "measurements": latest["measurements"],
            "system": {
                "home_assistant_version": system.get("home_assistant_version"),
                "installation_type": system.get("installation_type"),
                "entity_count": system.get("entity_count"),
                "device_count": system.get("device_count"),
                "config_entry_count": system.get("config_entry_count"),
                "recorder_loaded": system.get("recorder_loaded"),
                "architecture": system.get("architecture"),
                "cpu_model": system.get("cpu_model"),
                "device_model": system.get("device_model"),
                "operating_system": system.get("operating_system"),
                "python_version": system.get("python_version"),
                "cpu_cores_logical": system.get("cpu_cores_logical"),
                "ram_total_mb": system.get("ram_total_mb"),
            },
            "secondary": latest.get("secondary", {}),
            "validity": latest.get("validity", {}),
            "privacy": {
                "anonymous": True,
                "excluded": [
                    "entity_ids",
                    "device_names",
                    "hostnames",
                    "ip_addresses",
                    "usernames",
                    "tokens",
                    "config_path",
                    "integration_configuration",
                ],
            },
        }

    async def async_export(self) -> dict[str, str]:
        """Export v3 and migrated legacy history."""
        json_path = self.hass.config.path(EXPORT_JSON_FILE)
        csv_path = self.hass.config.path(EXPORT_CSV_FILE)
        document = {
            "schema": "ha_homeassistant_performance_history_v3",
            "exported_at": dt.datetime.now(dt.UTC).isoformat(),
            "history": self.history,
            "legacy_v2_history": self.legacy_history,
        }
        await self.hass.async_add_executor_job(
            write_json,
            json_path,
            document,
        )
        await self.hass.async_add_executor_job(
            write_csv,
            csv_path,
            self.history,
        )
        self.last_export = {"json": json_path, "csv": csv_path}
        self.publish()
        await self._notify(
            "Benchmark export created",
            f"`{json_path}`  \n`{csv_path}`",
            force=True,
        )
        return self.last_export

    async def async_export_worldlist(self) -> str:
        """Export the privacy-reduced latest standard result."""
        payload = self.build_worldlist_payload()
        if payload["profile"] != PROFILE_STANDARD:
            raise HomeAssistantError(
                "Only the standard profile is eligible for the worldlist"
            )
        path = self.hass.config.path(WORLDLIST_EXPORT_FILE)
        await self.hass.async_add_executor_job(write_json, path, payload)
        self.last_worldlist_export = path
        self.publish()
        await self._notify(
            "Worldlist export created",
            f"Anonymous comparison payload written to `{path}`.",
            force=True,
        )
        return path

    async def async_show_ranking_issue(self) -> None:
        """Create the payload and show a prefilled GitHub issue link."""
        path = await self.async_export_worldlist()
        latest = self.latest or {}
        score = latest.get("scores", {}).get("ha_performance_score")
        title = f"Ranking submission: HA score {score}"
        url = f"{GITHUB_ISSUES_URL}?" + urllib.parse.urlencode(
            {
                "template": "ranking_submission.yml",
                "title": title,
            }
        )
        await self._notify(
            "Submit benchmark result",
            (
                f"Open [the ranking form]({url}) and paste the content of "
                f"`{path}`. The public pipeline recalculates the score from "
                "the submitted measurements."
            ),
            force=True,
        )

    async def async_show_dashboard(self) -> None:
        """Show the ready-to-copy dashboard YAML."""
        await self._notify(
            "Benchmark dashboard YAML",
            f"```yaml\n{build_dashboard_yaml()}\n```",
            force=True,
        )

    async def async_show_support_issue(self) -> None:
        """Show a privacy-safe prefilled support issue URL."""
        latest = self.latest or {}
        score = latest.get("scores", {}).get("ha_performance_score")
        body = (
            "## Problem\n\nDescribe the problem here.\n\n"
            "## Basic diagnostic information\n\n"
            f"- Integration version: {INTEGRATION_VERSION}\n"
            f"- Last score: {score}\n"
            f"- Last error: {self.last_error}\n"
            "- Diagnostics attached: no\n"
        )
        url = f"{GITHUB_ISSUES_URL}?" + urllib.parse.urlencode(
            {
                "title": f"Benchmark issue {INTEGRATION_VERSION}",
                "body": body,
                "labels": "bug",
            }
        )
        await self._notify(
            "Report a benchmark issue",
            f"Open the [prefilled GitHub issue]({url}).",
            force=True,
        )
