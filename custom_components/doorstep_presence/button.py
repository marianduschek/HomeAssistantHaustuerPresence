"""Calibration buttons for Doorstep Presence."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CLASS_AWAY, CLASS_INSIDE, CLASS_OUTSIDE, DOMAIN
from .manager import PresenceManager


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up calibration buttons."""
    manager: PresenceManager = entry.runtime_data
    async_add_entities(
        [
            CaptureButton(manager, "inside", CLASS_INSIDE),
            CaptureButton(manager, "outside", CLASS_OUTSIDE),
            CaptureButton(manager, "away", CLASS_AWAY),
            ClearCalibrationButton(manager),
        ]
    )


class CalibrationButton(ButtonEntity):
    """Base class for calibration actions."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_should_poll = False

    def __init__(self, manager: PresenceManager, key: str) -> None:
        """Initialize a calibration button."""
        self.manager = manager
        self._attr_unique_id = f"{manager.entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, manager.entry.entry_id)}
        )


class CaptureButton(CalibrationButton):
    """Capture the current vector in a default profile."""

    _attr_icon = "mdi:map-marker-plus"

    def __init__(
        self,
        manager: PresenceManager,
        profile_name: str,
        kind: str,
    ) -> None:
        super().__init__(manager, f"capture_{profile_name}")
        self._attr_translation_key = f"capture_{profile_name}"
        self.profile_name = profile_name
        self.kind = kind

    async def async_press(self) -> None:
        """Capture one calibration sample."""
        await self.manager.async_record_sample(
            self.profile_name,
            self.kind,
        )


class ClearCalibrationButton(CalibrationButton):
    """Clear all captured profiles."""

    _attr_translation_key = "clear_calibration"
    _attr_icon = "mdi:delete-sweep"

    def __init__(self, manager: PresenceManager) -> None:
        super().__init__(manager, "clear_calibration")

    async def async_press(self) -> None:
        """Clear all calibration samples."""
        await self.manager.async_clear_calibration()
