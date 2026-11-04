"""!
@file   check_source.py
@brief  Check connection of the aimtti_ql564tp.py
"""
import time
from daq import aimtti_ql564tp as source

PSUPPLY = "ASRL/dev/ttyACM0::INSTR"

def main():
    src = source.open_source(PSUPPLY)
    try:
        volt1 = source.read_voltage(src, 1)
        volt2 = source.read_voltage(src, 2)
        curr1 = source.read_current(src, 1)
        curr2 = source.read_current(src, 2)
        clim1 = source.read_current_limit(src, 1)
        clim2 = source.read_current_limit(src, 2)
        
    finally:
        source.close_source(src)

if __name__ == "__main__":
    main()