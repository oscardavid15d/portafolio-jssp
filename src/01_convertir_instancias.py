"""
01_convertir_instancias.py - Convierte las instancias de la OR-Library (.txt) al formato
de datos de MiniZinc (.dzn) que usa modelos/jssp.mzn.

Formato .txt: primera línea "n_trabajos n_maquinas"; luego una línea por trabajo con pares
"maquina duracion" en el orden de sus operaciones (máquinas numeradas desde 0).

Uso (desde la raíz del repositorio):
    python src/01_convertir_instancias.py [carpeta_txt] [carpeta_dzn]
Por defecto: instancias/txt -> instancias/dzn
"""
import sys
from pathlib import Path

src = Path(sys.argv[1] if len(sys.argv) > 1 else "instancias/txt")
dst = Path(sys.argv[2] if len(sys.argv) > 2 else "instancias/dzn")
dst.mkdir(parents=True, exist_ok=True)

for txt in sorted(src.glob("*.txt")):
    lineas = [l.strip() for l in txt.read_text().splitlines() if l.strip()]
    n, m = map(int, lineas[0].split())
    maquinas, duraciones = [], []
    for l in lineas[1:1 + n]:
        v = list(map(int, l.split()))
        maquinas.append(v[0::2])
        duraciones.append(v[1::2])
    fila = lambda M: " | ".join(", ".join(map(str, r)) for r in M)
    (dst / f"{txt.stem}.dzn").write_text(
        f"n_jobs = {n};\nn_machines = {m};\n"
        f"machines = [| {fila(maquinas)} |];\ndurations = [| {fila(duraciones)} |];\n")
    print(f"OK  {txt} -> {dst / (txt.stem + '.dzn')}")
