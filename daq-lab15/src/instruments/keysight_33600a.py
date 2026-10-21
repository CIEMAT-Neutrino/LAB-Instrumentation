"""!
@file   keysight_33600a.py
@brief  Control functions of the Keysight 33600A signal generator
"""
import pyvisa #El generador utiliza el estándar USBTMC

def open_sigenerator(resource):
    """!
    @brief Open the signal generator resource

    @param resource Instrument controller
    @return source
    """
    rm = pyvisa.ResourceManager("@py")
    gen = rm.open_resource(resource)
    print(gen.query("*IDN?"))
    return gen

