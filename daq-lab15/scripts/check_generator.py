"""!
@file   check_generator.py
@brief  Check connection of the aimtti_tgp3152.py
"""
import os

from daq import aimtti_tgp3152 as generator

SIGENERATOR = os.environ.get("TGP3152_RESOURCE", "ASRL/dev/ttyACM0::INSTR")


def main():
    gen = generator.open_generator(SIGENERATOR)
    try:
        status = generator.read_generator_configuration(gen)
        print(f"IDN: {status['device_id']}")
        for channel in status["channels"]:
            print(f"Canal {channel['channel']}: {channel}")
    finally:
        gen.close()


if __name__ == "__main__":
    main()