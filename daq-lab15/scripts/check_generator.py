"""!
@file   check_generator.py
@brief  Check functions of the aimtti_tgp3452.py
"""
import time
import aimtti_tgp3152 as generator

#SIGENERATOR = "USB0::2391::22279::MY53801010::0::INSTR"

#gen = generator.open_sigenerator(SIGENERATOR)
try:
    
    
finally:
    #gen.output(gen, 1, 0)
    gen.close()