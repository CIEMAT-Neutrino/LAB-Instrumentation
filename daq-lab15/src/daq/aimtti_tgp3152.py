"""!
@file   aimtti_tgp3152.py
@brief  Control functions of the AIM-TTI TGP3152 signal generator
"""
import pyvisa #Estándar puerto serie virtual

def open_generator(resource):
    """!
    @brief Open the signal generator resource

    @param resource Instrument controller
    @return generator
    """
    gen = pyvisa.ResourceManager("@py") 

    generator = gen.open_resource(resource)
    #generator.baud_rate = 19200   # manual
    generator.read_termination = "\n"
    generator.write_termination = "\n"
    print(generator.query("*IDN?"))
    return generator

def check_errors(generator):
    """!
    @brief Raise an exception if the last commands caused an error.

    Reads and clears the Execution Error Register (EER?) and the Query Error
    Register (QER?).

    @param generator  VISA resource already opened with open_generator.
    @return None
    """
    exec_err = int(generator.query("EER?"))
    query_err = int(generator.query("QER?"))
    if exec_err != 0 or query_err != 0:
        raise RuntimeError(f"TGP3152 error (EER={exec_err}, QER={query_err})")

def select_channel(generator, channel):
    """!
    @brief Select the channel that subsequent commands will act on.

    @param generator  VISA resource already opened with open_generator.
    @param channel    Channel number (1 or 2).
    @return None
    """
    if channel not in (1, 2):
        raise ValueError(f"Invalid channel: {channel!r}")
    generator.write(f"CHN {channel}")


def set_waveform(generator, channel, wave):
    """!
    @brief Set the output waveform type of a channel.

    @param generator  VISA resource already opened with open_generator.
    @param channel    Channel number (1 or 2).
    @param wave       "PULSE", "SQUARE", "DOUBLEPULSE", "SINE", "RAMP", "TRIANG"
    @return None
    """
    select_channel(generator, channel)
    generator.write(f"WAVE {wave.upper()}")

def set_signal_frequency(generator, channel, hz):
    """!
    @brief Set the signal frequency of a channel.

    @param generator  VISA resource already opened with open_generator.
    @param channel    Channel number (1 or 2).
    @param hz         Frequency (Hz).
    @return None
    """
    select_channel(generator, channel)
    generator.write(f"FREQ {hz:.6g}")

def set_pulse_frequency(generator, channel, hz):
    """!
    @brief Set the pulse repetition frequency of a channel.

    @param generator  VISA resource already opened with open_generator.
    @param channel    Channel number (1 or 2).
    @param hz         Frequency (Hz).
    @return None
    """
    select_channel(generator, channel)
    generator.write(f"PULSFREQ {hz:.6g}")


def set_pulse_width(generator, channel, seconds):
    """!
    @brief Set the pulse width of a channel.

    @param generator  VISA resource already opened with open_generator.
    @param channel    Channel number (1 or 2).
    @param seconds    Pulse width (s).
    @return None
    """
    select_channel(generator, channel)
    generator.write(f"PULSWID {seconds:.6g}")


def set_pulse_edges(generator, channel, rise, fall):
    """!
    @brief Set the rising and falling edge times of a channel.

    @param generator  VISA resource already opened with open_generator.
    @param channel    Channel number (1 or 2).
    @param rise       Positive (leading) edge time (s).
    @param fall       Negative (trailing) edge time (s).
    @return None
    """
    select_channel(generator, channel)
    generator.write(f"PULSRISE {rise:.6g}")
    generator.write(f"PULSFALL {fall:.6g}")


def set_levels(generator, channel, high, low):
    """!
    @brief Set the high and low levels of a channel.

    @param generator  VISA resource already opened with open_generator.
    @param channel    Channel number (1 or 2).
    @param high       High level (V).
    @param low        Low level (V).
    @return None
    """
    if high <= low:
        raise ValueError(f"high ({high} V) must be greater than low ({low} V)")
    select_channel(generator, channel)
    generator.write(f"HILVL {high:.6g}")
    generator.write(f"LOLVL {low:.6g}")


def set_load(generator, channel, load):
    """!
    @brief Set the output load the generator assumes for amplitude entries.

    @param generator  VISA resource already opened with open_generator.
    @param channel    Channel number (1 or 2).
    @param load       Load in ohms (50 to 10000) or "OPEN".
    @return None
    """
    select_channel(generator, channel)
    generator.write(f"ZLOAD {str(load).upper()}")


def set_pulse_delay(generator, channel, seconds):
    """!
    @brief Set the pulse delay of a channel.

    @param generator  VISA resource already opened with open_generator.
    @param channel    Channel number (1 or 2).
    @param seconds    Pulse delay (s).
    @return None
    """
    select_channel(generator, channel)
    generator.write(f"PULSDLY {seconds:.6g}")


def output(generator, channel, state):
    """!
    @brief Set the output state of a channel.

    @param generator  VISA resource already opened with open_generator.
    @param channel    Channel number (1 or 2).
    @param state      "ON", "OFF", "NORMAL" or "INVERT".
    @return None
    """
    state = state.upper()
    if state not in ("ON", "OFF", "NORMAL", "INVERT"):
        raise ValueError(f"Invalid output state: {state!r}")
    select_channel(generator, channel)
    generator.write(f"OUTPUT {state}")


def generate_pulse(generator, channel, frequency, Hlevel, Llevel, delay, Width, Ledge, Tedge):
    """!
    @brief Configure a pulse train on a channel. The output state is not changed.

    @param generator  VISA resource already opened with open_generator.
    @param channel    Channel number (1 or 2).
    @param frequency  Pulse repetition frequency (Hz).
    @param Hlevel     High level (V).
    @param Llevel     Low level (V).
    @param delay      Pulse delay (s).
    @param Width      Pulse width (s).
    @param Ledge      Leading edge time (s).
    @param Tedge      Trailing edge time (s).
    @return None
    """
    set_waveform(generator, channel, "PULSE")
    set_pulse_frequency(generator, channel, frequency)
    set_pulse_width(generator, channel, Width)
    set_pulse_edges(generator, channel, Ledge, Tedge)
    set_levels(generator, channel, Hlevel, Llevel)
    set_pulse_delay(generator, channel, delay)
    check_errors(generator)

