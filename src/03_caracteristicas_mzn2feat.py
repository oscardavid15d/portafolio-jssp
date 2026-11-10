"""
extract_features.py

Ejecuta mzn2feat sobre todas las instancias .dzn de una carpeta, usando
un modelo .mzn fijo, y junta los resultados en un único CSV
(una fila por instancia, una columna por feature).

IMPORTANTE: este script debe correr en un entorno donde 'mzn2feat' esté
instalado y disponible en el PATH (dentro del contenedor Docker de
sunny-cp, o tras una instalación manual exitosa).

Uso:
    python extract_features.py \
        --model jssp.mzn \
        --instances "Instancias dzn" \
        --output features.csv

    # Con timeout por instancia (recomendado para evitar que una instancia
    # problemática trabe todo el proceso):
    python extract_features.py --model jssp.mzn --instances "Instancias dzn" \
        --output features.csv --timeout 60
"""

import argparse
import csv
import subprocess
import sys
from pathlib import Path


def get_feature_names(model_path, mzn2feat_bin="mzn2feat"):
    """
    Intenta obtener los nombres/identificadores de las 95 features
    llamando a 'mzn2feat -p'. Si requiere -i, lo intenta con el modelo.
    Si todo falla, retorna None (se usarán nombres genéricos f1..fN).
    """
    # Intento 1: -p sin modelo
    try:
        result = subprocess.run(
            [mzn2feat_bin, "-p"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and result.stdout.strip():
            names = result.stdout.strip().split(",")
            if len(names) > 1:
                return [n.strip() for n in names]
    except Exception:
        pass

    # Intento 2: -p con -i (algunas versiones lo requieren)
    try:
        result = subprocess.run(
            [mzn2feat_bin, "-p", "-i", str(model_path)],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and result.stdout.strip():
            names = result.stdout.strip().split(",")
            if len(names) > 1:
                return [n.strip() for n in names]
    except Exception:
        pass

    return None


def extract_one(model_path, dzn_path, mzn2feat_bin="mzn2feat", timeout=60):
    """
    Ejecuta mzn2feat sobre una instancia y devuelve la lista de valores
    (floats/strings) o None si falla.
    """
    cmd = [mzn2feat_bin, "-i", str(model_path), "-d", str(dzn_path), "-o", "csv"]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return None, "timeout"
    except FileNotFoundError:
        return None, "mzn2feat no encontrado en el PATH"

    if result.returncode != 0:
        err = result.stderr.strip()[:200] if result.stderr else "error desconocido"
        return None, err

    raw = result.stdout.strip()
    if not raw:
        return None, "salida vacía"

    values = [v.strip() for v in raw.split(",")]
    return values, None


def main():
    parser = argparse.ArgumentParser(
        description="Extrae features con mzn2feat para todas las instancias JSSP (.dzn)"
    )
    parser.add_argument("--model", required=True, help="Ruta al modelo .mzn fijo (ej: jssp.mzn)")
    parser.add_argument("--instances", required=True, help="Carpeta con los archivos .dzn")
    parser.add_argument("--output", default="features.csv", help="Archivo CSV de salida")
    parser.add_argument("--mzn2feat-bin", default="mzn2feat", help="Ruta/nombre del ejecutable mzn2feat")
    parser.add_argument("--timeout", type=int, default=60, help="Timeout en segundos por instancia")
    args = parser.parse_args()

    model_path = Path(args.model)
    instances_dir = Path(args.instances)
    output_path = Path(args.output)

    if not model_path.exists():
        print(f"ERROR: no se encontró el modelo '{model_path}'")
        sys.exit(1)
    if not instances_dir.exists():
        print(f"ERROR: no se encontró la carpeta de instancias '{instances_dir}'")
        sys.exit(1)

    dzn_files = sorted(instances_dir.glob("*.dzn"))
    if not dzn_files:
        print(f"ERROR: no se encontraron archivos .dzn en '{instances_dir}'")
        sys.exit(1)

    print(f"Encontradas {len(dzn_files)} instancias .dzn")

    # Intentar obtener nombres de features
    feature_names = get_feature_names(model_path, args.mzn2feat_bin)

    rows = []
    failed = []

    for idx, dzn_path in enumerate(dzn_files, start=1):
        instance_name = dzn_path.stem
        print(f"[{idx}/{len(dzn_files)}] Procesando {instance_name}...", end=" ")

        values, error = extract_one(model_path, dzn_path, args.mzn2feat_bin, args.timeout)

        if values is None:
            print(f"✗ FALLÓ ({error})")
            failed.append((instance_name, error))
            continue

        print(f"✓ OK ({len(values)} features)")
        rows.append([instance_name] + values)

        # Si aún no tenemos nombres de features, generarlos genéricos
        # con el largo correcto detectado en la primera instancia exitosa
        if feature_names is None:
            feature_names = [f"feat_{i+1}" for i in range(len(values))]

    if not rows:
        print("\nERROR: ninguna instancia pudo procesarse. Revisa la instalación de mzn2feat.")
        sys.exit(1)

    # Escribir CSV final
    header = ["instance"] + (feature_names if feature_names else
                              [f"feat_{i+1}" for i in range(len(rows[0]) - 1)])

    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)

    print(f"\n{'='*50}")
    print(f"Completado: {len(rows)}/{len(dzn_files)} instancias procesadas correctamente")
    print(f"Resultado guardado en: {output_path}")

    if failed:
        print(f"\n{len(failed)} instancias fallaron:")
        for name, err in failed:
            print(f"  - {name}: {err}")
        fail_log = output_path.with_suffix(".failed.txt")
        with open(fail_log, "w") as f:
            for name, err in failed:
                f.write(f"{name}\t{err}\n")
        print(f"Detalle de fallos guardado en: {fail_log}")


if __name__ == "__main__":
    main()
