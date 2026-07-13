"""Event-driven presence classifier and per-person state machine."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_NOT_HOME, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import (
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later, async_track_state_change_event
from homeassistant.helpers.storage import Store

from .calibration import CalibrationModel, Classification
from .const import (
    CLASS_AWAY,
    CLASS_INSIDE,
    CLASS_OUTSIDE,
    CLASS_UNKNOWN,
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
    EVENT_AUTHORIZED,
    EVENT_CANDIDATE,
    PHASE_ARMED,
    PHASE_ARRIVING,
    PHASE_AUTHORIZED,
    PHASE_COOLDOWN,
    PHASE_DEPARTING,
    PHASE_IDLE,
    SIGNAL_UPDATE,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)


class PresenceManager:
    """Classify measurements and track one person's movement."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the manager."""
        self.hass = hass
        self.entry = entry
        self.settings = {**entry.data, **entry.options}
        self.name: str = self.settings[CONF_NAME]
        self.phase = PHASE_IDLE
        self.classification = Classification(
            kind=CLASS_UNKNOWN,
            profile=None,
            confidence=0.0,
            score=None,
            points_used=0,
        )
        self.distances: dict[str, float] = {}
        self.last_reason = "initialized"
        self.last_area: str | None = None
        self.candidate = False
        self.authorized = False
        self._confirm_cancel: Callable[[], None] | None = None
        self._window_cancel: Callable[[], None] | None = None
        self._cooldown_cancel: Callable[[], None] | None = None
        self._store: Store[dict[str, Any]] = Store(
            hass,
            STORAGE_VERSION,
            f"{DOMAIN}.{entry.entry_id}",
        )
        self.calibration = CalibrationModel()

    @property
    def observe_only(self) -> bool:
        """Return whether the manager is prevented from authorizing."""
        return bool(self.settings.get(CONF_OBSERVE_ONLY, DEFAULT_OBSERVE_ONLY))

    @property
    def monitored_entities(self) -> list[str]:
        """Return entities whose state changes affect classification."""
        entities = list(self.settings.get(CONF_DISTANCE_ENTITIES, []))
        for key in (CONF_AREA_ENTITY, CONF_TRACKER_ENTITY):
            if entity_id := self.settings.get(key):
                entities.append(entity_id)
        return list(dict.fromkeys(entities))

    async def async_start(self) -> None:
        """Load calibration and subscribe to entity state changes."""
        self.calibration = CalibrationModel.from_dict(await self._store.async_load())
        if area_entity := self.settings.get(CONF_AREA_ENTITY):
            state = self.hass.states.get(area_entity)
            self.last_area = self._area_key(state)

        self.entry.async_on_unload(
            async_track_state_change_event(
                self.hass,
                self.monitored_entities,
                self._async_state_changed,
            )
        )
        await self.async_evaluate("startup")

    async def async_stop(self) -> None:
        """Cancel pending callbacks."""
        self._cancel_confirm()
        self._cancel_window()
        self._cancel_cooldown()

    @callback
    def _async_state_changed(
        self,
        event: Event[EventStateChangedData],
    ) -> None:
        """Handle one monitored entity changing."""
        entity_id = event.data["entity_id"]
        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")
        if new_state is None:
            return

        if entity_id == self.settings.get(CONF_AREA_ENTITY):
            self._handle_area_transition(old_state, new_state)
        self.hass.async_create_task(self.async_evaluate(f"state_changed:{entity_id}"))

    @staticmethod
    def _area_key(state: State | None) -> str | None:
        """Return the stable HA area ID exposed by Bermuda."""
        if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return None
        return state.attributes.get("area_id") or state.state

    @callback
    def _handle_area_transition(
        self,
        old_state: State | None,
        new_state: State,
    ) -> None:
        """Arm the departure sequence from a clear inside-to-door transition."""
        old_area = self._area_key(old_state)
        new_area = self._area_key(new_state)
        self.last_area = new_area
        inside_areas = set(self.settings.get(CONF_INSIDE_AREAS, []))
        door_areas = set(self.settings.get(CONF_DOOR_AREAS, []))
        if old_area in inside_areas and new_area in door_areas:
            self._set_phase(PHASE_DEPARTING, "inside_to_door_transition")

    async def async_evaluate(self, reason: str) -> None:
        """Evaluate current states and advance the state machine."""
        self.distances = self._read_distances()
        self.classification = self.calibration.classify(
            self.distances,
            min_points=int(self.settings.get(CONF_MIN_POINTS, DEFAULT_MIN_POINTS)),
            max_distance=float(
                self.settings.get(CONF_MAX_DISTANCE, DEFAULT_MAX_DISTANCE)
            ),
            max_score=float(
                self.settings.get(
                    CONF_MAX_PROFILE_SCORE,
                    DEFAULT_MAX_PROFILE_SCORE,
                )
            ),
        )
        tracker_state = self._tracker_state()
        area_state = self._area_state()

        effective_kind = self._effective_classification_kind()
        if effective_kind == CLASS_UNKNOWN and area_state in set(
            self.settings.get(CONF_INSIDE_AREAS, [])
        ):
            effective_kind = CLASS_INSIDE
        if effective_kind == CLASS_UNKNOWN and tracker_state == STATE_NOT_HOME:
            effective_kind = CLASS_AWAY

        if (
            tracker_state == STATE_NOT_HOME
            and self.settings.get(
                CONF_ALLOW_TRACKER_FALLBACK,
                DEFAULT_ALLOW_TRACKER_FALLBACK,
            )
            and self.phase == PHASE_IDLE
        ):
            self._set_phase(PHASE_ARMED, "tracker_fallback_not_home")

        if self.phase == PHASE_DEPARTING and (
            effective_kind == CLASS_AWAY or tracker_state == STATE_NOT_HOME
        ):
            self._set_phase(PHASE_ARMED, "departure_confirmed")

        if self.phase == PHASE_ARMED and effective_kind == CLASS_OUTSIDE:
            self._start_candidate(reason)
        elif self.phase in (PHASE_ARRIVING, PHASE_AUTHORIZED):
            if effective_kind == CLASS_INSIDE:
                self._reset_runtime("entered_inside")
            elif effective_kind != CLASS_OUTSIDE and not self.authorized:
                self._cancel_candidate("outside_candidate_lost")

        self.last_reason = reason
        self._notify_entities()

    def _read_distances(self) -> dict[str, float]:
        """Read valid numeric states from configured measurement points."""
        values: dict[str, float] = {}
        max_distance = float(self.settings.get(CONF_MAX_DISTANCE, DEFAULT_MAX_DISTANCE))
        for entity_id in self.settings.get(CONF_DISTANCE_ENTITIES, []):
            state = self.hass.states.get(entity_id)
            if state is None or state.state in (
                STATE_UNKNOWN,
                STATE_UNAVAILABLE,
            ):
                continue
            try:
                value = float(state.state)
            except (TypeError, ValueError):
                continue
            if value < 0:
                continue
            values[entity_id] = min(value, max_distance)
        return values

    def _tracker_state(self) -> str | None:
        """Return the optional tracker state."""
        entity_id = self.settings.get(CONF_TRACKER_ENTITY)
        state = self.hass.states.get(entity_id) if entity_id else None
        return state.state if state is not None else None

    def _area_state(self) -> str | None:
        """Return the optional area sensor state."""
        entity_id = self.settings.get(CONF_AREA_ENTITY)
        state = self.hass.states.get(entity_id) if entity_id else None
        return self._area_key(state)

    def _effective_classification_kind(self) -> str:
        """Reject classifications whose confidence is below the safety floor."""
        if self.classification.confidence < float(
            self.settings.get(
                CONF_MIN_CONFIDENCE,
                DEFAULT_MIN_CONFIDENCE,
            )
        ):
            return CLASS_UNKNOWN
        return self.classification.kind

    @callback
    def _start_candidate(self, reason: str) -> None:
        """Start the configured confirmation delay."""
        if self._confirm_cancel is not None:
            return
        self.candidate = True
        self._set_phase(PHASE_ARRIVING, f"outside_candidate:{reason}")
        self.hass.bus.async_fire(EVENT_CANDIDATE, self.event_data)
        self._confirm_cancel = async_call_later(
            self.hass,
            float(
                self.settings.get(
                    CONF_CONFIRM_SECONDS,
                    DEFAULT_CONFIRM_SECONDS,
                )
            ),
            self._async_confirm_candidate,
        )

    async def _async_confirm_candidate(self, _now: datetime) -> None:
        """Re-evaluate and authorize a stable outside candidate."""
        self._confirm_cancel = None
        self.distances = self._read_distances()
        self.classification = self.calibration.classify(
            self.distances,
            min_points=int(self.settings.get(CONF_MIN_POINTS, DEFAULT_MIN_POINTS)),
            max_distance=float(
                self.settings.get(CONF_MAX_DISTANCE, DEFAULT_MAX_DISTANCE)
            ),
            max_score=float(
                self.settings.get(
                    CONF_MAX_PROFILE_SCORE,
                    DEFAULT_MAX_PROFILE_SCORE,
                )
            ),
        )
        if self._effective_classification_kind() != CLASS_OUTSIDE:
            self._cancel_candidate("confirmation_failed")
            return

        self.candidate = True
        self.authorized = not self.observe_only
        self._set_phase(
            PHASE_AUTHORIZED if self.authorized else PHASE_ARRIVING,
            "outside_confirmed",
        )
        self.hass.bus.async_fire(
            EVENT_AUTHORIZED if self.authorized else EVENT_CANDIDATE,
            {**self.event_data, "confirmed": True},
        )
        self._window_cancel = async_call_later(
            self.hass,
            int(
                self.settings.get(
                    CONF_WINDOW_SECONDS,
                    DEFAULT_WINDOW_SECONDS,
                )
            ),
            self._async_end_window,
        )
        self._notify_entities()

    async def _async_end_window(self, _now: datetime) -> None:
        """End a candidate or authorization window."""
        self._window_cancel = None
        self.candidate = False
        self.authorized = False
        self._set_phase(PHASE_COOLDOWN, "window_finished")
        self._cooldown_cancel = async_call_later(
            self.hass,
            int(
                self.settings.get(
                    CONF_COOLDOWN_SECONDS,
                    DEFAULT_COOLDOWN_SECONDS,
                )
            ),
            self._async_end_cooldown,
        )

    async def _async_end_cooldown(self, _now: datetime) -> None:
        """Return to idle after cooldown."""
        self._cooldown_cancel = None
        self._set_phase(PHASE_IDLE, "cooldown_finished")

    @callback
    def _cancel_candidate(self, reason: str) -> None:
        """Cancel a not-yet-confirmed candidate."""
        self._cancel_confirm()
        self.candidate = False
        self.authorized = False
        self._set_phase(PHASE_ARMED, reason)

    @callback
    def _reset_runtime(self, reason: str) -> None:
        """Safely reset all transient state."""
        self._cancel_confirm()
        self._cancel_window()
        self._cancel_cooldown()
        self.candidate = False
        self.authorized = False
        self._set_phase(PHASE_IDLE, reason)

    @callback
    def _cancel_confirm(self) -> None:
        if self._confirm_cancel is not None:
            self._confirm_cancel()
            self._confirm_cancel = None

    @callback
    def _cancel_window(self) -> None:
        if self._window_cancel is not None:
            self._window_cancel()
            self._window_cancel = None

    @callback
    def _cancel_cooldown(self) -> None:
        if self._cooldown_cancel is not None:
            self._cooldown_cancel()
            self._cooldown_cancel = None

    @callback
    def _set_phase(self, phase: str, reason: str) -> None:
        self.phase = phase
        self.last_reason = reason
        self._notify_entities()

    @callback
    def _notify_entities(self) -> None:
        async_dispatcher_send(
            self.hass,
            f"{SIGNAL_UPDATE}_{self.entry.entry_id}",
        )

    @property
    def event_data(self) -> dict[str, Any]:
        """Return stable event payload and diagnostic context."""
        return {
            "entry_id": self.entry.entry_id,
            "name": self.name,
            "phase": self.phase,
            "classification": self.classification.kind,
            "profile": self.classification.profile,
            "confidence": self.classification.confidence,
            "distances": self.distances,
            "observe_only": self.observe_only,
        }

    async def async_record_sample(
        self,
        profile_name: str,
        kind: str,
    ) -> int:
        """Capture current measurements into a calibration profile."""
        values = self._read_distances()
        count = self.calibration.add_sample(profile_name, kind, values)
        await self._store.async_save(self.calibration.as_dict())
        await self.async_evaluate(f"calibration_recorded:{profile_name}")
        return count

    async def async_clear_calibration(
        self,
        profile_name: str | None = None,
    ) -> None:
        """Clear calibration data."""
        self.calibration.clear(profile_name)
        await self._store.async_save(self.calibration.as_dict())
        await self.async_evaluate("calibration_cleared")

    async def async_force_arm(self) -> None:
        """Force the next outside classification to be considered an arrival."""
        self._set_phase(PHASE_ARMED, "force_arm_service")
        await self.async_evaluate("force_arm_service")

    async def async_reset(self) -> None:
        """Reset transient state without removing calibration."""
        self._reset_runtime("reset_service")
