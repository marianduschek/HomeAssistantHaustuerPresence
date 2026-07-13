"""Config flow for Haustuer Presence."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.util import slugify

from .const import (
    CONF_ALLOW_TRACKER_FALLBACK,
    CONF_AREA_ENTITY,
    CONF_CONFIRM_SECONDS,
    CONF_COOLDOWN_SECONDS,
    CONF_DISTANCE_ENTITIES,
    CONF_DOOR_AREAS,
    CONF_INSIDE_AREAS,
    CONF_MAX_DISTANCE,
    CONF_MAX_PROFILE_SCORE,
    CONF_MIN_CONFIDENCE,
    CONF_MIN_POINTS,
    CONF_NAME,
    CONF_OBSERVE_ONLY,
    CONF_TRACKER_ENTITY,
    CONF_WINDOW_SECONDS,
    DEFAULT_ALLOW_TRACKER_FALLBACK,
    DEFAULT_CONFIRM_SECONDS,
    DEFAULT_COOLDOWN_SECONDS,
    DEFAULT_MAX_DISTANCE,
    DEFAULT_MAX_PROFILE_SCORE,
    DEFAULT_MIN_CONFIDENCE,
    DEFAULT_MIN_POINTS,
    DEFAULT_OBSERVE_ONLY,
    DEFAULT_WINDOW_SECONDS,
    DOMAIN,
)


def _comma_list(value: str | list[str] | None) -> list[str]:
    """Normalize comma-separated text to a clean list."""
    if isinstance(value, list):
        return [item.strip() for item in value if item.strip()]
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _defaults_for_form(data: Mapping[str, Any]) -> dict[str, Any]:
    """Convert stored values to values accepted by selectors."""
    defaults = dict(data)
    defaults[CONF_INSIDE_AREAS] = ", ".join(
        _comma_list(defaults.get(CONF_INSIDE_AREAS))
    )
    defaults[CONF_DOOR_AREAS] = ", ".join(_comma_list(defaults.get(CONF_DOOR_AREAS)))
    return defaults


def _normalize_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Normalize config flow values before storage."""
    normalized = dict(user_input)
    normalized[CONF_INSIDE_AREAS] = _comma_list(normalized.get(CONF_INSIDE_AREAS))
    normalized[CONF_DOOR_AREAS] = _comma_list(normalized.get(CONF_DOOR_AREAS))
    for optional_entity in (CONF_AREA_ENTITY, CONF_TRACKER_ENTITY):
        if not normalized.get(optional_entity):
            normalized.pop(optional_entity, None)
    return normalized


def _config_schema(defaults: Mapping[str, Any] | None = None) -> vol.Schema:
    """Return the person and measurement-point schema."""
    values = _defaults_for_form(defaults or {})
    area_key = (
        vol.Optional(
            CONF_AREA_ENTITY,
            description={"suggested_value": values[CONF_AREA_ENTITY]},
        )
        if values.get(CONF_AREA_ENTITY)
        else vol.Optional(CONF_AREA_ENTITY)
    )
    tracker_key = (
        vol.Optional(
            CONF_TRACKER_ENTITY,
            description={"suggested_value": values[CONF_TRACKER_ENTITY]},
        )
        if values.get(CONF_TRACKER_ENTITY)
        else vol.Optional(CONF_TRACKER_ENTITY)
    )
    return vol.Schema(
        {
            vol.Required(
                CONF_NAME,
                default=values.get(CONF_NAME, ""),
            ): selector.TextSelector(),
            vol.Required(
                CONF_DISTANCE_ENTITIES,
                default=values.get(CONF_DISTANCE_ENTITIES, []),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor",
                    multiple=True,
                )
            ),
            area_key: selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            tracker_key: selector.EntitySelector(
                selector.EntitySelectorConfig(domain="device_tracker")
            ),
            vol.Optional(
                CONF_INSIDE_AREAS,
                default=values.get(CONF_INSIDE_AREAS, ""),
            ): selector.TextSelector(),
            vol.Optional(
                CONF_DOOR_AREAS,
                default=values.get(CONF_DOOR_AREAS, ""),
            ): selector.TextSelector(),
            vol.Required(
                CONF_CONFIRM_SECONDS,
                default=values.get(
                    CONF_CONFIRM_SECONDS,
                    DEFAULT_CONFIRM_SECONDS,
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=10,
                    step=0.1,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="s",
                )
            ),
            vol.Required(
                CONF_WINDOW_SECONDS,
                default=values.get(
                    CONF_WINDOW_SECONDS,
                    DEFAULT_WINDOW_SECONDS,
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=600,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="s",
                )
            ),
            vol.Required(
                CONF_COOLDOWN_SECONDS,
                default=values.get(
                    CONF_COOLDOWN_SECONDS,
                    DEFAULT_COOLDOWN_SECONDS,
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=86400,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="s",
                )
            ),
            vol.Required(
                CONF_MIN_POINTS,
                default=values.get(CONF_MIN_POINTS, DEFAULT_MIN_POINTS),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=20,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_MAX_DISTANCE,
                default=values.get(
                    CONF_MAX_DISTANCE,
                    DEFAULT_MAX_DISTANCE,
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=100,
                    step=0.1,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="m",
                )
            ),
            vol.Required(
                CONF_MAX_PROFILE_SCORE,
                default=values.get(
                    CONF_MAX_PROFILE_SCORE,
                    DEFAULT_MAX_PROFILE_SCORE,
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0.01,
                    max=3,
                    step=0.01,
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_MIN_CONFIDENCE,
                default=values.get(
                    CONF_MIN_CONFIDENCE,
                    DEFAULT_MIN_CONFIDENCE,
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=1,
                    step=0.01,
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_OBSERVE_ONLY,
                default=values.get(
                    CONF_OBSERVE_ONLY,
                    DEFAULT_OBSERVE_ONLY,
                ),
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_ALLOW_TRACKER_FALLBACK,
                default=values.get(
                    CONF_ALLOW_TRACKER_FALLBACK,
                    DEFAULT_ALLOW_TRACKER_FALLBACK,
                ),
            ): selector.BooleanSelector(),
        }
    )


class HaustuerPresenceConfigFlow(
    config_entries.ConfigFlow,
    domain=DOMAIN,
):
    """Handle a config flow for one tracked person."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Create a person classifier."""
        if user_input is not None:
            normalized = _normalize_input(user_input)
            await self.async_set_unique_id(slugify(normalized[CONF_NAME]))
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=normalized[CONF_NAME],
                data=normalized,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=_config_schema(),
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow."""
        return HaustuerPresenceOptionsFlow()


class HaustuerPresenceOptionsFlow(config_entries.OptionsFlowWithReload):
    """Edit measurement points and classifier behavior."""

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Update all configurable values."""
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data=_normalize_input(user_input),
            )

        current = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=_config_schema(current),
        )
