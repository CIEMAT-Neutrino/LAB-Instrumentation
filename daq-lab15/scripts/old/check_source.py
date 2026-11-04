"""!
@file   check_source.py
@brief  Check functions of the aimtti_ql564tp.py
"""
import time
from daq import aimtti_ql564tp as source

PSUPPLY = "ASRL/dev/ttyACM0::INSTR"

def main():
    src = source.open_source(PSUPPLY)
    try:
        source.set_voltage(src, 1, 20)
        source.check_errors(src)
        source.set_voltage(src, 2, 53)
        source.check_errors(src)
        source.set_current_limit(src, 1, 15e-3)
        source.set_current_limit(src, 2, 10e-3)
        source.output(src, 1, 1)
        source.output(src, 2, 1)
        time.sleep(2)
        volt_set1 = source.read_set_voltage(src, 1)
        volt_set2 = source.read_set_voltage(src, 2)
        volt1 = source.read_voltage(src, 1)
        volt2 = source.read_voltage(src, 2)
        curr1 = source.read_current(src, 1)
        curr2 = source.read_current(src, 2)
        clim1 = source.read_current_limit(src, 1)
        clim2 = source.read_current_limit(src, 2)
        print("----CH1 POWER SUPPLY TEST----")
        print("Measured V1:", volt1)
        print("Measured I1:", curr1)
        print("V1 set:", volt_set1)
        print("I1 limit:", clim1)
        print("\n")
        print("----CH2 POWER SUPPLY TEST----")
        print("Measured V2:", volt2)
        print("Measured I2:", curr2)
        print("V2 set:", volt_set2)
        print("I2 limit:", clim2)
        print("\n")
        input("Output on. Press enter to turn off...")
    finally:
        source.shutdown(src, 1)
        source.shutdown(src, 2)
        source.close_source(src)

if __name__ == "__main__":
    main()