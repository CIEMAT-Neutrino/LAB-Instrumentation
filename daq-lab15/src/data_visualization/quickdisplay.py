"""!
@file   quickdisplay.py
@brief  Genera una vista rapida de la waveform media del RAW de CoMPASS.

Visualizacion rapida de los datos RAW de CoMPASS guardados en
Data/CoMPASS256_ExternalTrigger/DAQ/<run>/RAW.

Para cada archivo calcula la waveform media de un numero limitado de eventos
(100 por defecto) y genera una pagina HTML interactiva con Plotly que se abre
en el navegador.

Ejemplos de uso:
- python src/data_visualization/quickdisplay.py
- python src/data_visualization/quickdisplay.py 11Junio_run_2 11Junio_run_3
- python src/data_visualization/quickdisplay.py --max-events 100 --no-open
- python src/data_visualization/quickdisplay.py data/CoMPASS256_ExternalTrigger/DAQ/11Junio_run_2/RAW/DataR_CH0@DT2730_66353_11Junio_run_2.BIN
"""

import argparse
import mmap
import re
import webbrowser
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
DAQ_DIR = DATA_DIR / "CoMPASS256_ExternalTrigger" / "DAQ"
OUT_HTML = DATA_DIR / "quickdisplay.html"
DEFAULT_MAX_EVENTS = 100

# Parametro de settings.xml con el numero de bins del espectro y rango de la energia (16 bits)
KEY_NBINS = "SRV_PARAM_CH_SPECTRUM_NBINS"
ENERGY_RANGE = 1 << 16
DEFAULT_NBINS = 4096

# Waveform media de single photon electron (SPE): eventos usados y deteccion de picos
SPE_EVENTS = 100
PEAK_MIN_PROMINENCE = 0.05  # fraccion del maximo del histograma suavizado
PEAK_SMOOTH_SIGMA = 1.5     # en bins
HIST_TARGET_BINS = 300      # resolucion del histograma usado para buscar picos

# Arapucas: los canales van por pares (CH0+CH1 = arapuca A, CH2+CH3 = arapuca B, ...)
CHANNELS_PER_ARAPUCA = 2
PALETTE = ["#f2a65a", "#7dd3fc"]  # color del 1er / 2o canal de una arapuca

# Geometria de las figuras con varias filas (px): alto por fila y hueco entre filas
ROW_HEIGHT_PX = 300
ROW_GAP_PX = 140

# DT2730: 500 MS/s (2 ns) con WAVE_DOWNSAMPLING_X2 en CoMPASS -> 4 ns por muestra
SAMPLE_PERIOD_NS = 4.0

# Bits del header (0xCAEx)
HAS_ENERGY_CH = 1 << 0
HAS_ENERGY_CAL = 1 << 1
HAS_ENERGY_SHORT = 1 << 2
HAS_WAVEFORM = 1 << 3


def read_header(path):
    """!
    @brief Lee el header del archivo .BIN y devuelve la informacion del evento.

    @param path Ruta al archivo RAW de CoMPASS.
    @return Tupla (n_samples, dtype) con el numero de muestras y el dtype del evento.
    """
    with open(path, "rb") as f:
        header = int.from_bytes(f.read(2), "little")
        if header & 0xFFF0 != 0xCAE0:
            raise ValueError(f"{path.name}: header invalido 0x{header:04X}")

        fields = [("board", "<u2"), ("channel", "<u2"), ("timestamp", "<u8")]
        if header & HAS_ENERGY_CH:
            fields.append(("energy", "<u2"))
        if header & HAS_ENERGY_CAL:
            fields.append(("energy_cal", "<f8"))
        if header & HAS_ENERGY_SHORT:
            fields.append(("energy_short", "<u2"))
        fields.append(("flags", "<u4"))

        if not header & HAS_WAVEFORM:
            raise ValueError(f"{path.name}: el archivo no contiene waveforms")

        # El numero de muestras va dentro de cada evento; se lee del primero
        # y se asume constante (lo es en CoMPASS para una misma adquisicion).
        f.seek(2 + np.dtype(fields).itemsize + 1)
        n_samples = int.from_bytes(f.read(4), "little")

    fields += [("wave_code", "u1"), ("n_samples", "<u4"), ("samples", "<u2", (n_samples,))]
    return n_samples, np.dtype(fields)


