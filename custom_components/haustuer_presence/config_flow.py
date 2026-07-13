"""Config flow for Haustuer Presence."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
import yaml
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import area_registry as ar
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
    CONF_YAML_CONFIG,
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

CONFIG_KEYS = {
    CONF_NAME,
    CONF_DISTANCE_ENTITIES,
    CONF_AREA_ENTITY,
    CONF_TRACKER_ENTITY,
    CONF_INSIDE_AREAS,
    CONF_DOOR_AREAS,
    CONF_CONFIRM_SECONDS,
    CONF_WINDOW_SECONDS,
    CONF_COOLDOWN_SECONDS,
    CONF_MIN_POINTS,
    CONF_MAX_DISTANCE,
    CONF_MAX_PROFILE_SCORE,
    CONF_MIN_CONFIDENCE,
    CONF_OBSERVE_ONLY,
    CONF_ALLOW_TRACKER_FALLBACK,
}


def _list_value(value: str | list[str] | None) -> list[str]:
    """Normalize legacy comma-separated values and selector lists."""
    if isinstance(value, list):
        return [item.strip() for item in value if item.strip()]
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _default_values() -> dict[str, Any]:
    """Return defaults shared by form and YAML setup."""
    return {
        CONF_DISTANCE_ENTITIES: [],
        CONF_INSIDE_AREAS: [],
        CONF_DOOR_AREAS: [],
        CONF_CONFIRM_SECONDS: DEFAULT_CONFIRM_SECONDS,
        CONF_WINDOW_SECONDS: DEFAULT_WINDOW_SECONDS,
        CONF_COOLDOWN_SECONDS: DEFAULT_COOLDOWN_SECONDS,
        CONF_MIN_POINTS: DEFAULT_MIN_POINTS,
        CONF_MAX_DISTANCE: DEFAULT_MAX_DISTANCE,
        CONF_MAX_PROFILE_SCORE: DEFAULT_MAX_PROFILE_SCORE,
        CONF_MIN_CONFIDENCE: DEFAULT_MIN_CONFIDENCE,
        CONF_OBSERVE_ONLY: DEFAULT_OBSERVE_ONLY,
        CONF_ALLOW_TRACKER_FALLBACK: DEFAULT_ALLOW_TRACKER_FALLBACK,
    }


def _normalize_input(user_input: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize config values before storage."""
    normalized = {key: value for key, value in user_input.items() if key in CONFIG_KEYS}
    normalized[CONF_DISTANCE_ENTITIES] = _list_value(
        normalized.get(CONF_DISTANCE_ENTITIES)
    )
    normalized[CONF_INSIDE_AREAS] = _list_value(normalized.get(CONF_INSIDE_AREAS))
    normalized[CONF_DOOR_AREAS] = _list_value(normalized.get(CONF_DOOR_AREAS))
    for optional_entity in (CONF_AREA_ENTITY, CONF_TRACKER_ENTITY):
        if not normalized.get(optional_entity):
            normalized.pop(optional_entity, None)
    return normalized


def _config_schema(defaults: Mapping[str, Any] | None = None) -> vol.Schema:
    """Return the identity and measurement-point schema."""
    values = {**_default_values(), **(defaults or {})}
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
                default=values[CONF_DISTANCE_ENTITIES],
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", multiple=True)
            ),
            area_key: selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            tracker_key: selector.EntitySelector(
                selector.EntitySelectorConfig(domain="device_tracker")
            ),
            vol.Required(
                CONF_INSIDE_AREAS,
                default=_list_value(values.get(CONF_INSIDE_AREAS)),
            ): selector.AreaSelector(selector.AreaSelectorConfig(multiple=True)),
            vol.Required(
                CONF_DOOR_AREAS,
                default=_list_value(values.get(CONF_DOOR_AREAS)),
            ): selector.AreaSelector(selector.AreaSelectorConfig(multiple=True)),
            vol.Required(
                CONF_CONFIRM_SECONDS,
                default=values[CONF_CONFIRM_SECONDS],
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
                default=values[CONF_WINDOW_SECONDS],
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
                default=values[CONF_COOLDOWN_SECONDS],
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
                default=values[CONF_MIN_POINTS],
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
                default=values[CONF_MAX_DISTANCE],
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
                default=values[CONF_MAX_PROFILE_SCORE],
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
                default=values[CONF_MIN_CONFIDENCE],
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
                default=values[CONF_OBSERVE_ONLY],
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_ALLOW_TRACKER_FALLBACK,
                default=values[CONF_ALLOW_TRACKER_FALLBACK],
            ): selector.BooleanSelector(),
        }
    )


def _yaml_schema(suggested_value: str = "") -> vol.Schema:
    """Return a YAML editor schema."""
    key = (
        vol.Required(
            CONF_YAML_CONFIG,
            description={"suggested_value": suggested_value},
        )
        if suggested_value
        else vol.Required(CONF_YAML_CONFIG)
    )
    return vol.Schema(
        {key: selector.TextSelector(selector.TextSelectorConfig(multiline=True))}
    )


