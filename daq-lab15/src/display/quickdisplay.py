"""
Visualizacion rapida de los .bin de CoMPASS guardados en data/.

Para cada archivo calcula la waveform media de todos los eventos y genera
una pagina HTML interactiva (plotly) que se abre en el navegador.

Uso:
    python src/display/quickdisplay.py                 # todos los .bin de data/
    python src/display/quickdisplay.py run_1.BIN ...   # archivos concretos
    python src/display/quickdisplay.py --max-events 10000 --no-open
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
OUT_HTML = DATA_DIR / "quickdisplay.html"

# DT2730: 500 MS/s (2 ns) con WAVE_DOWNSAMPLING_X2 en CoMPASS -> 4 ns por muestra
SAMPLE_PERIOD_NS = 4.0

# Bits del header (0xCAEx)
HAS_ENERGY_CH = 1 << 0
HAS_ENERGY_CAL = 1 << 1
HAS_ENERGY_SHORT = 1 << 2
HAS_WAVEFORM = 1 << 3


def read_header(path):
    """Lee el header y devuelve (n_samples, dtype del evento)."""
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
    """Posiciones de inicio de cada evento valido.

    Algunos archivos tienen eventos truncados (bloques perdidos al escribir),
    asi que no se puede asumir tamano fijo: se recorre evento a evento y, si
    uno no cuadra, se busca el siguiente por la firma wave_code + n_samples.
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
    """Devuelve (waveform media, desviacion estandar, n eventos, n eventos descartados)."""
    n_samples, dtype = read_header(path)
    with open(path, "rb") as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
        offsets, skipped = event_offsets(mm, dtype)
        if max_events:
            offsets = offsets[:max_events]
        mean, std = _accumulate(np.frombuffer(mm, dtype=np.uint8), offsets, dtype, n_samples)
    return mean, std, len(offsets), skipped


def _accumulate(raw, offsets, dtype, n_samples):
    """Media y desviacion estandar muestra a muestra de los eventos dados."""
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
    """Ordena run_2 antes que run_10."""
    tail = path.stem.rsplit("_", 1)[-1]
    return (path.stem.rsplit("_", 1)[0], int(tail) if tail.isdigit() else 0)


def main():
    parser = argparse.ArgumentParser(description="Waveform media de los .bin de CoMPASS")
    parser.add_argument("files", nargs="*", type=Path, help="archivos .bin (por defecto todos los de data/)")
    parser.add_argument("--max-events", type=int, default=None, help="limitar eventos por archivo")
    parser.add_argument("--out", type=Path, default=OUT_HTML, help="HTML de salida")
    parser.add_argument("--no-open", action="store_true", help="no abrir el navegador")
    parser.add_argument("--dt-ns", type=float, default=SAMPLE_PERIOD_NS,
                        help=f"periodo de muestreo en ns, incluido el downsampling (por defecto {SAMPLE_PERIOD_NS})")
    args = parser.parse_args()

    files = [f if f.exists() else DATA_DIR / f for f in args.files]
    if not files:
        files = sorted((p for p in DATA_DIR.iterdir() if p.suffix.lower() == ".bin"), key=run_sort_key)
    if not files:
        raise SystemExit(f"No hay archivos .bin en {DATA_DIR}")

    results = []
    for path in files:
        mean, std, n, skipped = mean_waveform(path, args.max_events)
        name = path.stem.split("_", 3)[-1] if "_" in path.stem else path.stem
        msg = f"{path.name}: {n} eventos, {len(mean)} muestras"
        if skipped:
            msg += f" ({skipped} eventos corruptos descartados)"
        print(msg)
        results.append((name, mean, std, n))

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