def event_offsets(mm, dtype):
    """!
    @brief Busca las posiciones de inicio de cada evento valido dentro del buffer.

    Algunos archivos tienen eventos truncados por bloques perdidos al escribir,
    asi que no se puede asumir un tamano fijo. Se recorre evento a evento y, si
    uno no cuadra, se busca el siguiente por la firma wave_code + n_samples.

    @param mm Buffer mapeado en memoria del archivo.
    @param dtype Dtype del evento leido en el header.
    @return Tupla (offsets, skipped) con los offsets validos y los eventos corruptos descartados.
    """
    size = dtype.itemsize
    sig_pos = dtype.fields["wave_code"][1]
    sig = mm[2 + sig_pos:2 + sig_pos + 5]  # wave_code + n_samples del primer evento
    ident = mm[2:6]                        # board + channel del primer evento
    buf = memoryview(mm)

    offsets, skipped = [], 0
    pos, end = 2, len(mm)
    while pos + size <= end:
        if buf[pos + sig_pos:pos + sig_pos + 5] == sig and buf[pos:pos + 4] == ident:
            nxt = pos + size
            # Si el siguiente evento no empieza donde toca, este esta truncado
            if nxt + sig_pos + 5 > end or buf[nxt + sig_pos:nxt + sig_pos + 5] == sig:
                offsets.append(pos)
                pos = nxt
                continue
        skipped += 1
        found = mm.find(sig, pos + 1 + sig_pos)
        if found < 0:
            break
        pos = found - sig_pos
    buf.release()
    return np.array(offsets, dtype=np.int64), skipped


def mean_waveform(path, max_events=None):
    """!
    @brief Calcula la waveform media para un archivo y un numero maximo de eventos.

    @param path Ruta al archivo .BIN a analizar.
    @param max_events Numero maximo de eventos a considerar. Si es None, usa todos.
    @return Tupla (mean, std, n_events, skipped) con la media, la desviacion estandar,
            el numero de eventos usados y los eventos corruptos descartados.
    """
    n_samples, dtype = read_header(path)
    with open(path, "rb") as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
        offsets, skipped = event_offsets(mm, dtype)
        if max_events:
            offsets = offsets[:max_events]
        mean, std = _accumulate(np.frombuffer(mm, dtype=np.uint8), offsets, dtype, n_samples)
    return mean, std, len(offsets), skipped


def _accumulate(raw, offsets, dtype, n_samples):
    """!
    @brief Acumula muestra a muestra los eventos para calcular la media y la sigma.

    @param raw Buffer en bruto del archivo.
    @param offsets Posiciones de inicio de los eventos validos.
    @param dtype Dtype del evento.
    @param n_samples Numero de muestras por waveform.
    @return Tupla (mean, std) con la waveform media y la desviacion estandar.
    """
    # Acumular por bloques para no cargar el archivo entero en memoria
    samples_pos = dtype.fields["samples"][1] + 2 * np.arange(n_samples)
    acc = np.zeros(n_samples)
    acc2 = np.zeros(n_samples)
    chunk = 2000
    for i in range(0, len(offsets), chunk):
        idx = offsets[i:i + chunk, None] + samples_pos
        w = (raw[idx].astype(np.uint16) | (raw[idx + 1].astype(np.uint16) << 8)).astype(np.float64)
        acc += w.sum(axis=0)
        acc2 += (w * w).sum(axis=0)

    n = len(offsets)
    mean = acc / n
    std = np.sqrt(np.maximum(acc2 / n - mean**2, 0))
    return mean, std


