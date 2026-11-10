"""
ejecutor.py - Ejecuta automáticamente los experimentos del paquete.

No requiere ninguna decisión del operador: lee plan.csv y config.json, verifica el
entorno, ejecuta los bloques en orden, guarda cada resultado apenas termina (si se
interrumpe, al volver a ejecutarlo continúa donde quedó) y al final genera un .zip
con los resultados para enviar.

Uso normal: doble clic en EJECUTAR_CAMPANA.bat (Chuffed y Gecode, modelo con cotas),
EJECUTAR_CHUFFED_V2.bat (Chuffed con la estrategia de búsqueda del modelo) o
EJECUTAR_CPSAT.bat (CP-SAT con el modelo con cotas, referencia externa) o
EJECUTAR_MODELO_ORIGINAL.bat (Chuffed, Gecode y CP-SAT con el modelo original).
Opciones:
  --prueba-seca         límite de 3 s por ejecución y pocas ejecuciones por bloque;
                        resultados en la carpeta resultados_prueba_seca/
  --bloques B1 B2 ...   ejecutar solo esos bloques
  --minizinc RUTA       ruta a minizinc(.exe)
  --ignorar-versiones   continuar aunque las versiones de los solvers no coincidan
  --a-la-vez N          ejecutar N corridas a la vez en los bloques de campaña (D_*)
"""
import argparse
import csv
import hashlib
import json
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent.parent  # raíz del repositorio
IS_WINDOWS = sys.platform == "win32"
VERSION_EJECUTOR = "1.4"

# En Windows, MiniZinc aplica --time-limit enviando CTRL_C a toda la consola.
# Cada minizinc se lanza en su PROPIA consola oculta para que el límite de uno no
# interrumpa a los demás (mismo esquema que run_solvers_parallel.py).
if IS_WINDOWS:
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    CREATION_FLAGS = subprocess.CREATE_NEW_CONSOLE
else:
    CREATION_FLAGS = 0

PROCESOS_PROPIOS = ["minizinc.exe", "fzn-chuffed.exe", "fzn-gecode.exe", "fzn-cp-sat.exe"]
CAMPOS = ["id", "bloque", "rep", "instancia", "variante", "solver", "busqueda_libre", "limite_s",
          "modo", "makespan", "optimo", "estado", "tiempo_pared_s", "tiempo_minizinc_s",
          "returncode", "inicio", "fin", "validacion", "stderr", "trayectoria"]
lock = threading.Lock()


# ----------------------------------------------------------------------------- utilidades
def ahora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class Registro:
    def __init__(self, ruta):
        self.ruta = ruta

    def __call__(self, msg="", consola=True):
        linea = f"[{ahora()}] {msg}" if msg else ""
        if consola:
            print(msg, flush=True)
        with lock, open(self.ruta, "a", encoding="utf-8") as f:
            f.write(linea + "\n")


def mantener_despierto(activar=True):
    """Evita la suspensión del equipo mientras corre (sin cambiar la configuración de Windows)."""
    if not IS_WINDOWS:
        return
    try:
        import ctypes
        ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if activar else 0))
    except Exception:
        pass


def correr(cmd, timeout=60):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
        return (p.stdout or "") + (p.stderr or "")
    except Exception as e:
        return f"ERROR: {e}"


def fmt_h(seg):
    seg = max(0, int(seg))
    return f"{seg // 3600} h {(seg % 3600) // 60:02d} min"


def hidden_startupinfo():
    if not IS_WINDOWS:
        return None
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0
    return si


def matar_arbol(pid):
    if IS_WINDOWS:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
    else:
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except Exception:
            pass


# ----------------------------------------------------------------------------- entorno
def buscar_minizinc(arg):
    candidatos = [arg, os.environ.get("MINIZINC_PATH"), shutil.which("minizinc")]
    if IS_WINDOWS:
        candidatos += [r"C:\Program Files\MiniZinc\minizinc.exe",
                       r"C:\Program Files (x86)\MiniZinc\minizinc.exe",
                       os.path.expandvars(r"%LOCALAPPDATA%\Programs\MiniZinc\minizinc.exe")]
    for c in candidatos:
        if c and Path(c).exists():
            return str(Path(c))
    return None


