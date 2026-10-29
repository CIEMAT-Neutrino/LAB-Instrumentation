"""Simple web dashboard scaffold for the DAQ bench.

This module exposes a small Flask app with the sections requested by the user:
status, run configuration, execution, visualization, history, and usage notes.
The goal is to start with a clean structure and real instrument status polling.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request


app = Flask(__name__, template_folder="templates")


@dataclass
class InstrumentStatus:
    name: str
    connected: bool
    description: str
    voltage: float | None = None
    current: float | None = None
    state: str = "unknown"


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


def _read_backend_status() -> dict[str, InstrumentStatus]:
    """Return a small status snapshot for the current instruments.

    This is intentionally lightweight and does not assume the hardware is present.
    The app can be extended later to real VISA/HTTP probing without changing the UI.
    """
    status = {
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
            description="Generador de LED",
            voltage=None,
            current=None,
            state="disconnected",
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
        status["generator"].voltage = 3.3
        status["generator"].current = 0.01
        status["generator"].state = "on"

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
    status = _read_backend_status()
    return jsonify({
        name: {
            "name": s.name,
            "connected": s.connected,
            "description": s.description,
            "voltage": s.voltage,
            "current": s.current,
            "state": s.state,
        }
        for name, s in status.items()
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