def _read_u2(raw, offsets, pos):
    """!
    @brief Lee un campo uint16 little-endian situado en `pos` dentro de cada evento.

    @param raw Buffer en bruto del archivo (uint8).
    @param offsets Posiciones de inicio de los eventos.
    @param pos Desplazamiento del campo dentro del evento.
    @return Array uint16 con un valor por evento.
    """
    return raw[offsets + pos].astype(np.uint16) | (raw[offsets + pos + 1].astype(np.uint16) << 8)


def read_energies(path, field="energy"):
    """!
    @brief Lee el campo de energia (carga integrada) de todos los eventos validos de un archivo.

    @param path Ruta al archivo .BIN.
    @param field Campo a leer: "energy" (carga larga) o "energy_short".
    @return Tupla (energies, skipped) con un array uint16 y los eventos corruptos descartados.
    """
    n_samples, dtype = read_header(path)
    if field not in dtype.fields:
        raise ValueError(f"{path.name}: el archivo no contiene el campo '{field}'")
    with open(path, "rb") as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
        offsets, skipped = event_offsets(mm, dtype)
        raw = np.frombuffer(mm, dtype=np.uint8)
        energies = _read_u2(raw, offsets, dtype.fields[field][1])
        del raw
    return energies, skipped


def _find_peaks(h, min_prominence):
    """!
    @brief Busca maximos locales con prominencia minima en un histograma suavizado.

    @param h Cuentas por bin (suavizadas).
    @param min_prominence Prominencia minima en cuentas.
    @return Lista de indices de pico ordenada por posicion.
    """
    peaks = []
    n = len(h)
    for i in range(n):
        left_ok = i == 0 or h[i] >= h[i - 1]
        right_ok = i == n - 1 or h[i] > h[i + 1]
        if not (left_ok and right_ok):
            continue
        left_min = h[i]
        for j in range(i - 1, -1, -1):
            if h[j] > h[i]:
                break
            left_min = min(left_min, h[j])
        right_min = h[i]
        for j in range(i + 1, n):
            if h[j] > h[i]:
                break
            right_min = min(right_min, h[j])
        if h[i] - max(left_min, right_min) >= min_prominence:
            peaks.append(i)
    return peaks


def find_spe_window(energies):
    """!
    @brief Localiza el rango de carga del single photon electron (SPE) en el histograma.

    El histograma de carga tiene varias "montanas": la primera es el pedestal de ruido,
    la segunda el SPE, la tercera 2 fotoelectrones, etc. Se suaviza el histograma, se
    detectan los picos y se toma el segundo. El rango va de un valle al otro: del minimo
    entre pedestal y SPE al minimo entre SPE y el siguiente pico (si no hay siguiente
    pico, de forma simetrica respecto al valle izquierdo).

    @param energies Array de cargas (energy) de todos los eventos.
    @return Dict con pedestal, spe, lo, hi (ambos inclusivos, en canales) o None si no
            se distinguen al menos dos picos.
    """
    if len(energies) < 100:
        return None
    top = float(np.percentile(energies, 99.5)) + 1
    width = max(1, int(np.ceil(top / HIST_TARGET_BINS)))
    edges = np.arange(0, top + width, width)
    counts, _ = np.histogram(energies, bins=edges)

    radius = int(4 * PEAK_SMOOTH_SIGMA) + 1
    kernel = np.exp(-0.5 * (np.arange(-radius, radius + 1) / PEAK_SMOOTH_SIGMA) ** 2)
    h = np.convolve(counts, kernel / kernel.sum(), mode="same")

    peaks = _find_peaks(h, PEAK_MIN_PROMINENCE * h.max())
    if len(peaks) < 2:
        return None
    ped, spe = peaks[0], peaks[1]
    left = ped + int(np.argmin(h[ped:spe + 1]))
    if len(peaks) > 2:
        right = spe + int(np.argmin(h[spe:peaks[2] + 1]))
    else:
        right = min(len(h), spe + (spe - left))
    return {
        "pedestal": (ped + 0.5) * width,
        "spe": (spe + 0.5) * width,
        "lo": int(left * width),
        "hi": int(right * width) - 1,
    }