def verificar_versiones(mzn, cfg, log):
    """Devuelve (ok, info). Compara las versiones de los solvers con las de la campaña original."""
    info = {"minizinc_version": correr([mzn, "--version"]).strip()}
    salida = correr([mzn, "--solvers-json"])
    try:
        solvers = {s["id"]: s.get("version", "?") for s in json.loads(salida)}
    except Exception:
        solvers = {}
        for sid in cfg["versiones_esperadas"]:
            m = re.search(re.escape(sid) + r"\s+([\w.]+)", correr([mzn, "--solvers"]))
            if m:
                solvers[sid] = m.group(1)
    info["solvers"] = {sid: solvers.get(sid, "NO ENCONTRADO") for sid in cfg["versiones_esperadas"]}
    ok = True
    for sid, esperado in cfg["versiones_esperadas"].items():
        real = solvers.get(sid)
        marca = "OK" if real == esperado else "DIFERENTE"
        if real != esperado:
            ok = False
        log(f"   {sid:22s} esperado {esperado:12s} encontrado {real or 'NO ENCONTRADO':12s} [{marca}]")
    if cfg.get("minizinc_esperado") and cfg["minizinc_esperado"] not in info["minizinc_version"]:
        log(f"   (aviso) versión de MiniZinc distinta de {cfg['minizinc_esperado']}: "
            f"{info['minizinc_version'].splitlines()[0] if info['minizinc_version'] else '?'}")
    return ok, info


def info_equipo():
    info = {"fecha": ahora(), "python": sys.version.split()[0], "plataforma": platform.platform(),
            "procesadores_logicos": os.cpu_count(), "version_ejecutor": VERSION_EJECUTOR}
    if IS_WINDOWS:
        ps = ("$c=Get-CimInstance Win32_Processor; $s=Get-CimInstance Win32_ComputerSystem; "
              "$m=Get-CimInstance Win32_PhysicalMemory; $o=Get-CimInstance Win32_OperatingSystem; "
              "'CPU=' + $c.Name; 'Nucleos=' + $c.NumberOfCores; 'Hilos=' + $c.NumberOfLogicalProcessors; "
              "'MaxMHz=' + $c.MaxClockSpeed; 'RAM_GB=' + [math]::Round($s.TotalPhysicalMemory/1GB,1); "
              "'RAM_MHz=' + (($m | Select-Object -ExpandProperty Speed) -join ','); "
              "'SO=' + $o.Caption + ' ' + $o.Version")
        for linea in correr(["powershell", "-NoProfile", "-Command", ps]).splitlines():
            if "=" in linea:
                k, v = linea.split("=", 1)
                info[k.strip()] = v.strip()
        info["plan_energia"] = correr(["powercfg", "/getactivescheme"]).strip()
    return info


def carga_cpu():
    """Porcentaje de uso de CPU durante ~3 s (None si no se puede medir)."""
    if IS_WINDOWS:
        out = correr(["powershell", "-NoProfile", "-Command",
                      "1..3 | % { (Get-CimInstance Win32_Processor | Measure-Object LoadPercentage -Average).Average;"
                      " Start-Sleep 1 } | Measure-Object -Average | % Average"], timeout=30)
        try:
            return float(out.strip().splitlines()[-1].replace(",", "."))
        except Exception:
            return None
    try:
        return os.getloadavg()[0] / (os.cpu_count() or 1) * 100
    except Exception:
        return None


def procesos_propios_activos():
    if not IS_WINDOWS:
        return []
    out = correr(["tasklist", "/FO", "CSV", "/NH"]).lower()
    return [p for p in PROCESOS_PROPIOS if f'"{p}"' in out]


