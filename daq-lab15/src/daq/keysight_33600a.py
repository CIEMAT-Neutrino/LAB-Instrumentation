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
    return generator

def set_tracking(generator, mode)
"""!
    @brief Set the channel tracking mode.

    @param generator  VISA resource already opened with open_sigenerator.
    @param mode       "OFF" (independent channels), "ON" (channel 2 tracks
                      channel 1) or "INV" (channel 2 tracks channel 1 inverted).
    @return None
    """
    mode = mode.upper() #mayusc
    if mode not in ("OFF", "ON", "INV"):
        raise ValueError(f"Invalid tracking mode: {mode!r}")
    generator.write(f"SOURce1:TRACk {mode}")

def generate_pulse(generator, channel, frequency, Hlevel, Llevel, phase, Width, Ledge, Tedge):
    """!
    @brief Configure a pulse train on a specific channel.

    @param generator  VISA resource already opened with open_sigenerator.
    @param channel    Channel number (1 or 2).
    @param frequency  Pulse repetition frequency (Hz).
    @param Hlevel     High level (V).
    @param Llevel     Low level (V).
    @param phase      Phase (degrees).
    @param Width      Pulse width (s).
    @param Ledge      Leading edge time (s).
    @param Tedge      Trailing edge time (s).
    @return None
    """
    if Hlevel <= Llevel:
        raise ValueError(f"Hlevel ({Hlevel} V) must be greater than Llevel ({Llevel} V)")

    generator.write(f"SOURce{channel}:FUNCtion PULSe")
    generator.write(f"SOURce{channel}:FREQuency {frequency:.6g}")
    generator.write(f"SOURce{channel}:FUNCtion:PULSe:WIDTh {Width:.6g}")
    generator.write(f"SOURce{channel}:FUNCtion:PULSe:TRANsition:LEADing {Ledge:.6g}")
    generator.write(f"SOURce{channel}:FUNCtion:PULSe:TRANsition:TRAiling {Tedge:.6g}")

    # El generador rechaza un nivel bajo mayor que el nivel alto actual (y al revés),
    # así que el orden de escritura depende de dónde estén los niveles ahora.
    current_high = float(generator.query(f"SOURce{channel}:VOLTage:HIGH?"))
    if Llevel < current_high:
        generator.write(f"SOURce{channel}:VOLTage:LOW {Llevel:.6g}")
        generator.write(f"SOURce{channel}:VOLTage:HIGH {Hlevel:.6g}")
    else:
        generator.write(f"SOURce{channel}:VOLTage:HIGH {Hlevel:.6g}")
        generator.write(f"SOURce{channel}:VOLTage:LOW {Llevel:.6g}")

    generator.write(f"SOURce{channel}:PHASe {phase:.6g}")