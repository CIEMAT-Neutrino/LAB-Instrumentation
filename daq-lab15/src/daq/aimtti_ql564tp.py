"""!
@file   aimtti_ql564tp.py
@brief  Control functions of the AIM-TTI QL564TP power supply
"""
import logging
import pyvisa # La fuente utiliza el estándar de puerto serie virtual CDC (TTY)
import re

logger = logging.getLogger("daq.ql564tp")


def open_source(resource):
    """!
    @brief Open the power supply resource

    @param resource Instrument controller
    @return source
    """
    logger.info("SOURCE trying to open resource=%s", resource)
    try:
        rm = pyvisa.ResourceManager("@py") 

        source = rm.open_resource(resource)
        source.baud_rate = 19200   # manual
        source.read_termination = "\n"
        source.write_termination = "\n"
        idn = source.query("*IDN?")
        logger.info("SOURCE IDN reply=%r", idn)
        return source
    except Exception:
        logger.exception("SOURCE connection failed for resource=%s", resource)
        raise

def set_voltage(source, channel, volts):
    """!
    @brief Set the output voltage of a specific channel.

    @param source   VISA resource already opened with open_source.
    @param channel  Channel number (1, 2...).
    @param volts    Voltage (V).
    @return None
    """
    source.write(f"V{channel} {volts:.3f}")

def _to_float(reply):
    """!
    @brief Extract the number from an instrument reply such as '15.000V' or 'V1 15.000'.
    """
    return float(re.findall(r"[-+]?\d*\.?\d+", reply)[-1])
    
def read_voltage(source, channel):
    """!
    @brief Read the output voltage of a specific channel.

    @param source   VISA resource already opened with open_source.
    @param channel  Channel number (1, 2...).
    @return voltage
    """
    try:
        reply = source.query(f"V{channel}O?")
        value = _to_float(reply)
        logger.info("SOURCE read_voltage channel=%s reply=%r value=%s", channel, reply, value)
        return value
    except Exception:
        logger.exception("SOURCE read_voltage failed channel=%s", channel)
        raise

def read_set_voltage(source, channel):
    """!
    @brief Read the set voltage of a specific channel.

    @param source   VISA resource already opened with open_source.
    @param channel  Channel number (1, 2...).
    @return voltage
    """
    return _to_float(source.query(f"V{channel}?"))

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
    try:
        reply = source.query(f"I{channel}O?")
        value = _to_float(reply)
        logger.info("SOURCE read_current channel=%s reply=%r value=%s", channel, reply, value)
        return value
    except Exception:
        logger.exception("SOURCE read_current failed channel=%s", channel)
        raise

def read_current_limit(source, channel):
    """!
    @brief Read the current limit configured in a specific channel.

    @param source   VISA resource already opened with open_source.
    @param channel  Channel number (1, 2...).
    @return current_limit
    """
    try:
        reply = source.query(f"I{channel}?")
        value = _to_float(reply)
        logger.info("SOURCE read_current_limit channel=%s reply=%r value=%s", channel, reply, value)
        return value
    except Exception:
        logger.exception("SOURCE read_current_limit failed channel=%s", channel)
        raise

def check_errors(source):
    """!
    @brief Raise an exception if the last commands caused an execution error.

    @param source VISA resource already opened with open_source.
    @return None
    """
    code = int(source.query("EER?"))
    if code != 0:
        raise RuntimeError(f"QL564TP execution error (EER={code})")

def output(source, channel, on):
    """!
    @brief Activate/deactivate channel output

    @param source   VISA resource already opened with open_source.
    @param channel  Channel number (1, 2...).
    @param on   1 to activate, 0 to deactivate
    @return None
    """
    source.write(f"OP{channel} {1 if on else 0}")

def shutdown(source, channel):
    """!
    @brief Leave a channel in a safe state: 0 V and output off.
    """
    try:
        set_voltage(source, channel, 0)
    finally:
        output(source, channel, 0)

def close_source(source):
    """!
    @brief Close the VISA resource.
    """
    source.close()