def cerrar_procesos_propios(log):
    for p in procesos_propios_activos():
        log(f"   Cerrando proceso pendiente de una ejecución anterior: {p}")
        subprocess.run(["taskkill", "/F", "/IM", p], capture_output=True)


# ----------------------------------------------------------------------------- ejecución
def parsear(stdout, pared, limite):
    r = {"makespan": "", "optimo": False, "estado": "UNKNOWN", "tiempo_minizinc_s": ""}
    # trayectoria: cada solución mejorada con el instante (s) en que se encontró
    pares = []
    for bloque in stdout.split("----------"):
        m_ = re.search(r"makespan\s*=\s*(\d+)", bloque)
        t_ = re.search(r"time elapsed[:\s]+([\d.]+)\s*s", bloque)
        if m_ and t_:
            pares.append((m_.group(1), t_.group(1)))
    r["trayectoria"] = "|".join(f"{float(t):g}:{m}" for m, t in pares)
    ms = re.findall(r"makespan\s*=\s*(\d+)", stdout)
    if ms:
        r["makespan"], r["estado"] = int(ms[-1]), "SATISFIABLE"
    if "=====ERROR=====" in stdout:
        r["estado"] = "ERROR"
    elif "=====UNSATISFIABLE=====" in stdout:
        r["estado"], r["makespan"] = "UNSATISFIABLE", ""
    elif "==========" in stdout:
        r["optimo"], r["estado"] = True, "OPTIMAL"
    te = re.findall(r"time elapsed[:\s]+([\d.]+)\s*s", stdout, re.IGNORECASE)
    if te:
        r["tiempo_minizinc_s"] = float(te[-1])
    if r["estado"] in ("SATISFIABLE", "UNKNOWN") and pared < 0.95 * limite:
        r["estado"] = "INTERRUMPIDO"
    return r


_slots, _slot_lock = {}, threading.Lock()


def mascara_afinidad():
    """Un núcleo físico distinto por hilo trabajador: lógicos 2, 6, 10, 14 (núcleos 1, 3, 5, 7).
    En Windows los hilos lógicos 2k y 2k+1 son el mismo núcleo físico (SMT)."""
    with _slot_lock:
        k = _slots.setdefault(threading.get_ident(), len(_slots))
    return 1 << (2 + 4 * (k % 4))


def fijar_afinidad(pid, mascara):
    try:
        if IS_WINDOWS:
            import ctypes
            k32 = ctypes.windll.kernel32
            h = k32.OpenProcess(0x0200 | 0x0400, False, pid)  # SET_INFORMATION | QUERY_INFORMATION
            ok = k32.SetProcessAffinityMask(h, ctypes.c_size_t(mascara))
            k32.CloseHandle(h)
            return bool(ok)
        os.sched_setaffinity(pid, {mascara.bit_length() - 1})
        return True
    except Exception:
        return False


