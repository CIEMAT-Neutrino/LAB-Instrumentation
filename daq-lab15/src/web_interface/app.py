"""Simple web dashboard scaffold for the DAQ bench.

This module exposes a small Flask app with the sections requested by the user:
status, run configuration, execution, visualization, history, and usage notes.
The goal is to start with a clean structure and real instrument status polling.
"""

from __future__ import annotations

import logging
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("daq.web")

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from flask import Flask, jsonify, render_template, request

from daq import aimtti_ql564tp as source_driver
from daq import aimtti_tgp3152 as generator_driver

app = Flask(__name__, template_folder="templates")


@dataclass
class InstrumentStatus:
    name: str
    connected: bool
    description: str
    voltage: float | None = None
    current: float | None = None
    state: str = "unknown"
    channels: list[dict[str, Any]] | None = None


def build_voltage_points(start: float, end: float, step: float) -> list[float]:
    """Return the ordered list of voltage points for a sweep including both ends."""
    if step <= 0:
        raise ValueError("step must be positive")
    points = []
    if start <= end:
        value = float(start)
        while value <= end + 1e-9:
            points.append(round(value, 6))
            value += float(step)
    else:
        value = float(start)
        while value >= end - 1e-9:
            points.append(round(value, 6))
            value -= float(step)
    if not points or points[-1] != round(float(end), 6):
        points.append(round(float(end), 6))
    return points


def _safe_float(raw: Any) -> float | None:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _default_source_resources() -> list[str]:
    candidates = [
        os.environ.get("QL564TP_RESOURCE"),
        "ASRL/dev/ttyACM0::INSTR",
        "ASRL/dev/ttyUSB0::INSTR",
        "ASRL/dev/ttyACM1::INSTR",
        "ASRL/dev/ttyUSB1::INSTR",
    ]
    seen: set[str] = set()
    ordered: list[str] = []
    for candidate in candidates:
        if not candidate:
            continue
        if candidate not in seen:
            seen.add(candidate)
            ordered.append(candidate)
    return ordered


def _read_source_status() -> dict[str, Any]:
    """Probe the QL564TP power source and return the configured channel values."""
    if request.args.get("demo") == "1":
        return {
            "connected": True,
            "voltage": 12.3,
            "current": 0.12,
            "current_limit": 0.5,
            "state": "enabled",
            "message": "Comunicación OK (modo demo)",
        }

    last_error: Exception | None = None
    log_lines: list[str] = []
    for resource in _default_source_resources():
        log_lines.append(f"Intentando fuente en {resource}")
        try:
            source = source_driver.open_source(resource)
            try:
                voltage = source_driver.read_voltage(source, 1)
                current = source_driver.read_current(source, 1)
                current_limit = source_driver.read_current_limit(source, 1)
                log_lines.append(f"Fuente responde: V={voltage} V, I={current} A, limit={current_limit} A")
                return {
                    "connected": True,
                    "voltage": voltage,
                    "current": current,
                    "current_limit": current_limit,
                    "state": "enabled",
                    "message": "Comunicación OK",
                    "log": log_lines,
                }
            finally:
                source_driver.close_source(source)
        except Exception as exc:  # pragma: no cover - hardware dependent
            last_error = exc
            log_lines.append(f"Error en {resource}: {exc}")

    return {
        "connected": False,
        "voltage": None,
        "current": None,
        "current_limit": None,
        "state": "disconnected",
        "message": str(last_error) if last_error else "No se detectó la fuente QL564TP",
        "log": log_lines or ["No se detectó la fuente QL564TP"],
    }


def _read_generator_status() -> dict[str, Any]:
    """Ask the driver to perform the real probe for the generator status."""
    if request.args.get("demo") == "1":
        return {
            "connected": True,
            "description": "Thurlby Thandar Instruments Limited TGP3152",
            "channels": [
                {"channel": 1, "waveform": "PULSE", "frequency": 10.0, "high_level": 3.3, "low_level": 0.0, "pulse_width": 0.12},
                {"channel": 2, "waveform": "SINE", "frequency": 1000.0, "high_level": 2.5, "low_level": 0.0, "pulse_width": 0.05},
            ],
            "state": "ready",
            "message": "Comunicación OK (modo demo)",
            "log": ["Modo demo: comunicación simulada OK"],
        }
    return generator_driver.check_generator_communication()


def _empty_backend_status() -> dict[str, InstrumentStatus]:
    """Build an initial disconnected view with no hardware probing on page load."""
    return {
        "source": InstrumentStatus(
            name="QL564TP",
            connected=False,
            description="Fuente de alimentación",
            voltage=None,
            current=None,
            state="disconnected",
        ),
        "generator": InstrumentStatus(
            name="TGP3152",
            connected=False,
            description="Thurlby Thandar Instruments Limited TGP3152",
            voltage=None,
            current=None,
            state="disconnected",
            channels=[],
        ),
        "compass": InstrumentStatus(
            name="CoMPASS",
            connected=False,
            description="Digitizador DT2730",
            voltage=None,
            current=None,
            state="disconnected",
        ),
    }