def spe_mean_waveform(path, n_events=SPE_EVENTS):
    """!
    @brief Waveform media de los primeros `n_events` eventos cuya carga cae en el pico SPE.

    Si no se distingue el pico SPE en el histograma de carga, se promedian los primeros
    `n_events` eventos del archivo sin filtrar por carga.

    @param path Ruta al archivo .BIN a analizar.
    @param n_events Numero de eventos a promediar.
    @return Tupla (mean, std, n_used, skipped, window) con la media, la sigma, los eventos
            usados, los eventos corruptos descartados y el dict de find_spe_window
            (None si se uso el respaldo sin SPE).
    @throws ValueError si el archivo no tiene ningun evento utilizable.
    """
    n_samples, dtype = read_header(path)
    with open(path, "rb") as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
        offsets, skipped = event_offsets(mm, dtype)
        raw = np.frombuffer(mm, dtype=np.uint8)
        energies = _read_u2(raw, offsets, dtype.fields["energy"][1])
        window = find_spe_window(energies)
        if window is None:
            selected = offsets[:n_events]
        else:
            in_peak = (energies >= window["lo"]) & (energies <= window["hi"])
            selected = offsets[in_peak][:n_events]
        if len(selected) == 0:
            del raw
            raise ValueError(f"{path.name}: sin eventos utilizables")
        mean, std = _accumulate(raw, selected, dtype, n_samples)
        del raw
    return mean, std, len(selected), skipped, window


def _figure_height(rows):
    """!
    @brief Alto total de la figura en px: filas mas huecos entre ellas.

    @param rows Numero de filas de graficas.
    @return Alto en px.
    """
    return ROW_HEIGHT_PX * rows + ROW_GAP_PX * (rows - 1)


def _row_spacing(rows):
    """!
    @brief Separacion vertical entre filas como fraccion del alto, para que no se solapen los textos.

    @param rows Numero de filas de graficas.
    @return Fraccion para vertical_spacing (0 si solo hay una fila).
    """
    return ROW_GAP_PX / _figure_height(rows) if rows > 1 else 0


def waveform_legend(label, n, rng):
    """!
    @brief Texto de leyenda de una waveform media.

    @param label Etiqueta del canal (p. ej. "CH0").
    @param n Eventos promediados.
    @param rng Tupla (lo, hi) del rango de carga usado, o None si no se filtro por carga.
    @return "<canal> · carga lo–hi ch" o "<canal> · primeros N eventos".
    """
    if rng:
        return f"{label} · carga {rng[0]}–{rng[1]} ch"
    return f"{label} · primeros {n} eventos"