def ejecutar_uno(job, mzn, cfg, limite_override=None, afinidad=False):
    limite = int(limite_override or job["limite_s"])
    cmd = [mzn, "--solver", cfg["solver_ids"][job["solver"]], "-a"]
    if job["busqueda_libre"] == "1":
        cmd.append("-f")
    cmd += ["--time-limit", str(limite * 1000), "--output-time",
            str(RAIZ / "modelos" / job["modelo"]), str(RAIZ / "instancias" / job["dzn"])]
    inicio = ahora()
    t0 = time.perf_counter()
    rc = None
    try:
        kw = dict(stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                  encoding="utf-8", errors="replace")
        if IS_WINDOWS:
            kw.update(creationflags=CREATION_FLAGS, startupinfo=hidden_startupinfo())
        else:
            kw.update(start_new_session=True)
        p = subprocess.Popen(cmd, **kw)
        if afinidad:  # los procesos hijos (fzn-chuffed, fzn-gecode) heredan la afinidad
            fijar_afinidad(p.pid, mascara_afinidad())
        try:
            out, err = p.communicate(timeout=limite + cfg["margen_python_s"])
            rc = p.returncode
        except subprocess.TimeoutExpired:
            matar_arbol(p.pid)
            out, err = p.communicate()
            rc = "KILLED_BY_PYTHON"
    except Exception as e:
        out, err, rc = "", str(e), "EXCEPTION"
    pared = time.perf_counter() - t0
    r = parsear(out or "", pared, limite)
    fila = {k: job[k] for k in ["id", "bloque", "rep", "instancia", "variante", "solver",
                                "busqueda_libre", "limite_s", "modo"]}
    fila.update(limite_s=limite, makespan=r["makespan"], optimo=r["optimo"], estado=r["estado"],
                tiempo_pared_s=round(pared, 3), tiempo_minizinc_s=r["tiempo_minizinc_s"],
                returncode=rc, inicio=inicio, fin=ahora(), trayectoria=r["trayectoria"],
                stderr=(err or "").strip().replace("\n", " | ")[-400:])
    fila["validacion"] = validar(job, fila)
    return fila


def validar(job, fila):
    if fila["estado"] in ("ERROR", "UNKNOWN", "INTERRUMPIDO", "UNSATISFIABLE") or fila["makespan"] == "":
        return "FALLA"
    if job.get("esperado"):
        if not fila["optimo"]:
            return "FALLA_NO_OPTIMO"
        if str(fila["makespan"]) != job["esperado"]:
            return "FALLA_VALOR"
    if job["variante"] != "V0_actual":
        txt = (RAIZ / "instancias" / job["dzn"]).read_text()
        lb = int(re.search(r"\blb\s*=\s*(\d+)", txt).group(1))
        ub = int(re.search(r"\bub\s*=\s*(\d+)", txt).group(1))
        if not lb <= int(fila["makespan"]) <= ub:
            return "FALLA_COTAS"
    return "OK"


def ya_hechos(ruta):
    if not ruta.exists():
        return set()
    with open(ruta, encoding="utf-8") as f:
        return {r["id"] for r in csv.DictReader(f)}


def guardar(ruta, fila):
    with lock:
        nuevo = not ruta.exists()
        with open(ruta, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=CAMPOS)
            if nuevo:
                w.writeheader()
            w.writerow(fila)
            f.flush()
            os.fsync(f.fileno())


class Progreso:
    def __init__(self, restantes_s):
        self.restante = restantes_s
        self.t0 = time.time()

    def avanzar(self, est):
        with lock:
            self.restante = max(0, self.restante - est)

    def texto(self):
        return f"tiempo restante estimado: {fmt_h(self.restante)}"


