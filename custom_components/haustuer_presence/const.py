"""Constants for the Haustuer Presence integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "haustuer_presence"
PLATFORMS: Final = ["sensor", "binary_sensor", "button"]

CONF_NAME: Final = "name"
CONF_AREA_ENTITY: Final = "area_entity"
CONF_TRACKER_ENTITY: Final = "tracker_entity"
CONF_DISTANCE_ENTITIES: Final = "distance_entities"
CONF_INSIDE_AREAS: Final = "inside_areas"
CONF_DOOR_AREAS: Final = "door_areas"
CONF_CONFIRM_SECONDS: Final = "confirm_seconds"
CONF_WINDOW_SECONDS: Final = "window_seconds"
CONF_COOLDOWN_SECONDS: Final = "cooldown_seconds"
CONF_MIN_POINTS: Final = "min_points"
CONF_MAX_DISTANCE: Final = "max_distance"
CONF_MAX_PROFILE_SCORE: Final = "max_profile_score"
CONF_MIN_CONFIDENCE: Final = "min_confidence"
CONF_OBSERVE_ONLY: Final = "observe_only"
CONF_ALLOW_TRACKER_FALLBACK: Final = "allow_tracker_fallback"

DEFAULT_CONFIRM_SECONDS: Final = 1.0
DEFAULT_WINDOW_SECONDS: Final = 30
DEFAULT_COOLDOWN_SECONDS: Final = 600
DEFAULT_MIN_POINTS: Final = 2
DEFAULT_MAX_DISTANCE: Final = 30.0
DEFAULT_MAX_PROFILE_SCORE: Final = 0.5
DEFAULT_MIN_CONFIDENCE: Final = 0.2
DEFAULT_OBSERVE_ONLY: Final = True
DEFAULT_ALLOW_TRACKER_FALLBACK: Final = False

SERVICE_RECORD_SAMPLE: Final = "record_sample"
SERVICE_CLEAR_CALIBRATION: Final = "clear_calibration"
SERVICE_FORCE_ARM: Final = "force_arm"
SERVICE_RESET: Final = "reset"

EVENT_CANDIDATE: Final = f"{DOMAIN}_candidate"
EVENT_AUTHORIZED: Final = f"{DOMAIN}_authorized"

SIGNAL_UPDATE: Final = f"{DOMAIN}_update"

STORAGE_VERSION: Final = 1

CLASS_INSIDE: Final = "inside"
CLASS_OUTSIDE: Final = "outside"
CLASS_AWAY: Final = "away"
CLASS_UNKNOWN: Final = "unknown"
CALIBRATION_KINDS: Final = {
    CLASS_INSIDE,
    CLASS_OUTSIDE,
    CLASS_AWAY,
}

PHASE_IDLE: Final = "idle"
PHASE_DEPARTING: Final = "departing"
PHASE_ARMED: Final = "armed"
PHASE_ARRIVING: Final = "arriving"
PHASE_AUTHORIZED: Final = "authorized"
PHASE_COOLDOWN: Final = "cooldown"
