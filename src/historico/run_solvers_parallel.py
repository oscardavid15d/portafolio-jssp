"""
run_solvers_parallel.py - Ejecucion en PARALELO de solvers para JSSP (Timeout 300s)

Cada instancia se ejecuta en cada solver durante un MAXIMO de --timeout segundos
(por defecto 300). El limite lo impone MiniZinc (--time-limit, incluye compilacion
a FlatZinc + busqueda). Python agrega un margen de seguridad de 20 s y, si se
supera, mata el arbol de procesos completo (minizinc + solver hijo).

Uso piloto (12 instancias):
    python run_solvers_parallel.py --pilot

Uso completo:
    python run_solvers_parallel.py
"""

import argparse
import csv
import re
import signal
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

MINIZINC_CMD = r"C:\Program Files\MiniZinc\minizinc.exe"

SOLVER_IDS = {
    "chuffed": "org.chuffed.chuffed",
    "gecode":  "org.gecode.gecode",
    "cpsat":   "cp-sat",
}

# Margen de seguridad de Python sobre el limite interno de MiniZinc
PY_GUARD_SEC = 20
# Una corrida NO optima que termina antes de este % del timeout se marca como sospechosa
UMBRAL_INTERRUPCION = 0.95

IS_WINDOWS = sys.platform == "win32"

# En Windows, MiniZinc aplica --time-limit enviando CTRL_C_EVENT a TODA la consola.
# Si varios solvers comparten consola, el timeout de uno interrumpe a los demas.
# Solucion: cada minizinc se lanza en su PROPIA consola oculta (CREATE_NEW_CONSOLE),
# asi su CTRL_C solo llega a su propio solver hijo.
# (NO usar CREATE_NEW_PROCESS_GROUP: bloquea el CTRL_C y el solver nunca se detiene.)
if IS_WINDOWS:
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    CREATION_FLAGS = subprocess.CREATE_NEW_CONSOLE
else:
    CREATION_FLAGS = 0


def hidden_startupinfo():
    if not IS_WINDOWS:
        return None
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0  # SW_HIDE
    return si

csv_lock = threading.Lock()
log_lock = threading.Lock()


def kill_tree(pid: int):
    """Mata minizinc.exe y su proceso hijo (fzn-chuffed / fzn-gecode / fzn-cp-sat)."""
    if IS_WINDOWS:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                       capture_output=True)
    else:
        try:
            import os
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except Exception:
            pass


def parse_output(stdout: str, elapsed: float, timeout_sec: int):
    result = {
        "makespan":   None,
        "tiempo_sol": round(elapsed, 3),
        "optimo":     False,
        "estado":     "UNKNOWN",
    }

    matches = re.findall(r'makespan\s*=\s*(\d+)', stdout)
    if matches:
        result["makespan"] = int(matches[-1])
        result["estado"] = "SATISFIABLE"

    if "=====ERROR=====" in stdout:
        result["estado"] = "ERROR"
    elif "=====UNSATISFIABLE=====" in stdout:
        result["estado"] = "UNSATISFIABLE"
        result["makespan"] = None
    elif "==========" in stdout:
        result["optimo"] = True
        result["estado"] = "OPTIMAL"

    # Control de calidad: una corrida que no probo optimalidad (ni insatisfacibilidad)
    # deberia agotar el timeout. Si termino mucho antes, fue interrumpida o fallo.
    if result["estado"] in ("SATISFIABLE", "UNKNOWN") and elapsed < UMBRAL_INTERRUPCION * timeout_sec:
        result["estado"] = "INTERRUMPIDO"

    return result


def run_solver(model: Path, instance: Path, solver: str, solver_id: str, timeout_sec: int):
    # Mismas banderas que run_solvers.py (campaña de 15 s) para que los
    # experimentos sean comparables: -a (soluciones intermedias), -f (busqueda libre)
    cmd = [
        MINIZINC_CMD,
        "--solver", solver_id,
        "-a",
        "-f",
        "--time-limit", str(timeout_sec * 1000),   # MiniZinc usa milisegundos
        "--output-time",
        str(model),
        str(instance),
    ]

    start = time.perf_counter()
    returncode = None
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, encoding="utf-8", errors="replace",
                                creationflags=CREATION_FLAGS,
                                startupinfo=hidden_startupinfo())
        try:
            stdout, stderr = proc.communicate(timeout=timeout_sec + PY_GUARD_SEC)
            returncode = proc.returncode
        except subprocess.TimeoutExpired:
            kill_tree(proc.pid)
            stdout, stderr = proc.communicate()
            returncode = "KILLED_BY_PYTHON"
    except Exception as e:
        elapsed = time.perf_counter() - start
        return ({"makespan": None, "tiempo_sol": round(elapsed, 3), "optimo": False, "estado": "ERROR"},
                {"returncode": "EXCEPTION", "stderr": str(e)})

    elapsed = time.perf_counter() - start
    res = parse_output(stdout, elapsed, timeout_sec)
    diag = {"returncode": returncode, "stderr": (stderr or "").strip().replace("\n", " | ")[-500:]}
    return res, diag