def correr_bloque(nombre, jobs, mzn, cfg, dir_res, log, prog, limite_override, a_la_vez=None, afinidad=False):
    if nombre == "0_humo":  # la prueba inicial se repite en cada sesión, en su propio archivo
        ruta = dir_res / f"0_humo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    else:
        ruta = dir_res / f"{nombre}.csv"
    hechos = ya_hechos(ruta)
    pend = [j for j in jobs if j["id"] not in hechos]
    if not pend:
        log(f"== Bloque {nombre}: ya estaba completo ({len(jobs)} ejecuciones).")
        return True
    modo = pend[0]["modo"]
    workers = cfg["workers_paralelo"] if modo == "paralelo" else 1
    if a_la_vez and nombre.startswith("D_"):
        workers = a_la_vez
        modo = (f"paralelo{a_la_vez}" if a_la_vez > 1 else "serie") + ("_afinidad" if afinidad else "")
        for j in pend:
            j["modo"] = modo
    cpu = carga_cpu()
    log(f"== Bloque {nombre}: {len(pend)} de {len(jobs)} ejecuciones pendientes "
        f"| modo {modo}, {workers} a la vez | uso de CPU antes de empezar: "
        f"{'?' if cpu is None else f'{cpu:.0f}%'}")
    if cpu is not None and cpu > cfg["carga_cpu_maxima_pct"]:
        log(f"   AVISO: el equipo está ocupado ({cpu:.0f}% de CPU). Los tiempos medidos podrían verse "
            f"afectados. Si es posible, cierre otros programas. Se continúa en 60 s.")
        time.sleep(60)

    fallas = []
    n_total, hechos_ahora = len(pend), [0]

    def tarea_instancia(lista):
        for job in lista:
            fila = ejecutar_uno(job, mzn, cfg, limite_override, afinidad and nombre.startswith("D_"))
            guardar(ruta, fila)
            est = float(job["estimado_s"]) if not limite_override else limite_override
            prog.avanzar(est / workers)
            with lock:
                hechos_ahora[0] += 1
                k = hechos_ahora[0]
            marca = "" if fila["validacion"] == "OK" else f"  <-- {fila['validacion']}"
            if fila["validacion"] != "OK":
                fallas.append(fila)
            log(f"   [{k}/{n_total}] {job['instancia']:8s} {job['variante']:18s} {job['solver']:8s} "
                f"{fila['estado']:12s} makespan={fila['makespan']!s:6s} {fila['tiempo_pared_s']:8.1f} s"
                f"{marca}   | {prog.texto()}")
        return True

    if workers == 1:
        tarea_instancia(pend)
    else:
        grupos = {}
        for j in pend:
            grupos.setdefault(j["instancia"], []).append(j)
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = [ex.submit(tarea_instancia, g) for g in grupos.values()]
            for f in as_completed(futs):
                f.result()
    if fallas:
        log(f"   Bloque {nombre}: {len(fallas)} ejecuciones con alguna observación (quedan registradas).")
    return not (nombre == "0_humo" and fallas)


def empaquetar(dir_res, log):
    prefijo = "PRUEBA_SECA_resultados" if dir_res.name.endswith("prueba_seca") else "RESULTADOS"
    destino = dir_res.parent / f"{prefijo}_{datetime.now().strftime('%Y%m%d_%H%M')}.zip"
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(dir_res.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(dir_res.parent))
    h = hashlib.sha256(destino.read_bytes()).hexdigest()
    (destino.with_suffix(".sha256.txt")).write_text(f"{h}  {destino.name}\n")
    log(f"Archivo de resultados: {destino.name}")
    return destino


