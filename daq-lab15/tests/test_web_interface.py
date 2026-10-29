import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from web_interface.app import build_voltage_points


def test_build_voltage_points_includes_end_and_step():
    points = build_voltage_points(0, 10, 2.5)
    assert points == [0.0, 2.5, 5.0, 7.5, 10.0]


def test_build_voltage_points_handles_reversed_range():
    points = build_voltage_points(10, 0, 2.5)
    assert points == [10.0, 7.5, 5.0, 2.5, 0.0]
