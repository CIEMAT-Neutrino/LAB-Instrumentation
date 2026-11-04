"""!
@file   check_generator.py
@brief  Check functions of the aimtti_tgp3152.py
"""
import time
from daq import aimtti_tgp3152 as generator

SIGENERATOR = "ASRL/dev/ttyACM0::INSTR"

def main():
    gen = generator.open_generator(SIGENERATOR)
    try:
        print("Configuring pulse output...")
        #CH1
        """
        generator.set_waveform(gen, 1, "SINE")
        generator.check_errors(gen)
        generator.set_signal_frequency(gen, 1, 2000)
        generator.check_errors(gen)
        generator.set_levels(gen, 1, 3, -3)
        #CH2
        """
        generator.set_waveform(gen, 1, "PULSE")
        generator.check_errors(gen)
        generator.set_pulse_frequency(gen, 1, 5000)
        generator.check_errors(gen)
        generator.set_pulse_width(gen, 1, 100e-6)
        generator.set_pulse_edges(gen, 1, 10e-6, 10e-6)
        generator.set_levels(gen, 1, 2.5, -3)
        generator.set_pulse_delay(gen, 1, 0.0)
        
        #generator.output(gen, 1, "ON")
        generator.output(gen, 1, "ON")

        input("Output on. Press enter to turn off...")
        print("Output disabled.")
    finally:
        try:
            #generator.output(gen, 1, "OFF")
            generator.output(gen, 1, "OFF")
        finally:
            gen.close()


if __name__ == "__main__":
    main()