def _parse_yaml(value: str) -> dict[str, Any]:
    """Parse one identity mapping from YAML."""
    try:
        parsed = yaml.safe_load(value)
    except yaml.YAMLError as err:
        raise vol.Invalid("Invalid YAML") from err
    if not isinstance(parsed, dict):
        raise vol.Invalid("YAML must contain one mapping")
    unknown = set(parsed) - CONFIG_KEYS
    if unknown:
        raise vol.Invalid(f"Unknown keys: {', '.join(sorted(unknown))}")
    return _normalize_input({**_default_values(), **parsed})


def _as_yaml(values: Mapping[str, Any]) -> str:
    """Serialize editable settings as YAML."""
    normalized = _normalize_input({**_default_values(), **values})
    return yaml.safe_dump(
        normalized,
        allow_unicode=True,
        sort_keys=False,
    )


def _validate_config(hass: HomeAssistant, values: Mapping[str, Any]) -> None:
    """Validate entity domains, selected areas, and point count."""
    distances = values[CONF_DISTANCE_ENTITIES]
    if not distances:
        raise vol.Invalid("At least one distance sensor is required")
    if int(values[CONF_MIN_POINTS]) > len(distances):
        raise vol.Invalid("Minimum points exceeds selected sensors")

    for entity_id in distances:
        state = hass.states.get(entity_id)
        if state is None or not entity_id.startswith("sensor."):
            raise vol.Invalid(f"Invalid distance sensor: {entity_id}")

    expected_domains = {
        CONF_AREA_ENTITY: "sensor.",
        CONF_TRACKER_ENTITY: "device_tracker.",
    }
    for key, domain_prefix in expected_domains.items():
        if (entity_id := values.get(key)) and (
            hass.states.get(entity_id) is None
            or not entity_id.startswith(domain_prefix)
        ):
            raise vol.Invalid(f"Invalid entity: {entity_id}")

    area_registry = ar.async_get(hass)
    for key in (CONF_INSIDE_AREAS, CONF_DOOR_AREAS):
        areas = values[key]
        if not areas:
            raise vol.Invalid("Inside and door areas are required")
        for area_id in areas:
            if area_registry.async_get_area(area_id) is None:
                raise vol.Invalid(f"Invalid area: {area_id}")


class HaustuerPresenceConfigFlow(
    config_entries.ConfigFlow,
    domain=DOMAIN,
):
    """Handle a config flow for one tracked identity."""

    VERSION = 2

    async def async_step_user(
        self,
        _user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Choose form or YAML setup."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["form", "yaml"],
        )

    async def async_step_form(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Create an identity using validated selectors."""
        errors: dict[str, str] = {}
        if user_input is not None:
            normalized = _normalize_input(user_input)
            try:
                _validate_config(self.hass, normalized)
            except (KeyError, TypeError, ValueError, vol.Invalid):
                errors["base"] = "invalid_config"
            else:
                await self.async_set_unique_id(slugify(normalized[CONF_NAME]))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=normalized[CONF_NAME],
                    data=normalized,
                )

        return self.async_show_form(
            step_id="form",
            data_schema=_config_schema(user_input),
            errors=errors,
        )

    async def async_step_yaml(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Create an identity from pasted YAML."""
        errors: dict[str, str] = {}
        suggested = user_input.get(CONF_YAML_CONFIG, "") if user_input else ""
        if user_input is not None:
            try:
                normalized = _parse_yaml(user_input[CONF_YAML_CONFIG])
                _validate_config(self.hass, normalized)
            except (KeyError, TypeError, ValueError, vol.Invalid):
                errors["base"] = "invalid_yaml"
            else:
                await self.async_set_unique_id(slugify(normalized[CONF_NAME]))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=normalized[CONF_NAME],
                    data=normalized,
                )

        return self.async_show_form(
            step_id="yaml",
            data_schema=_yaml_schema(suggested),
            errors=errors,
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
        _user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Choose form or YAML editing."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["form", "yaml"],
        )

    @property
    def _current(self) -> dict[str, Any]:
        return _normalize_input({**self.config_entry.data, **self.config_entry.options})

    async def async_step_form(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Edit all settings using validated selectors."""
        errors: dict[str, str] = {}
        if user_input is not None:
            normalized = _normalize_input(user_input)
            try:
                _validate_config(self.hass, normalized)
            except (KeyError, TypeError, ValueError, vol.Invalid):
                errors["base"] = "invalid_config"
            else:
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    title=normalized[CONF_NAME],
                )
                return self.async_create_entry(title="", data=normalized)

        return self.async_show_form(
            step_id="form",
            data_schema=_config_schema(user_input or self._current),
            errors=errors,
        )

    async def async_step_yaml(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Replace settings from pasted YAML."""
        errors: dict[str, str] = {}
        suggested = (
            user_input.get(CONF_YAML_CONFIG, "")
            if user_input
            else _as_yaml(self._current)
        )
        if user_input is not None:
            try:
                normalized = _parse_yaml(user_input[CONF_YAML_CONFIG])
                _validate_config(self.hass, normalized)
            except (KeyError, TypeError, ValueError, vol.Invalid):
                errors["base"] = "invalid_yaml"
            else:
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    title=normalized[CONF_NAME],
                )
                return self.async_create_entry(title="", data=normalized)

        return self.async_show_form(
            step_id="yaml",
            data_schema=_yaml_schema(suggested),
            errors=errors,
        )
