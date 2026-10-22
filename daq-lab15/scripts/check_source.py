"""!
@file   check_source.py
@brief  Check functions of the aimtti_ql564tp.py
"""
import time
from daq import aimtti_ql564tp as source
#import keysight_33600a as generator

PSUPPLY = "ASRL/dev/ttyACM0::INSTR"
#SIGENERATOR = "USB0::2391::22279::MY53801010::0::INSTR"

src = source.open_source(PSUPPLY)
#gen = generator.open_sigenerator(SIGENERATOR)
"""try:
    source.set_voltage(src, 1, 30)
    source.set_current_limit(src, 1, 18e-3)
    #source.output(src, 1, 1)
    time.sleep(2)
    volt_set = source.read_set_voltage(src, 1)
    volt = source.read_voltage(src, 1)
    curr = source.read_current(src, 1)
    clim = source.read_current_limit(src, 1)
    print("POWER SUPPLY TEST")
    print("Measured V:", volt)
    print("Measured I:", curr)
    print("V set:", volt_set)
    print("I limit:", clim)
    print("\n")
    input("Output on. Press enter to turn off...")
finally:
    #source.output(src, 1, 0)
    #gen.output(gen, 1, 0)"""
src.close()