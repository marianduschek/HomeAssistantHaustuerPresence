"""Sensors for Haustuer Presence."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CLASS_AWAY,
    CLASS_INSIDE,
    CLASS_OUTSIDE,
    CLASS_UNKNOWN,
    DOMAIN,
    PHASE_ARMED,
    PHASE_ARRIVING,
    PHASE_AUTHORIZED,
    PHASE_COOLDOWN,
    PHASE_DEPARTING,
    PHASE_IDLE,
    SIGNAL_UPDATE,
)
from .manager import PresenceManager


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up classifier sensors."""
    manager: PresenceManager = entry.runtime_data
    async_add_entities(
        [
            PhaseSensor(manager),
            ClassificationSensor(manager),
            ConfidenceSensor(manager),
        ]
    )


class PresenceSensor(SensorEntity):
    """Base class for event-driven classifier sensors."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, manager: PresenceManager, key: str) -> None:
        """Initialize a sensor."""
        self.manager = manager
        self._attr_unique_id = f"{manager.entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, manager.entry.entry_id)},
            name=manager.name,
            manufacturer="Haustuer Presence",
            model="Calibrated BLE presence classifier",
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to manager updates."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SIGNAL_UPDATE}_{self.manager.entry.entry_id}",
                self._handle_update,
            )
        )

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()


class PhaseSensor(PresenceSensor):
    """Expose the movement state machine phase."""

    _attr_translation_key = "phase"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [
        PHASE_IDLE,
        PHASE_DEPARTING,
        PHASE_ARMED,
        PHASE_ARRIVING,
        PHASE_AUTHORIZED,
        PHASE_COOLDOWN,
    ]
    _attr_icon = "mdi:state-machine"

    def __init__(self, manager: PresenceManager) -> None:
        super().__init__(manager, "phase")

    @property
    def native_value(self) -> str:
        return self.manager.phase

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "reason": self.manager.last_reason,
            "observe_only": self.manager.observe_only,
            "sample_counts": self.manager.calibration.sample_counts(),
            "distances": self.manager.distances,
        }


class ClassificationSensor(PresenceSensor):
    """Expose the current calibrated location class."""

    _attr_translation_key = "classification"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [
        CLASS_UNKNOWN,
        CLASS_INSIDE,
        CLASS_OUTSIDE,
        CLASS_AWAY,
    ]
    _attr_icon = "mdi:map-marker-question"

    def __init__(self, manager: PresenceManager) -> None:
        super().__init__(manager, "classification")

    @property
    def native_value(self) -> str:
        return self.manager.classification.kind

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "profile": self.manager.classification.profile,
            "score": self.manager.classification.score,
            "points_used": self.manager.classification.points_used,
        }


class ConfidenceSensor(PresenceSensor):
    """Expose classifier confidence."""

    _attr_translation_key = "confidence"
    _attr_native_unit_of_measurement = "%"
    _attr_icon = "mdi:percent-circle-outline"

    def __init__(self, manager: PresenceManager) -> None:
        super().__init__(manager, "confidence")

    @property
    def native_value(self) -> float:
        return round(self.manager.classification.confidence * 100, 1)
