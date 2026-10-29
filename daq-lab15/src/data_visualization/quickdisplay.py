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
import webbrowser
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
DAQ_DIR = DATA_DIR / "CoMPASS256_ExternalTrigger" / "DAQ"
OUT_HTML = DATA_DIR / "quickdisplay.html"
DEFAULT_MAX_EVENTS = 100

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

        run_name = path.parent.parent.name if path.parent.name == "RAW" else path.parent.name
        name = f"{run_name}:{path.stem}"
        msg = f"{path.name}: {n} eventos, {len(mean)} muestras"
        if skipped:
            msg += f" ({skipped} eventos corruptos descartados)"
        print(msg)
        results.append((name, mean, std, n))

    if not results:
        raise SystemExit(f"No se encontraron waveforms validas en ninguna carpeta de {DATA_DIR}")

    # Una grafica por archivo, en una cuadricula de 2 columnas
    cols = 1 if len(results) == 1 else 2
    rows = -(-len(results) // cols)
    fig = make_subplots(
        rows=rows, cols=cols,
        subplot_titles=[f"{name} (N={n})" for name, _, _, n in results],
        vertical_spacing=0.25 / rows, horizontal_spacing=0.08,
    )
    for i, (name, mean, std, n) in enumerate(results):
        row, col = i // cols + 1, i % cols + 1
        t_us = np.arange(len(mean)) * args.dt_ns / 1000
        fig.add_trace(go.Scatter(
            x=t_us, y=mean, mode="lines", name=name, showlegend=False,
            customdata=std,
            hovertemplate="t %{x:.3f} µs<br>media %{y:.1f}<br>σ %{customdata:.1f}<extra></extra>",
        ), row=row, col=col)
        fig.update_xaxes(title_text="Tiempo (µs)", row=row, col=col)
        fig.update_yaxes(title_text="ADC (ch)", row=row, col=col)

    fig.update_layout(
        title="Waveform media por archivo",
        height=350 * rows,
        template="plotly_white",
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(args.out, include_plotlyjs=True)
    print(f"Guardado en {args.out}")
    if not args.no_open:
        webbrowser.open(args.out.as_uri())


if __name__ == "__main__":
    main()
