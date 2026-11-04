"""!
@file   aimtti_tgp3152.py
@brief  Control functions of the AIM-TTI TGP3152 signal generator
"""
import logging
import os
import re

import pyvisa #Estándar puerto serie virtual

logger = logging.getLogger("daq.tgp3152")


def open_generator(resource):
    """!
    @brief Open the signal generator resource

    @param resource Instrument controller
    @return generator
    """
    logger.info("GENERATOR: intentando abrir puerto %s", resource)
    try:
        gen = pyvisa.ResourceManager("@py") 

        generator = gen.open_resource(resource)
        #generator.baud_rate = 19200   # manual
        generator.read_termination = "\n"
        generator.write_termination = "\n"
        idn = generator.query("*IDN?")
        logger.info("GENERATOR: respuesta IDN -> %s", str(idn).strip())
        return generator
    except Exception:
        logger.exception("GENERATOR: fallo de conexión con %s", resource)
        raise


def _coerce_query_value(raw_value):
    """Convert a VISA response into a numeric value or a normalized string."""
    value = str(raw_value).strip()
    if not value:
        return None
    if re.search(r"[A-Za-z]", value):
        return value.upper()
    match = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", value)
    if not match:
        return value.upper()
    return float(match[-1])


def read_channel_configuration(generator, channel):
    """Read the configuration of a specific channel in a normalized format."""
    if channel not in (1, 2):
        raise ValueError(f"Invalid channel: {channel!r}")
    try:
        select_channel(generator, channel)
        queries = {
            "waveform": "WAVE?",
            "frequency": "FREQ?",
            "high_level": "HILVL?",
            "low_level": "LOLVL?",
            "pulse_width": "PULSWID?",
        }
        payload = {"channel": channel}
        for key, command in queries.items():
            try:
                reply = generator.query(command)
                payload[key] = _coerce_query_value(reply)
                logger.info("GENERATOR: canal %s consulta %s -> %r", channel, command, reply)
            except Exception as exc:
                logger.error(
                    "GENERATOR: canal %s fallo en consulta %s: %s",
                    channel,
                    command,
                    exc,
                )
                raise RuntimeError(f"Canal {channel}: consulta {command} falló: {exc}") from exc
        logger.info("GENERATOR: canal %s configuración final = %s", channel, payload)
        return payload
    except Exception:
        logger.exception("GENERATOR: fallo al leer configuración del canal %s", channel)
        raise


def read_generator_configuration(generator):
    """Read the full configuration of both channels of the TGP3152."""
    try:
        device_id = generator.query("*IDN?").strip()
        payload = {
            "device_id": device_id,
            "channels": [
                read_channel_configuration(generator, 1),
                read_channel_configuration(generator, 2),
            ],
        }
        logger.info("GENERATOR full configuration=%s", payload)
        return payload
    except Exception:
        logger.exception("GENERATOR read_generator_configuration failed")
        raise


def check_generator_communication(resources=None):
    """Try the configured resource and return the current generator configuration.

    For this bench the TGP3152 is known to be connected on a single serial resource,
    so we do not iterate over a broad list of fallback ports by default. This keeps
    the log readable and prevents false confusion caused by trying several ports
    that are simply not present.
    """
    if resources is None:
        configured = os.environ.get("TGP3152_RESOURCE")
        if configured:
            resources = [part.strip() for part in configured.split(",") if part.strip()]
        else:
            resources = ["ASRL/dev/ttyACM0::INSTR"]

    log_lines: list[str] = []
    last_error = None
    for resource in resources:
        if not resource:
            continue
        log_lines.append(f"Abriendo generador en {resource}")
        try:
            generator = open_generator(resource)
            try:
                idn_value = generator.query("*IDN?").strip()
                log_lines.append(f"IDN OK: {idn_value}")
                try:
                    config = read_generator_configuration(generator)
                    log_lines.append(f"Generador responde: {config['device_id']}")
                    return {
                        "connected": True,
                        "description": config["device_id"],
                        "channels": config["channels"],
                        "state": "ready",
                        "message": "Comunicación OK",
                        "log": log_lines,
                    }
                except Exception as exc:
                    log_lines.append(f"Error al leer canales: {exc}")
                    return {
                        "connected": True,
                        "description": idn_value,
                        "channels": [],
                        "state": "connected",
                        "message": f"IDN OK, pero falla la lectura de canales: {exc}",
                        "log": log_lines,
                    }
            finally:
                generator.close()
        except Exception as exc:  # pragma: no cover - hardware dependent
            last_error = exc
            log_lines.append(f"Error en {resource}: {exc}")
            logger.exception("GENERATOR: fallo de comunicación en %s", resource)
            break

    failure_message = str(last_error) if last_error else "No se detectó el generador TGP3152"
    return {
        "connected": False,
        "description": "Thurlby Thandar Instruments Limited TGP3152",
        "channels": [],
        "state": "disconnected",
        "message": failure_message,
        "log": log_lines or [failure_message],
    }


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