def _grid(groups):
    """!
    @brief Crea la cuadricula de subgraficas (2 columnas) con una por grupo.

    @param groups Lista de titulos de subgrafica.
    @return Tupla (fig, rows, cols).
    """
    cols = 1 if len(groups) == 1 else 2
    rows = -(-len(groups) // cols)
    fig = make_subplots(rows=rows, cols=cols, subplot_titles=groups,
                        vertical_spacing=_row_spacing(rows), horizontal_spacing=0.08)
    return fig, rows, cols


def _legend_layout():
    """!
    @brief Leyenda horizontal fuera del area de graficas (clic en una entrada oculta/muestra el canal).

    @return Dict con legend y margin para update_layout.
    """
    return {
        "legend": dict(orientation="h", yref="container", y=1, yanchor="top", x=0, xanchor="left"),
        "margin": dict(t=110),
    }


def waveform_figure(items, dt_ns=SAMPLE_PERIOD_NS, legend=True):
    """!
    @brief Construye la figura de waveforms medias, una grafica por grupo con un trazo por canal.

    @param items Lista de dicts con group (titulo de la grafica), name (leyenda), mean, std
           y color_idx (0/1, color dentro del grupo).
    @param dt_ns Periodo de muestreo en ns.
    @param legend Si es True muestra la leyenda (clic para ocultar/mostrar un canal).
    @return Figura de Plotly.
    """
    groups = list(dict.fromkeys(it["group"] for it in items))
    fig, rows, cols = _grid(groups)
    for it in items:
        i = groups.index(it["group"])
        row, col = i // cols + 1, i % cols + 1
        t_us = np.arange(len(it["mean"])) * dt_ns / 1000
        fig.add_trace(go.Scatter(
            x=t_us, y=it["mean"], mode="lines", name=it["name"], showlegend=legend,
            line=dict(color=PALETTE[it.get("color_idx", 0) % len(PALETTE)]),
            customdata=it["std"],
            hovertemplate=f"{it['name']}<br>t %{{x:.3f}} µs<br>media %{{y:.1f}}<br>σ %{{customdata:.1f}}<extra></extra>",
        ), row=row, col=col)
        fig.update_xaxes(title_text="Tiempo (µs)", row=row, col=col)
        fig.update_yaxes(title_text="ADC (ch)", row=row, col=col)
    fig.update_layout(height=_figure_height(rows), template="plotly_white", **(_legend_layout() if legend else {}))
    return fig


def read_spectrum_nbins(path):
    """!
    @brief Lee SRV_PARAM_CH_SPECTRUM_NBINS del settings.xml del run al que pertenece el archivo.

    Se usa el valor del canal si existe en <channel><index>N</index> y, si no,
    el valor global de la placa. El canal se deduce del nombre (DataR_CH<N>@...).

    @param path Ruta al archivo .BIN dentro de <run>/RAW.
    @return Numero de bins o None si no hay settings.xml o no define el parametro.
    """
    settings = path.parent.parent / "settings.xml"
    if not settings.is_file():
        return None
    try:
        root = ET.parse(settings).getroot()
    except ET.ParseError:
        return None

    def _value(entries):
        for entry in entries:
            if entry.findtext("key") == KEY_NBINS:
                text = (entry.find("value/value").text or "").strip()
                if text.startswith("BINS_") and text[5:].isdigit():
                    return int(text[5:])
        return None

    match = re.search(r"CH(\d+)", path.name)
    if match:
        for channel in root.iter("channel"):
            if channel.findtext("index") == match.group(1):
                value = _value(channel.findall("values/entry"))
                if value:
                    return value
    return _value(root.findall("board/parameters/entry"))


def histogram_figure(items):
    """!
    @brief Histograma de carga larga (escala lineal): una grafica por grupo, un histograma por canal.

    Los bins dividen el rango completo de 16 bits (0..65535) en n_bins, igual que el
    espectro de CoMPASS. Solo se dibujan hasta el ultimo bin con cuentas. Los canales de
    un grupo se superponen con transparencia.

    @param items Lista de dicts con group, name (leyenda), energies, n_bins y color_idx.
    @return Figura de Plotly.
    """
    groups = list(dict.fromkeys(it["group"] for it in items))
    fig, rows, cols = _grid(groups)
    for it in items:
        i = groups.index(it["group"])
        row, col = i // cols + 1, i % cols + 1
        counts, edges = np.histogram(it["energies"], bins=it["n_bins"], range=(0, ENERGY_RANGE))
        nonzero = np.flatnonzero(counts)
        last = nonzero[-1] + 1 if len(nonzero) else it["n_bins"]
        centers = (edges[:last] + edges[1:last + 1]) / 2
        fig.add_trace(go.Bar(
            x=centers, y=counts[:last], name=it["name"], showlegend=True,
            marker=dict(color=PALETTE[it.get("color_idx", 0) % len(PALETTE)], line_width=0), opacity=0.7,
            hovertemplate=f"{it['name']}<br>carga %{{x:.0f}} ch<br>cuentas %{{y}}<extra></extra>",
        ), row=row, col=col)
        fig.update_xaxes(title_text="Carga (energy, ch)", row=row, col=col)
        fig.update_yaxes(title_text="Cuentas", row=row, col=col)
    fig.update_layout(height=_figure_height(rows), template="plotly_white", bargap=0, barmode="overlay",
                      **_legend_layout())
    return fig


def file_label(path):
    """!
    @brief Nombre corto "<run>:<archivo>" usado en los titulos de las graficas.

    @param path Ruta al archivo .BIN.
    @return Etiqueta de texto.
    """
    run_name = path.parent.parent.name if path.parent.name == "RAW" else path.parent.name
    return f"{run_name}:{path.stem}"


def channel_label(path):
    """!
    @brief Etiqueta corta del canal a partir del nombre (DataR_CH2@DT2730_... -> "CH2").

    @param path Ruta al archivo .BIN.
    @return "CH<n>" o el nombre del archivo si no lleva canal.
    """
    match = re.search(r"CH(\d+)", path.name)
    return f"CH{match.group(1)}" if match else path.stem


def channel_number(path):
    """!
    @brief Numero de canal a partir del nombre del archivo (DataR_CH2@... -> 2).

    @param path Ruta al archivo .BIN.
    @return int o None si el nombre no lleva canal.
    """
    match = re.search(r"CH(\d+)", path.name)
    return int(match.group(1)) if match else None


def arapuca_name(channel):
    """!
    @brief Letra de la arapuca a la que pertenece un canal (CH0, CH1 -> "A"; CH2, CH3 -> "B"...).

    @param channel Numero de canal.
    @return Letra de la arapuca.
    """
    return chr(ord("A") + channel // CHANNELS_PER_ARAPUCA)


def run_sort_key(path):
    """!
    @brief Ordena los nombres de run de forma numerica para evitar run_10 > run_2.

    @param path Ruta del directorio o archivo del run.
    @return Clave de ordenacion para sort().
    """
    stem = path.stem
    parts = stem.rsplit("_", 1)
    if len(parts) == 2 and parts[1].isdigit():
        return (parts[0], int(parts[1]))
    return (stem, 0)


def iter_raw_files(path):
    """!
    @brief Devuelve los archivos .BIN dentro de una carpeta RAW o de un run concreto.

    @param path Ruta a un archivo .BIN, a un directorio RAW o a un directorio de run.
    @return Lista ordenada de archivos .BIN encontrados.
    """
    path = Path(path)
    if path.is_file() and path.suffix.lower() == ".bin":
        return [path]

    if path.is_dir() and path.name == "RAW":
        files = [p for p in path.iterdir() if p.is_file() and p.suffix.lower() == ".bin"]
        return sorted(files, key=lambda p: p.name.lower())

    if path.is_dir():
        raw_dir = path / "RAW"
        if raw_dir.is_dir():
            return iter_raw_files(raw_dir)

    return []


def resolve_input_files(requests):
    """!
    @brief Resuelve nombres de run o rutas de archivo y devuelve los .BIN a procesar.

    Busca en cualquier carpeta dentro de data/

    @param requests Lista de nombres de run o rutas a archivos/directorios.
    @return Lista ordenada de archivos RAW que se van a plotear.
    """
    files = []
    seen = set()

    def _search_anywhere(request):
        candidates = []
        request_l = request.lower()

        for raw_dir in sorted(DATA_DIR.rglob("RAW"), key=lambda p: str(p).lower()):
            if not raw_dir.is_dir():
                continue
            parent_name = raw_dir.parent.name.lower()
            if request_l in parent_name or request_l in raw_dir.parent.name.lower():
                candidates.extend(iter_raw_files(raw_dir))
            candidates.extend(sorted(raw_dir.glob(f"*{request}*.BIN"), key=lambda p: p.name.lower()))
            candidates.extend(sorted(raw_dir.glob(f"*{request}*.bin"), key=lambda p: p.name.lower()))

        for bin_file in sorted(DATA_DIR.rglob("*.BIN"), key=lambda p: str(p).lower()):
            if request_l in bin_file.stem.lower():
                candidates.append(bin_file)
        for bin_file in sorted(DATA_DIR.rglob("*.bin"), key=lambda p: str(p).lower()):
            if request_l in bin_file.stem.lower():
                candidates.append(bin_file)

        return sorted(set(candidates), key=lambda p: str(p).lower())

    if not requests:
        for raw_dir in sorted(DATA_DIR.rglob("RAW"), key=lambda p: str(p).lower()):
            if raw_dir.is_dir():
                for file in iter_raw_files(raw_dir):
                    if file not in seen:
                        files.append(file)
                        seen.add(file)
        return files

    for request in requests:
        request_path = Path(request)
        if request_path.exists():
            matches = iter_raw_files(request_path)
            if not matches:
                matches = [request_path] if request_path.is_file() else []
        else:
            matches = _search_anywhere(request)
            if not matches:
                candidates = []
                candidates.append(DAQ_DIR / request)
                candidates.append(DATA_DIR / request)
                for cand in candidates:
                    if cand.exists():
                        matches.extend(iter_raw_files(cand))

        if not matches:
            raise SystemExit(f"No se encontraron archivos RAW para '{request}' en ninguna carpeta dentro de {DATA_DIR}")

        for file in matches:
            if file not in seen:
                files.append(file)
                seen.add(file)

    return sorted(files, key=lambda p: (str(p.parent.parent).lower(), p.name.lower()))


def main():
    """!
    @brief Funcion principal que genera el HTML con las waveforms medias de los runs seleccionados.

    @return None
    """
    parser = argparse.ArgumentParser(description="Waveform media de los archivos RAW de CoMPASS")
    parser.add_argument("runs", nargs="*", type=str, help="nombre del run o ruta al .BIN. Si se omite, usa todos los runs en DAQ/.")
    parser.add_argument("--max-events", type=int, default=DEFAULT_MAX_EVENTS, help=f"limitar eventos por archivo (por defecto {DEFAULT_MAX_EVENTS})")
    parser.add_argument("--all-events", action="store_true", help="usar todos los eventos del archivo (ignora --max-events)")
    parser.add_argument("--out", type=Path, default=OUT_HTML, help="HTML de salida")
    parser.add_argument("--no-open", action="store_true", help="no abrir el navegador")
    parser.add_argument("--dt-ns", type=float, default=SAMPLE_PERIOD_NS,
                        help=f"periodo de muestreo en ns, incluido el downsampling (por defecto {SAMPLE_PERIOD_NS})")
    args = parser.parse_args()

    files = resolve_input_files(args.runs)
    if not files:
        raise SystemExit(f"No hay archivos .bin en {DAQ_DIR}")

    max_events = None if args.all_events else args.max_events
    if max_events is not None and max_events <= 0:
        max_events = None

    results = []
    for path in files:
        try:
            mean, std, n, skipped = mean_waveform(path, max_events)
        except (ValueError, OSError, EOFError) as exc:
            print(f"Saltando {path}: {exc}")
            continue

        name = file_label(path)
        msg = f"{path.name}: {n} eventos, {len(mean)} muestras"
        if skipped:
            msg += f" ({skipped} eventos corruptos descartados)"
        print(msg)
        results.append((name, mean, std, n))

    if not results:
        raise SystemExit(f"No se encontraron waveforms validas en ninguna carpeta de {DATA_DIR}")

    items = [{"group": f"{name} (N={n})", "name": name, "mean": mean, "std": std}
             for name, mean, std, n in results]
    fig = waveform_figure(items, args.dt_ns, legend=False)
    fig.update_layout(title="Waveform media por archivo")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(args.out, include_plotlyjs=True)
    print(f"Guardado en {args.out}")
    if not args.no_open:
        webbrowser.open(args.out.as_uri())


if __name__ == "__main__":
    main()