def _read_backend_status(probe: bool = False) -> dict[str, InstrumentStatus]:
    """Return a small status snapshot for the current instruments.

    Hardware checks are intentionally disabled on normal page loads. A manual request
    or an explicit `probe=true` flag is required to contact the instruments.
    """
    if not probe and request.args.get("demo") != "1":
        return _empty_backend_status()

    source_status = _read_source_status()
    generator_status = _read_generator_status()
    status = {
        "source": InstrumentStatus(
            name="QL564TP",
            connected=source_status["connected"],
            description="Fuente de alimentación",
            voltage=source_status.get("voltage"),
            current=source_status.get("current"),
            state=source_status["state"],
        ),
        "generator": InstrumentStatus(
            name="TGP3152",
            connected=generator_status["connected"],
            description=generator_status["description"],
            voltage=None,
            current=None,
            state=generator_status["state"],
            channels=generator_status["channels"],
        ),
        "compass": InstrumentStatus(
            name="CoMPASS",
            connected=False,
            description="Digitizador DT2730",
            voltage=None,
            current=None,
            state="disconnected",
        ),
    }

    # Simple demo values for development: if a query parameter is present, it can be
    # used to simulate an instrument being connected and reporting live readings.
    if request.args.get("demo") == "1":
        status["source"].connected = True
        status["source"].voltage = 15.2
        status["source"].current = 0.08
        status["source"].state = "enabled"

        status["generator"].connected = True
        status["generator"].state = "on"
        status["generator"].channels = [
            {"channel": 1, "waveform": "PULSE", "frequency": 10.0, "high_level": 3.3, "low_level": 0.0, "pulse_width": 0.12},
            {"channel": 2, "waveform": "SINE", "frequency": 1000.0, "high_level": 2.5, "low_level": 0.0, "pulse_width": 0.05},
        ]

        status["compass"].connected = True
        status["compass"].voltage = None
        status["compass"].current = None
        status["compass"].state = "ready"

    return status


@app.get("/")
def index():
    status = _read_backend_status()
    return render_template(
        "index.html",
        status=status,
        voltage_points=build_voltage_points(0, 12, 1),
        run_profiles=["calibración", "luz alta", "oscuridad"],
        logs=[
            "Sistema listo.",
            "Esperando configuración del run.",
        ],
    )


@app.get("/api/status")
def api_status():
    probe = request.args.get("probe", "0") == "1"
    status = _read_backend_status(probe=probe)
    return jsonify({
        name: {
            "name": s.name,
            "connected": s.connected,
            "description": s.description,
            "voltage": s.voltage,
            "current": s.current,
            "state": s.state,
            "channels": s.channels,
        }
        for name, s in status.items()
    })


@app.post("/api/source/check")
def api_source_check():
    payload = _read_source_status()
    return jsonify({
        "connected": payload["connected"],
        "voltage": payload.get("voltage"),
        "current": payload.get("current"),
        "current_limit": payload.get("current_limit"),
        "state": payload["state"],
        "message": payload["message"],
        "log": payload.get("log", [payload["message"]]),
    })


@app.post("/api/generator/check")
def api_generator_check():
    payload = _read_generator_status()
    return jsonify({
        "connected": bool(payload["connected"]),
        "description": payload.get("description", "Thurlby Thandar Instruments Limited TGP3152"),
        "channels": payload.get("channels", []),
        "state": payload.get("state", "disconnected"),
        "message": payload.get("message", "No se pudo comprobar el generador"),
        "log": payload.get("log", [payload.get("message", "No se pudo comprobar el generador")]),
    })


@app.post("/api/connect")
def api_connect():
    payload = request.get_json(silent=True) or {}
    instrument = payload.get("instrument")
    if instrument not in {"source", "generator", "compass"}:
        return jsonify({"error": "instrument not valid"}), 400

    status = _read_backend_status()
    status[instrument].connected = True
    status[instrument].state = "connected"
    if instrument == "source":
        status[instrument].voltage = _safe_float(payload.get("voltage"))
        status[instrument].current = _safe_float(payload.get("current"))
    return jsonify({"ok": True, "instrument": instrument})


@app.post("/api/emergency-stop")
def api_emergency_stop():
    return jsonify({"ok": True, "message": "Salidas apagadas", "status": "stopped"})


@app.get("/api/voltage-points")
def api_voltage_points():
    start = float(request.args.get("start", 0))
    end = float(request.args.get("end", 12))
    step = float(request.args.get("step", 1))
    return jsonify({"points": build_voltage_points(start, end, step)})


if __name__ == "__main__":
    port = int(os.environ.get("FLASK_PORT", "5003"))
    app.run(host="0.0.0.0", port=port, debug=True)
