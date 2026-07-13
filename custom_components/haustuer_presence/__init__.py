"""Haustuer Presence integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError

from .const import (
    CALIBRATION_KINDS,
    DOMAIN,
    PLATFORMS,
    SERVICE_CLEAR_CALIBRATION,
    SERVICE_FORCE_ARM,
    SERVICE_RECORD_SAMPLE,
    SERVICE_RESET,
)
from .manager import PresenceManager

type HaustuerPresenceConfigEntry = ConfigEntry[PresenceManager]

SERVICE_ENTRY_SCHEMA = vol.Schema(
    {
        vol.Required("entry_id"): str,
    }
)
SERVICE_RECORD_SCHEMA = SERVICE_ENTRY_SCHEMA.extend(
    {
        vol.Required("profile"): str,
        vol.Required("kind"): vol.In(CALIBRATION_KINDS),
    }
)
SERVICE_CLEAR_SCHEMA = SERVICE_ENTRY_SCHEMA.extend(
    {
        vol.Optional("profile"): str,
    }
)


async def async_setup(hass: HomeAssistant, _config: dict[str, Any]) -> bool:
    """Set up integration-wide actions."""
    managers: dict[str, PresenceManager] = hass.data.setdefault(DOMAIN, {})

    def manager_for(call: ServiceCall) -> PresenceManager:
        entry_id = call.data["entry_id"]
        if manager := managers.get(entry_id):
            return manager
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entry_not_loaded",
            translation_placeholders={"entry_id": entry_id},
        )

    async def record_sample(call: ServiceCall) -> None:
        await manager_for(call).async_record_sample(
            call.data["profile"],
            call.data["kind"],
        )

    async def clear_calibration(call: ServiceCall) -> None:
        await manager_for(call).async_clear_calibration(call.data.get("profile"))

    async def force_arm(call: ServiceCall) -> None:
        await manager_for(call).async_force_arm()

    async def reset(call: ServiceCall) -> None:
        await manager_for(call).async_reset()

    hass.services.async_register(
        DOMAIN,
        SERVICE_RECORD_SAMPLE,
        record_sample,
        schema=SERVICE_RECORD_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR_CALIBRATION,
        clear_calibration,
        schema=SERVICE_CLEAR_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_FORCE_ARM,
        force_arm,
        schema=SERVICE_ENTRY_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RESET,
        reset,
        schema=SERVICE_ENTRY_SCHEMA,
    )
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HaustuerPresenceConfigEntry,
) -> bool:
    """Set up one tracked person from a config entry."""
    manager = PresenceManager(hass, entry)
    entry.runtime_data = manager
    hass.data[DOMAIN][entry.entry_id] = manager
    await manager.async_start()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: HaustuerPresenceConfigEntry,
) -> bool:
    """Unload a tracked person."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    await entry.runtime_data.async_stop()
    hass.data[DOMAIN].pop(entry.entry_id, None)
    return True