# ----------------------------------------------------------------------------- principal
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prueba-seca", action="store_true")
    ap.add_argument("--bloques", nargs="+")
    ap.add_argument("--minizinc")
    ap.add_argument("--ignorar-versiones", action="store_true")
    ap.add_argument("--a-la-vez", type=int)
    ap.add_argument("--afinidad", action="store_true")
    a = ap.parse_args()

    cfg = json.loads((AQUI / "config.json").read_text(encoding="utf-8"))
    plan = list(csv.DictReader(open(AQUI / "plan.csv", encoding="utf-8")))
    original = bool(a.bloques) and "D_original" in a.bloques
    carpeta = "campana_modelo_original_dual" if original else "campana_cotas"
    dir_res = RAIZ / "resultados" / ("prueba_seca" if a.prueba_seca else carpeta)
    dir_res.mkdir(parents=True, exist_ok=True)
    log = Registro(dir_res / "registro.txt")
    limite_override = 3 if a.prueba_seca else None

    print("=" * 78)
    if original:
        print("  CAMPAÑA CON EL MODELO ORIGINAL (Chuffed, Gecode y CP-SAT)")
    else:
        print("  CAMPAÑA PORTAFOLIO DUAL (Chuffed + Gecode, modelo con cotas)")
    print("  No cierre esta ventana. Si se cierra o se apaga el equipo, vuelva a hacer")
    print("  doble clic en el mismo .bat: continuará donde quedó.")
    print("=" * 78, flush=True)
    log(f"Inicio de sesión (ejecutor {VERSION_EJECUTOR}{', PRUEBA SECA' if a.prueba_seca else ''})", consola=False)

    mzn = buscar_minizinc(a.minizinc)
    if not mzn:
        log("ERROR: no se encontró MiniZinc. Instálelo o use --minizinc RUTA.")
        return 2
    log(f"MiniZinc: {mzn}")
    log("Verificando versiones de los solvers...")
    usados = {cfg["solver_ids"][j["solver"]] for j in plan if j["bloque"] in (a.bloques or cfg["bloques"])}
    cfg_v = dict(cfg, versiones_esperadas={k: v for k, v in cfg["versiones_esperadas"].items() if k in usados})
    ok, versiones = verificar_versiones(mzn, cfg_v, log)
    if not ok and not a.ignorar_versiones:
        log("ERROR: las versiones de los solvers no coinciden con las de los experimentos originales.")
        log("No se ejecutó nada. Revise resultados/registro.txt.")
        return 3
    eq = info_equipo()
    eq.update(versiones)
    (dir_res / f"equipo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json").write_text(
        json.dumps(eq, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"Equipo: {eq.get('CPU', platform.processor())} | RAM {eq.get('RAM_GB', '?')} GB | "
        f"{eq.get('SO', platform.platform())}")
    cerrar_procesos_propios(log)
    mantener_despierto(True)

    bloques = a.bloques or cfg["bloques"]
    por_bloque = {b: [j for j in plan if j["bloque"] == b] for b in bloques}
    if a.prueba_seca:  # pocas ejecuciones por bloque, cubriendo todas las variantes
        for b, js in por_bloque.items():
            vistos, sel = set(), []
            insts = list(dict.fromkeys(j["instancia"] for j in js))
            if any(j["variante"] != "V0_actual" for j in js) and len(insts) > 2:
                elegidas = {insts[0], insts[len(insts) // 2], insts[-1]}
                por_bloque[b] = [j for j in js if j["instancia"] in elegidas]
                continue
            for j in js:
                clave = (j["variante"], j["solver"])
                if clave not in vistos or len(sel) < 4:
                    vistos.add(clave)
                    sel.append(j)
            por_bloque[b] = sel
    restante = 0.0
    for b, js in por_bloque.items():
        hechos = ya_hechos(dir_res / f"{b}.csv")
        w = cfg["workers_paralelo"] if js and js[0]["modo"] == "paralelo" else 1
        if a.a_la_vez and b.startswith("D_"):
            w = a.a_la_vez
        restante += sum((limite_override or float(j["estimado_s"])) for j in js if j["id"] not in hechos) / w
    prog = Progreso(restante)
    log(f"Bloques: {', '.join(bloques)} | {prog.texto()}")

    try:
        for b in bloques:
            if not correr_bloque(b, por_bloque[b], mzn, cfg, dir_res, log, prog, limite_override, a.a_la_vez, a.afinidad):
                log("ERROR: la prueba inicial (bloque 0_humo) falló. No se ejecutaron los experimentos largos.")
                log("Revise la carpeta resultados.")
                empaquetar(dir_res, log)
                return 4
    finally:
        mantener_despierto(False)

    destino = empaquetar(dir_res, log)
    print()
    print("#" * 78)
    print("#  TERMINADO. Todos los experimentos se completaron.")
    print(f"#  Copia comprimida de los resultados: {destino.name}")
    print(f"#  (está en la carpeta {destino.parent})")
    print("#" * 78, flush=True)
    log("Sesión terminada: TODO COMPLETO", consola=False)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\nERROR INESPERADO: {e}\nRevise la carpeta 'resultados'.")
        try:
            with open(RAIZ / "resultados" / "campana_cotas" / "registro.txt", "a", encoding="utf-8") as f:
                import traceback
                f.write(f"[{ahora()}] ERROR INESPERADO\n{traceback.format_exc()}\n")
        except Exception:
            pass
        sys.exit(1)
