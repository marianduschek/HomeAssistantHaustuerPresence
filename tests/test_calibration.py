"""Tests for the dependency-free calibration model."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).parents[1]
PACKAGE = "custom_components.haustuer_presence"


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
    str(ROOT / "custom_components" / "haustuer_presence")
]
sys.modules.setdefault(PACKAGE, integration_package)

_load_module(
    f"{PACKAGE}.const",
    ROOT / "custom_components" / "haustuer_presence" / "const.py",
)
calibration = _load_module(
    f"{PACKAGE}.calibration",
    ROOT / "custom_components" / "haustuer_presence" / "calibration.py",
)

CalibrationModel = calibration.CalibrationModel


def _trained_model():
    model = CalibrationModel()
    model.add_sample(
        "WE2 Windfang",
        "inside",
        {"door": 4.0, "flur": 8.0, "we2": 1.5},
    )
    model.add_sample(
        "WE2 Windfang",
        "inside",
        {"door": 4.5, "flur": 7.5, "we2": 1.8},
    )
    model.add_sample(
        "Außen vor Tür",
        "outside",
        {"door": 2.0, "flur": 12.0, "we2": 14.0},
    )
    model.add_sample(
        "Außen vor Tür",
        "outside",
        {"door": 2.4, "flur": 13.0, "we2": 15.0},
    )
    model.add_sample(
        "Abwesend",
        "away",
        {"door": 30.0, "flur": 30.0, "we2": 30.0},
    )
    return model


def test_classifies_outside_against_three_points() -> None:
    model = _trained_model()

    result = model.classify(
        {"door": 2.2, "flur": 12.5, "we2": 14.4},
        min_points=2,
        max_distance=30,
    )

    assert result.kind == "outside"
    assert result.profile == "Außen vor Tür"
    assert result.points_used == 3
    assert result.confidence > 0.5


def test_new_inside_reference_disambiguates_we2() -> None:
    model = _trained_model()

    result = model.classify(
        {"door": 3.8, "flur": 9.0, "we2": 1.6},
        min_points=2,
        max_distance=30,
    )

    assert result.kind == "inside"
    assert result.profile == "WE2 Windfang"


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
        {"door": 20.0, "flur": 1.0, "we2": 20.0},
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
        {"door": 2.2, "flur": 12.0, "we2": 14.0},
        min_points=2,
        max_distance=30,
    )
    assert result.kind == "outside"


def test_profile_kind_cannot_change_accidentally() -> None:
    model = CalibrationModel()
    model.add_sample("Tür", "inside", {"door": 1.0})

    try:
        model.add_sample("Tür", "outside", {"door": 2.0})
    except ValueError as err:
        assert "already belongs" in str(err)
    else:
        raise AssertionError("Expected profile kind mismatch to fail")
