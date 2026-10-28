# daq-lab15

Automatic data acquisition (DAQ) system for characterizing the X-ARAPUCA light sensors for the DUNE project at CIEMAT's new cryogenics laboratory. It orchestrates the bench instruments from Python so that calibration and measurement runs can be executed unattended, with one CoMPASS acquisition per setting.

> **Status:** work in progress. See [Project status](#project-status).

## Overview

The setup is made of three instruments, all controlled from a single Python program:

| Role | Instrument | Interface |
|------|------------|-----------|
| Digitizer (waveforms and charge information) | CAEN DT2730, DPP-PSD firmware, operated through CAEN CoMPASS | CoMPASS remote control over HTTP (port 8080) |
| Sensor power supply | AIM-TTI QL564TP | USB (virtual serial port, fixed 19200 baud) |
| LED signal generator (sets the light level) | AIM-TTI TGP3152 | USB |

> The LED signal generator was originally a Keysight 33600A (controlled with PyVISA over USB). It has been replaced by the TGP3152; the Keysight driver is kept in the repository for reference.

## Run types

1. **Calibration run.** Fixed LED drive level from the signal generator, sweep of the sensor supply voltage. One CoMPASS acquisition is taken at each voltage step.
2. **High-light run.** Same procedure as the calibration run, but with a higher LED drive level.
3. **Dark-current run.** Signal acquisition with the XA voltage off and measurement of the dark count rate.

## Repository layout

```
daq-lab15/
├── requirements.txt
├── pyproject.toml          # package metadata
├── README.md
├── .gitignore
├── src/
│   ├── daq/
│   │   ├── keysight_33600a.py     # Keysight 33600A driver (legacy LED generator)
│   │   ├── aimtti_ql564tp.py      # sensor power supply driver
│   │   ├── aimtti_tgp3152.py      # LED signal generator driver
│   │   └── caen_dt2730.py         # CoMPASS / DT2730 remote control (HTTP)
│   └── data_visualization/        # plotting and analysis of acquired data
├── scripts/                # check_* scripts for testing each instrument with real hardware
├── config/                 # run configuration (voltage levels, resource strings, CoMPASS configs)
└── data/                   # acquired data (not tracked by git)
```

## Installation

Requires Python 3.9+ (adjust to the version you use).

```bash
git clone https://github.com/CIEMAT-Neutrino/LAB-Instrumentation.git
cd LAB-Instrumentation/daq-lab15
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

The editable install (-e) makes the `daq` package importable from the scripts.

### USB permissions (Linux)

The QL564TP shows up as a CDC-ACM serial device (e.g. `/dev/ttyACM0`). If opening it fails with *Permission denied*, add your user to the `dialout` group and log in again:

```bash
sudo usermod -aG dialout $USER
```

If the device does not appear at all, check `dmesg` and try a different USB cable (a faulty cable can produce `cdc_acm` probe errors).

## Usage

Find the connected instruments with PyVISA:

```bash
python scripts/check_addr.py
```

Each instrument can be tested independently with the scripts in `scripts/` before launching a full run, for example:

```bash
python scripts/check_ql564tp.py
```

*(Script names may differ; see the `scripts/` folder.)*

### CoMPASS remote control

CoMPASS must be running with its remote control server enabled (default port 8080). The `caen_dt2730` module sends commands over HTTP: start/stop the acquisition, load a configuration file (`loadConfigFile`) and set the run identifier (`runId`, e.g. `run_A`, `run_B`).

## Configuration

Run parameters live in `config/`:

- sensor supply voltage levels for the sweep;
- LED generator level for each run type;
- instrument resource strings (VISA resource or serial port);
- CoMPASS address (e.g. `192.168.1.4:8080`) and the list of CoMPASS configuration files.

## Project status

- [x] Communication with the QL564TP and the signal generator over USB.
- [x] QL564TP driver: open, set/read voltage, set/read current limit, read current, output on/off.
- [ ] TGP3152 driver.
- [ ] DT2730 / CoMPASS remote control from Python (`caen_dt2730.py`).
- [ ] Run sequencer for the three run types.
- [ ] Data visualization tools.

## Code conventions

Source code is documented with Doxygen-style comments, written in English.

## Authors

Alba Moreno Ramos