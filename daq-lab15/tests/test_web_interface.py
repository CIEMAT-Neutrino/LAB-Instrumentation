import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from web_interface.app import app, build_voltage_points


def test_build_voltage_points_includes_end_and_step():
    points = build_voltage_points(0, 10, 2.5)
    assert points == [0.0, 2.5, 5.0, 7.5, 10.0]


def test_build_voltage_points_handles_reversed_range():
    points = build_voltage_points(10, 0, 2.5)
    assert points == [10.0, 7.5, 5.0, 2.5, 0.0]


def test_generator_check_reads_configuration():
    client = app.test_client()
    mocked_status = {
        "connected": True,
        "description": "Thurlby Thandar Instruments Limited TGP3152",
        "channels": [
            {"channel": 1, "waveform": "PULSE", "frequency": 10.0, "high_level": 3.3, "low_level": 0.0, "pulse_width": 0.12},
            {"channel": 2, "waveform": "SINE", "frequency": 1000.0, "high_level": 2.5, "low_level": 0.0, "pulse_width": 0.05},
        ],
        "state": "ready",
        "message": "Comunicación OK",
    }

    with patch("web_interface.app._read_generator_status", return_value=mocked_status):
        response = client.post("/api/generator/check")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["connected"] is True
    assert payload["channels"][0]["waveform"] == "PULSE"
    assert payload["channels"][0]["frequency"] == 10.0
    assert payload["channels"][0]["high_level"] == 3.3
    assert payload["channels"][0]["low_level"] == 0.0
    assert payload["channels"][0]["pulse_width"] == 0.12
