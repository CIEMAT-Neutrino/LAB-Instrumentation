"""!
@file   aimtti_ql564tp.py
@brief  
"""
import pyvisa # La fuente utiliza el estándar de puerto serie virtual CDC (TTY)

def open_source(resource):
    """!
    @brief Open the power supply resource

    @param resource Instrument controller
    @return source
    """
    rm = pyvisa.ResourceManager("@py") 

    source = rm.open_resource(resource)
    source.baud_rate = 19200   # manual
    source.read_termination = "\n"
    source.write_termination = "\n"
    print(source.query("*IDN?"))
    return source

def set_voltage(source, channel, volts):
    """!
    @brief Set the output voltage of a specific channel.

    @param source   VISA resource already opened with open_source.
    @param channel  Channel number (1, 2...).
    @param volts    Voltage (V).
    @return None
    """
    source.write(f"V{channel} {volts:.3f}")
    
def read_voltage(source, channel):
    """!
    @brief Read the output voltage of a specific channel.

    @param source   VISA resource already opened with open_source.
    @param channel  Channel number (1, 2...).
    @return voltage
    """
    return source.query(f"V{channel}O?")

def read_set_voltage(source, channel):
    """!
    @brief Read the set voltage of a specific channel.

    @param source   VISA resource already opened with open_source.
    @param channel  Channel number (1, 2...).
    @return voltage
    """
    return source.query(f"V{channel}?")

def set_current_limit(source, channel, amps):
    """!
    @brief Set the current limit of a specific channel.

    @param source   VISA resource already opened with open_source.
    @param channel  Channel number (1, 2...).
    @param amps     Current limit (A).
    @return None
    """
    source.write(f"I{channel} {amps:.4f}")

def read_current(source, channel):
    """!
    @brief Read the current given by a specific channel.

    @param source   VISA resource already opened with open_source.
    @param channel  Channel number (1, 2...).
    @return current
    """
    return source.query(f"I{channel}O?")

def read_current_limit(source, channel):
    """!
    @brief Read the current limit configured in a specific channel.

    @param source   VISA resource already opened with open_source.
    @param channel  Channel number (1, 2...).
    @return current_limit
    """
    return source.query(f"I{channel}?")

def output(source, channel, on):
    """!
    @brief Activate/deactivate channel output

    @param source   VISA resource already opened with open_source.
    @param channel  Channel number (1, 2...).
    @param on   1 to activate, 0 to deactivate
    @return None
    """
    source.write(f"OP{channel} {1 if on else 0}")