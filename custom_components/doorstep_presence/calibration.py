"""Calibration model and distance-vector classifier."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from math import log1p
from statistics import median
from typing import Any

from .const import CALIBRATION_KINDS, CLASS_UNKNOWN


@dataclass(slots=True, frozen=True)
class Classification:
    """Result returned by the calibration model."""

    kind: str
    profile: str | None
    confidence: float
    score: float | None
    points_used: int


@dataclass(slots=True)
class CalibrationSample:
    """One captured set of simultaneous proxy distances."""

    values: dict[str, float]
    captured_at: str

    @classmethod
    def create(cls, values: dict[str, float]) -> CalibrationSample:
        """Create a timestamped sample."""
        return cls(values=values, captured_at=datetime.now(UTC).isoformat())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CalibrationSample:
        """Deserialize a sample."""
        return cls(
            values={
                str(entity_id): float(value)
                for entity_id, value in data.get("values", {}).items()
            },
            captured_at=str(data.get("captured_at", "")),
        )

    def as_dict(self) -> dict[str, Any]:
        """Serialize a sample."""
        return {"values": self.values, "captured_at": self.captured_at}


@dataclass(slots=True)
class CalibrationProfile:
    """Named calibration location belonging to a broad class."""

    name: str
    kind: str
    samples: list[CalibrationSample] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CalibrationProfile:
        """Deserialize a profile."""
        return cls(
            name=str(data["name"]),
            kind=str(data["kind"]),
            samples=[
                CalibrationSample.from_dict(sample)
                for sample in data.get("samples", [])
            ],
        )

    def as_dict(self) -> dict[str, Any]:
        """Serialize a profile."""
        return {
            "name": self.name,
            "kind": self.kind,
            "samples": [sample.as_dict() for sample in self.samples],
        }

    def centroid(self) -> dict[str, float]:
        """Return the median distance for each measurement point."""
        entity_ids = {
            entity_id for sample in self.samples for entity_id in sample.values
        }
        return {
            entity_id: median(
                sample.values[entity_id]
                for sample in self.samples
                if entity_id in sample.values
            )
            for entity_id in entity_ids
        }


@dataclass(slots=True)
class CalibrationModel:
    """Collection of profiles used for nearest-profile classification."""

    profiles: dict[str, CalibrationProfile] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> CalibrationModel:
        """Deserialize the complete calibration model."""
        if not data:
            return cls()
        return cls(
            profiles={
                profile_data["name"]: CalibrationProfile.from_dict(profile_data)
                for profile_data in data.get("profiles", [])
            }
        )

    def as_dict(self) -> dict[str, Any]:
        """Serialize the complete calibration model."""
        return {
            "profiles": [
                profile.as_dict()
                for profile in sorted(
                    self.profiles.values(), key=lambda item: item.name
                )
            ]
        }

    def add_sample(
        self,
        profile_name: str,
        kind: str,
        values: dict[str, float],
    ) -> int:
        """Add a sample and return the profile's new sample count."""
        normalized_name = profile_name.strip()
        if not normalized_name:
            raise ValueError("profile_name must not be empty")
        if kind not in CALIBRATION_KINDS:
            raise ValueError(f"Unsupported calibration kind: {kind}")
        if not values:
            raise ValueError("No valid measurement values available")

        profile = self.profiles.get(normalized_name)
        if profile is None:
            profile = CalibrationProfile(name=normalized_name, kind=kind)
            self.profiles[normalized_name] = profile
        elif profile.kind != kind:
            raise ValueError(
                f"Profile {normalized_name!r} already belongs to {profile.kind!r}"
            )

        profile.samples.append(CalibrationSample.create(values))
        profile.samples[:] = profile.samples[-100:]
        return len(profile.samples)

    def clear(self, profile_name: str | None = None) -> None:
        """Clear one profile or the full calibration."""
        if profile_name is None:
            self.profiles.clear()
            return
        self.profiles.pop(profile_name, None)

    def sample_counts(self) -> dict[str, int]:
        """Return sample counts keyed by profile."""
        return {
            profile.name: len(profile.samples) for profile in self.profiles.values()
        }

    def classify(
        self,
        values: dict[str, float],
        *,
        min_points: int,
        max_distance: float,
        max_score: float | None = None,
    ) -> Classification:
        """Classify a current distance vector against calibrated profiles."""
        candidates: list[tuple[float, int, CalibrationProfile]] = []

        for profile in self.profiles.values():
            if not profile.samples:
                continue
            centroid = profile.centroid()
            common = set(values) & set(centroid)
            if len(common) < min_points:
                continue

            differences = [
                abs(
                    log1p(min(values[entity_id], max_distance))
                    - log1p(min(centroid[entity_id], max_distance))
                )
                for entity_id in common
            ]
            candidates.append(
                (sum(differences) / len(differences), len(common), profile)
            )

        if not candidates:
            return Classification(
                kind=CLASS_UNKNOWN,
                profile=None,
                confidence=0.0,
                score=None,
                points_used=0,
            )

        candidates.sort(key=lambda item: item[0])
        best_score, points_used, best_profile = candidates[0]
        if max_score is not None and best_score > max_score:
            return Classification(
                kind=CLASS_UNKNOWN,
                profile=None,
                confidence=0.0,
                score=round(best_score, 4),
                points_used=points_used,
            )

        competing_score = next(
            (
                score
                for score, _points, profile in candidates[1:]
                if profile.kind != best_profile.kind
            ),
            None,
        )
        if competing_score is None:
            confidence = 1.0 / (1.0 + best_score)
        else:
            confidence = max(
                0.0,
                min(
                    1.0,
                    (competing_score - best_score) / (competing_score + 0.05),
                ),
            )

        return Classification(
            kind=best_profile.kind,
            profile=best_profile.name,
            confidence=round(confidence, 3),
            score=round(best_score, 4),
            points_used=points_used,
        )
