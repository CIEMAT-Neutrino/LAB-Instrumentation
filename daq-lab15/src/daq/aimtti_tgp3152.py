"""!
@file   aimtti_tgp3152.py
@brief  Control functions of the AIM-TTI TGP3152 signal generator
"""
import pyvisa #Estándar puerto serie virtual

def open_generator(resource): #MODIFICAR
    """!
    @brief Open the power supply resource

    @param resource Instrument controller
    @return source
    """
    gen = pyvisa.ResourceManager("@py") 

    generator = gen.open_resource(resource)
    #generator.baud_rate = 19200   # manual
    generator.read_termination = "\n"
    generator.write_termination = "\n"
    print(generator.query("*IDN?"))
    return generator

