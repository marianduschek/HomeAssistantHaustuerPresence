"""Binary sensors for Haustuer Presence."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, SIGNAL_UPDATE
from .manager import PresenceManager


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up classifier binary sensors."""
    manager: PresenceManager = entry.runtime_data
    async_add_entities(
        [
            CandidateBinarySensor(manager),
            AuthorizedBinarySensor(manager),
        ]
    )


class PresenceBinarySensor(BinarySensorEntity):
    """Base class for manager-backed binary sensors."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, manager: PresenceManager, key: str) -> None:
        """Initialize a binary sensor."""
        self.manager = manager
        self._attr_unique_id = f"{manager.entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, manager.entry.entry_id)}
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates."""
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


class CandidateBinarySensor(PresenceBinarySensor):
    """Show a confirmed or pending outside-arrival candidate."""

    _attr_translation_key = "arrival_candidate"
    _attr_icon = "mdi:door-open"

    def __init__(self, manager: PresenceManager) -> None:
        super().__init__(manager, "arrival_candidate")

    @property
    def is_on(self) -> bool:
        return self.manager.candidate

    @property
    def extra_state_attributes(self) -> dict:
        return self.manager.event_data


class AuthorizedBinarySensor(PresenceBinarySensor):
    """Expose the live-mode authorization window."""

    _attr_translation_key = "arrival_authorized"
    _attr_icon = "mdi:door-open"

    def __init__(self, manager: PresenceManager) -> None:
        super().__init__(manager, "arrival_authorized")

    @property
    def is_on(self) -> bool:
        return self.manager.authorized

    @property
    def available(self) -> bool:
        """Hide authorization availability while deliberately observing."""
        return not self.manager.observe_only

    @property
    def extra_state_attributes(self) -> dict:
        return self.manager.event_data