def write_log(log_path: Path, instance: str, solver: str, res: dict, diag: dict):
    with log_lock:
        exists = log_path.exists()
        with open(log_path, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if not exists:
                w.writerow(["instancia", "solver", "estado", "tiempo", "makespan", "returncode", "stderr"])
            w.writerow([instance, solver, res["estado"], res["tiempo_sol"], res["makespan"],
                        diag["returncode"], diag["stderr"]])


def run_instance_all_solvers(args, instance: Path):
    """Ejecuta los 3 solvers (en secuencia) para una instancia. Corre en un hilo del pool."""
    row = {"instancia": instance.stem}
    resumen = []
    for solver_name, solver_id in SOLVER_IDS.items():
        res, diag = run_solver(args.model, instance, solver_name, solver_id, args.timeout)
        row[f"{solver_name}_makespan"] = res["makespan"]
        row[f"{solver_name}_tiempo"]   = res["tiempo_sol"]
        row[f"{solver_name}_optimo"]   = res["optimo"]
        row[f"{solver_name}_estado"]   = res["estado"]
        write_log(args.log, instance.stem, solver_name, res, diag)
        resumen.append(f"{solver_name}={res['estado']}({res['tiempo_sol']:.0f}s)")

    with csv_lock:
        file_exists = args.output.exists()
        with open(args.output, mode="a", newline="", encoding="utf-8") as csvfile:
            fieldnames = ["instancia"]
            for s in SOLVER_IDS:
                fieldnames.extend([f"{s}_makespan", f"{s}_tiempo", f"{s}_optimo", f"{s}_estado"])
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)

    alerta = " [REVISAR]" if any("INTERRUMPIDO" in r or "ERROR" in r for r in resumen) else ""
    print(f"[OK] {instance.stem}: {', '.join(resumen)}{alerta}", flush=True)
    return row


def main():
    parser = argparse.ArgumentParser(description="Ejecucion de solvers en paralelo")
    parser.add_argument("--model", type=Path, default=Path("jssp.mzn"))
    parser.add_argument("--instances", type=Path, default=Path("Instancias_dzn"))
    parser.add_argument("--output", type=Path, default=Path("resultados_solvers_300s.csv"))
    parser.add_argument("--log", type=Path, default=Path("log_ejecuciones_300s.csv"))
    parser.add_argument("--timeout", type=int, default=300, help="Timeout maximo por solver (s)")
    parser.add_argument("--workers", type=int, default=6, help="Instancias en paralelo")
    parser.add_argument("--pilot", action="store_true", help="Muestra piloto de 12 instancias")
    args = parser.parse_args()

    if not args.instances.exists():
        print(f"Carpeta {args.instances} no encontrada.")
        sys.exit(1)

    all_instances = sorted(args.instances.glob("*.dzn"))

    if args.pilot:
        pilot_names = ["ft06", "la01", "la05", "orb01", "swv01", "abz5",
                       "ta01js", "ta02js", "dmu01", "dmu02", "dmu10", "yn1"]
        instances = [p for p in all_instances if p.stem in pilot_names]
        faltantes = set(pilot_names) - {p.stem for p in instances}
        if faltantes:
            print(f"[AVISO] No se encontraron: {sorted(faltantes)}")
        print(f"--- MODO PILOTO ({len(instances)} instancias) ---")
    else:
        instances = all_instances

    if args.output.exists():
        with open(args.output, mode="r", encoding="utf-8") as csvfile:
            procesadas = {row["instancia"] for row in csv.DictReader(csvfile)}
        instances = [p for p in instances if p.stem not in procesadas]
        print(f"Retomando: {len(procesadas)} instancias ya estaban en {args.output}.")

    if not instances:
        print("No hay instancias nuevas por procesar.")
        sys.exit(0)

    print(f"Instancias a procesar: {len(instances)} | Workers: {args.workers} | "
          f"Timeout maximo por solver: {args.timeout} s")
    print("-" * 60, flush=True)

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(run_instance_all_solvers, args, inst): inst for inst in instances}
        for future in as_completed(futures):
            inst = futures[future]
            try:
                future.result()
            except Exception as exc:
                print(f"[ERROR] {inst.stem}: {exc}", flush=True)

    print("-" * 60)
    print(f"PROCESO FINALIZADO. Tiempo total: {(time.perf_counter() - t0) / 60:.2f} min")
    print(f"Resultados: {args.output}  |  Diagnostico: {args.log}")


if __name__ == "__main__":
    main()
