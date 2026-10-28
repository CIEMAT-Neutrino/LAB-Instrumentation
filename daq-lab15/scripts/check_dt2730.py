"""
@file check_dt2730.py
@brief Hardware check of the CoMPASS remote control (CAEN DT2730).

@details
Runs, step by step, the basic operations of daq.caen_dt2730.CaenDT2730 and stops
at the first one that fails:
  1. Test the connection with the CoMPASS server.
  2. (Optional) Load a configuration file.
  3. Set a unique run ID (timestamp based, so no folder name collision happens).
  4. Perform a short acquisition (START, wait, STOP).

Prerequisites: CoMPASS running, board added, "Remote Control" enabled and data
saving enabled in CoMPASS (otherwise no run folder will be created).

Usage examples:
  python scripts/check_dt2730.py --host 192.168.1.4
  python scripts/check_dt2730.py --host 192.168.1.4 --config config1_thr_15LSB.xml --duration 10
"""

import argparse
import sys
import time

from daq.caen_dt2730 import CaenDT2730, CompassError


def parse_args():
    """
    @brief Parse the command line arguments.
    @return argparse.Namespace with host, port, config, duration and wait.
    """
    p = argparse.ArgumentParser(description="Check the CoMPASS remote control.")
    p.add_argument("--host", default="127.0.0.1", help="IP of the PC running CoMPASS")
    p.add_argument("--port", type=int, default=8080, help="Remote control port")
    p.add_argument("--config", default=None,
                   help="Config .xml in the CONFIG folder of the CoMPASS project (optional)")
    p.add_argument("--duration", type=float, default=10.0, help="Test run duration (s)")
    p.add_argument("--wait", type=float, default=6.0,
                   help="Seconds to wait after commands the server takes time to process")
    return p.parse_args()


def main():
    """
    @brief Run the check sequence.
    @return 0 if every step succeeded, 1 otherwise.
    """
    args = parse_args()
    dt = CaenDT2730(host=args.host, port=args.port, wait_time=args.wait)
    run_id = time.strftime("check_%Y%m%d_%H%M%S")

    try:
        print(f"[1/4] Testing connection with {args.host}:{args.port} ...")
        print("      CoMPASS says:", dt.test_connection().strip())

        if args.config:
            print(f"[2/4] Loading config '{args.config}' (waiting {args.wait} s) ...")
            dt.load_config(args.config)
        else:
            print("[2/4] No config file given, using the current CoMPASS configuration.")

        print(f"[3/4] Setting run ID '{run_id}' (waiting {args.wait} s) ...")
        dt.set_run_id(run_id, auto_increment=False)

        print(f"[4/4] Running for {args.duration} s ...")
        dt.run(args.duration)
    except CompassError as e:
        print(f"ERROR: {e}")
        return 1

    print(f"OK. Check that the folder '{run_id}' exists in the CoMPASS project "
          "and that it contains data.")
    return 0


if __name__ == "__main__":
    sys.exit(main())