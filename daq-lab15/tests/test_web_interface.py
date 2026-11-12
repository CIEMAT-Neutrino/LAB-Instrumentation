import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src" / "data_visualization") not in sys.path:
    sys.path.insert(0, str(ROOT / "src" / "data_visualization"))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from web_interface.app import _item_group, app, build_voltage_points


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


def test_runs_lists_runs_with_raw_files():
    client = app.test_client()
    payload = client.get("/api/runs").get_json()
    for run in payload["runs"]:
        assert run["files"], run
        assert not run["id"].startswith("/") and ".." not in run["id"]


def test_run_plot_rejects_bad_requests():
    client = app.test_client()
    assert client.get("/api/run-plot?run=../../etc&kind=waveform").status_code == 404
    assert client.get("/api/run-plot?run=x&kind=nope").status_code == 400


def test_each_channel_gets_a_separate_subplot():
    import numpy as np
    import quickdisplay

    channel_paths = [Path("DataR_CH0.BIN"), Path("DataR_CH1.BIN")]
    items = []
    for path in channel_paths:
        group, color_idx = _item_group(path)
        items.append({
            "group": group,
            "name": quickdisplay.channel_label(path),
            "color_idx": color_idx,
            "mean": np.array([0.0, 1.0]),
            "std": np.array([0.0, 0.0]),
            "energies": np.array([10, 20], dtype=np.uint16),
            "n_bins": 2,
        })

    figures = [
        quickdisplay.waveform_figure(items),
        quickdisplay.histogram_figure(items),
    ]
    for figure in figures:
        axes = {trace.xaxis for trace in figure.data}
        assert len(axes) == len(channel_paths)
        domains = sorted(
            getattr(figure.layout, f"xaxis{axis[1:]}").domain for axis in axes
        )
        assert all(left[1] <= right[0] for left, right in zip(domains, domains[1:]))


def test_find_spe_window_picks_second_peak():
    import numpy as np
    import quickdisplay

    rng = np.random.default_rng(0)
    energies = np.concatenate([
        rng.normal(10, 1.5, 20000),   # pedestal
        rng.normal(22, 2.0, 15000),   # SPE
        rng.normal(35, 2.5, 6000),    # 2 p.e.
    ]).round().clip(0).astype(np.uint16)
    window = quickdisplay.find_spe_window(energies)
    assert window is not None
    assert 14 <= window["lo"] <= 17 and 27 <= window["hi"] <= 30
    assert abs(window["spe"] - 22) <= 1.5


def test_find_spe_window_returns_none_without_peaks():
    import numpy as np
    import quickdisplay

    assert quickdisplay.find_spe_window(np.zeros(5000, dtype=np.uint16)) is None
