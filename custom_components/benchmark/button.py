"""Button entities for Home Assistant Performance Benchmark."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTRIBUTION,
    PROFILE_EXTENDED,
    PROFILE_QUICK,
    PROFILE_STANDARD,
    STATUS_RESTARTING,
)
from .runtime import BenchmarkConfigEntry, BenchmarkRuntime

ACTION_RUN = "run"
ACTION_RESTART = "restart"
ACTION_EXPORT = "export"
ACTION_WORLDLIST = "worldlist"
ACTION_RANKING = "ranking"
ACTION_DASHBOARD = "dashboard"
ACTION_ISSUE = "issue"


@dataclass(frozen=True, kw_only=True)
class BenchmarkButtonDescription(ButtonEntityDescription):
    """Describe a benchmark button."""

    action: str
    profile: str | None = None
    suggested_object_id: str


BUTTONS: tuple[BenchmarkButtonDescription, ...] = (
    BenchmarkButtonDescription(
        key="start_real_world_benchmark",
        translation_key="start_standard",
        icon="mdi:speedometer",
        action=ACTION_RUN,
        profile=PROFILE_STANDARD,
        suggested_object_id="benchmark_start_standard",
    ),
    BenchmarkButtonDescription(
        key="start_quick",
        translation_key="start_quick",
        icon="mdi:run-fast",
        action=ACTION_RUN,
        profile=PROFILE_QUICK,
        suggested_object_id="benchmark_start_quick",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BenchmarkButtonDescription(
        key="start_extended",
        translation_key="start_extended",
        icon="mdi:chart-timeline-variant-shimmer",
        action=ACTION_RUN,
        profile=PROFILE_EXTENDED,
        suggested_object_id="benchmark_start_extended",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BenchmarkButtonDescription(
        key="restart_and_run",
        translation_key="restart_and_run",
        icon="mdi:restart",
        action=ACTION_RESTART,
        profile=PROFILE_STANDARD,
        suggested_object_id="benchmark_restart_and_run",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BenchmarkButtonDescription(
        key="export_history",
        translation_key="export_history",
        icon="mdi:database-export-outline",
        action=ACTION_EXPORT,
        suggested_object_id="benchmark_export_history",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BenchmarkButtonDescription(
        key="export_worldlist",
        translation_key="export_worldlist",
        icon="mdi:earth",
        action=ACTION_WORLDLIST,
        suggested_object_id="benchmark_export_worldlist",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BenchmarkButtonDescription(
        key="create_ranking_issue",
        translation_key="prepare_ranking",
        icon="mdi:trophy",
        action=ACTION_RANKING,
        suggested_object_id="benchmark_prepare_ranking",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BenchmarkButtonDescription(
        key="show_dashboard",
        translation_key="show_dashboard",
        icon="mdi:view-dashboard-edit-outline",
        action=ACTION_DASHBOARD,
        suggested_object_id="benchmark_show_dashboard",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BenchmarkButtonDescription(
        key="create_issue",
        translation_key="report_issue",
        icon="mdi:github",
        action=ACTION_ISSUE,
        suggested_object_id="benchmark_report_issue",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    _hass,
    entry: BenchmarkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up benchmark buttons."""
    runtime = entry.runtime_data
    async_add_entities(BenchmarkButton(runtime, description) for description in BUTTONS)


class BenchmarkButton(CoordinatorEntity, ButtonEntity):
    """A coordinator-backed benchmark action button."""

    entity_description: BenchmarkButtonDescription
    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        runtime: BenchmarkRuntime,
        description: BenchmarkButtonDescription,
    ) -> None:
        super().__init__(runtime.coordinator)
        self.runtime = runtime
        self.entity_description = description
        self._attr_unique_id = f"{runtime.entry.entry_id}_{description.key}_button"
        self._attr_suggested_object_id = description.suggested_object_id
        self.internal_integration_suggested_object_id = description.suggested_object_id
        self.entity_id = f"button.{description.suggested_object_id}"
        self._attr_device_info = runtime.device_info

    @property
    def suggested_object_id(self) -> str:
        """Keep documented default entity IDs stable across HA versions."""
        return self.entity_description.suggested_object_id

    @property
    def available(self) -> bool:
        """Disable actions that cannot safely run in the current state."""
        if not super().available:
            return False
        action = self.entity_description.action
        if action in (ACTION_RUN, ACTION_RESTART):
            return not self.runtime.running and self.runtime.status != STATUS_RESTARTING
        if action in (ACTION_WORLDLIST, ACTION_RANKING):
            latest = self.runtime.latest
            return bool(
                latest
                and latest.get("profile") == PROFILE_STANDARD
                and latest.get("validity", {}).get("ranking_eligible")
            )
        if action == ACTION_EXPORT:
            return bool(self.runtime.history or self.runtime.legacy_history)
        return True

    async def async_press(self) -> None:
        """Execute the configured action."""
        description = self.entity_description
        if description.action == ACTION_RUN:
            await self.runtime.async_run(description.profile)
        elif description.action == ACTION_RESTART:
            await self.runtime.async_prepare_restart(description.profile)
        elif description.action == ACTION_EXPORT:
            await self.runtime.async_export()
        elif description.action == ACTION_WORLDLIST:
            await self.runtime.async_export_worldlist()
        elif description.action == ACTION_RANKING:
            await self.runtime.async_show_ranking_issue()
        elif description.action == ACTION_DASHBOARD:
            await self.runtime.async_show_dashboard()
        elif description.action == ACTION_ISSUE:
            await self.runtime.async_show_support_issue()
