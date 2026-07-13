"""Tests for the dependency-free calibration model."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).parents[1]
PACKAGE = "custom_components.doorstep_presence"


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


custom_components = ModuleType("custom_components")
custom_components.__path__ = []  # type: ignore[attr-defined]
sys.modules.setdefault("custom_components", custom_components)

integration_package = ModuleType(PACKAGE)
integration_package.__path__ = [  # type: ignore[attr-defined]
    str(ROOT / "custom_components" / "doorstep_presence")
]
sys.modules.setdefault(PACKAGE, integration_package)

_load_module(
    f"{PACKAGE}.const",
    ROOT / "custom_components" / "doorstep_presence" / "const.py",
)
calibration = _load_module(
    f"{PACKAGE}.calibration",
    ROOT / "custom_components" / "doorstep_presence" / "calibration.py",
)

CalibrationModel = calibration.CalibrationModel


def _trained_model():
    model = CalibrationModel()
    model.add_sample(
        "Vestibule",
        "inside",
        {"door": 4.0, "hall": 8.0, "side": 1.5},
    )
    model.add_sample(
        "Vestibule",
        "inside",
        {"door": 4.5, "hall": 7.5, "side": 1.8},
    )
    model.add_sample(
        "Outside doorstep",
        "outside",
        {"door": 2.0, "hall": 12.0, "side": 14.0},
    )
    model.add_sample(
        "Outside doorstep",
        "outside",
        {"door": 2.4, "hall": 13.0, "side": 15.0},
    )
    model.add_sample(
        "Away",
        "away",
        {"door": 30.0, "hall": 30.0, "side": 30.0},
    )
    return model


def test_classifies_outside_against_three_points() -> None:
    model = _trained_model()

    result = model.classify(
        {"door": 2.2, "hall": 12.5, "side": 14.4},
        min_points=2,
        max_distance=30,
    )

    assert result.kind == "outside"
    assert result.profile == "Outside doorstep"
    assert result.points_used == 3
    assert result.confidence > 0.5


def test_new_inside_reference_disambiguates_vestibule() -> None:
    model = _trained_model()

    result = model.classify(
        {"door": 3.8, "hall": 9.0, "side": 1.6},
        min_points=2,
        max_distance=30,
    )

    assert result.kind == "inside"
    assert result.profile == "Vestibule"


def test_requires_configured_minimum_available_points() -> None:
    model = _trained_model()

    result = model.classify(
        {"door": 2.1},
        min_points=2,
        max_distance=30,
    )

    assert result.kind == "unknown"
    assert result.points_used == 0


def test_rejects_location_far_from_every_profile() -> None:
    model = _trained_model()

    result = model.classify(
        {"door": 20.0, "hall": 1.0, "side": 20.0},
        min_points=2,
        max_distance=30,
        max_score=0.3,
    )

    assert result.kind == "unknown"
    assert result.score is not None


def test_round_trip_preserves_profiles_and_samples() -> None:
    original = _trained_model()

    restored = CalibrationModel.from_dict(original.as_dict())

    assert restored.sample_counts() == original.sample_counts()
    result = restored.classify(
        {"door": 2.2, "hall": 12.0, "side": 14.0},
        min_points=2,
        max_distance=30,
    )
    assert result.kind == "outside"


def test_profile_kind_cannot_change_accidentally() -> None:
    model = CalibrationModel()
    model.add_sample("Door", "inside", {"door": 1.0})

    try:
        model.add_sample("Door", "outside", {"door": 2.0})
    except ValueError as err:
        assert "already belongs" in str(err)
    else:
        raise AssertionError("Expected profile kind mismatch to fail")
