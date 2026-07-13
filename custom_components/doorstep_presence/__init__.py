"""Doorstep Presence integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import area_registry as ar

from .const import (
    CALIBRATION_KINDS,
    CONF_COOLDOWN_SECONDS,
    CONF_DOOR_AREAS,
    CONF_INSIDE_AREAS,
    DOMAIN,
    PLATFORMS,
    SERVICE_CLEAR_CALIBRATION,
    SERVICE_FORCE_ARM,
    SERVICE_RECORD_SAMPLE,
    SERVICE_RESET,
)
from .manager import PresenceManager

type DoorstepPresenceConfigEntry = ConfigEntry[PresenceManager]


def _legacy_list(value: str | list[str] | None) -> list[str]:
    """Normalize values stored by version 1."""
    if isinstance(value, list):
        return value
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _migrate_settings(
    hass: HomeAssistant,
    settings: dict[str, Any],
) -> dict[str, Any]:
    """Convert legacy area names to stable HA area IDs."""
    migrated = dict(settings)
    registry = ar.async_get(hass)
    areas = registry.async_list_areas()
    names_to_ids = {area.name: area.id for area in areas}
    valid_ids = {area.id for area in areas}
    for key in (CONF_INSIDE_AREAS, CONF_DOOR_AREAS):
        if key in migrated:
            migrated[key] = [
                item if item in valid_ids else names_to_ids[item]
                for item in _legacy_list(migrated.get(key))
                if item in valid_ids or item in names_to_ids
            ]
    if migrated.get(CONF_COOLDOWN_SECONDS) == 600:
        migrated[CONF_COOLDOWN_SECONDS] = 20
    return migrated


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


async def async_migrate_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Migrate version 1 text areas to version 2 selector values."""
    if entry.version > 2:
        return False
    if entry.version == 1:
        hass.config_entries.async_update_entry(
            entry,
            data=_migrate_settings(hass, dict(entry.data)),
            options=_migrate_settings(hass, dict(entry.options)),
            version=2,
        )
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DoorstepPresenceConfigEntry,
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
    entry: DoorstepPresenceConfigEntry,
) -> bool:
    """Unload a tracked person."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    await entry.runtime_data.async_stop()
    hass.data[DOMAIN].pop(entry.entry_id, None)
    return True
