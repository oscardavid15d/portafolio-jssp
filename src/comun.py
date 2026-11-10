"""
comun.py - Carga y utilidades compartidas por los scripts de análisis (06, 07, 08, 09).

Configuraciones (miembros posibles del portafolio):
  chuffed_v1  Chuffed, modelo con cotas, búsqueda libre        (resultados/campana_cotas/D_campana.csv)
  gecode_v1   Gecode,  modelo con cotas, búsqueda libre        (resultados/campana_cotas/D_campana.csv)
  chuffed_v2  Chuffed, modelo con cotas y estrategia de búsqueda (resultados/campana_cotas/D_chuffed_v2.csv)
  cpsat_v1    CP-SAT, modelo con cotas: referencia externa, no es miembro del portafolio (resultados/campana_cotas/D_cpsat.csv)

Convenciones:
  - Si una configuración no encuentra solución, su resultado es la cota superior (ub): la solución
    de la heurística, que el portafolio siempre tiene.
  - En las instancias con lb = ub el óptimo queda probado sin ejecutar solvers; se reportan aparte.
  - El tiempo de cada solución es el que informa MiniZinc (--output-time), incluida la compilación.
  - Gap(%) = 100 * (makespan - BKS) / BKS.
"""
import csv, re
from pathlib import Path
import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent          # raíz del repositorio
RES = RAIZ / 'resultados'
RUTAS = {
    'cotas':    RAIZ / 'instancias/cotas.csv',
    'bks':      RAIZ / 'instancias/bks.csv',
    'original': RES / 'campana_modelo_original/resultados_solvers_300s.csv',
    'campana':  RES / 'campana_cotas/D_campana.csv',
    'v2':       RES / 'campana_cotas/D_chuffed_v2.csv',
    'cpsat':    RES / 'campana_cotas/D_cpsat.csv',      # referencia externa
    'mzn2feat': RES / 'caracteristicas/mzn2feat_modelo_original.csv',
    'meta_mzn2feat': RES / 'campana_modelo_original/metadata_caracteristicas.csv',
    'propias':  RES / 'caracteristicas/propias.csv',
}
SALIDAS = RES / 'analisis'
LIMITE = 300.0
PENAL = 10 * LIMITE       # PAR10
NOMBRES = {'chuffed_v1': 'Chuffed', 'gecode_v1': 'Gecode', 'chuffed_v2': 'Chuffed V2', 'cpsat_v1': 'CP-SAT'}


def familia(i):
    return re.match(r'[a-z]+', i).group(0)


def cargar_instancias():
    cot = pd.read_csv(RUTAS['cotas']).set_index('instancia')
    bks = pd.read_csv(RUTAS['bks'])
    bks['instancia'] = bks['inst.id'].where(~bks['inst.id'].str.startswith('ta'), bks['inst.id'] + 'js')
    bks = bks.set_index('instancia')['inst.bks'].astype(float)
    df = cot.copy()
    df['bks'] = bks.reindex(df.index)
    df['familia'] = [familia(i) for i in df.index]
    df['tamano'] = df['n'].astype(str) + 'x' + df['m'].astype(str)
    df['ops'] = df['n'] * df['m']
    df['trivial'] = df['lb'] == df['ub']          # lb = ub: óptimo probado por las cotas
    return df


def _trayectoria(txt):
    pares = []
    for p in str(txt or '').split('|'):
        if ':' in p:
            t, m = p.split(':')
            pares.append((float(t), int(m)))
    return pares


def cargar_corridas():
    """dict configuración -> DataFrame por instancia."""
    filas = list(csv.DictReader(open(RUTAS['campana'], encoding='utf-8')))
    for k in ('v2', 'cpsat'):
        if RUTAS[k].exists():
            filas += list(csv.DictReader(open(RUTAS[k], encoding='utf-8')))
    out = {}
    for r in filas:
        cfg = r['solver'] + ('_v2' if r['variante'] == 'V2_cotas_busqueda' else '_v1')
        tz = float(r['tiempo_minizinc_s'] or r['tiempo_pared_s'])
        out.setdefault(cfg, []).append(dict(
            instancia=r['instancia'], makespan=int(r['makespan']) if r['makespan'] else np.nan,
            optimo=r['optimo'] == 'True', estado=r['estado'], t_pared=float(r['tiempo_pared_s']),
            t_fin=tz, tray=_trayectoria(r['trayectoria'])))
    return {k: pd.DataFrame(v).set_index('instancia') for k, v in out.items()}


def cargar_original():
    """Campaña con el modelo original (jssp.mzn): makespan, óptimo y tiempo por solver."""
    o = pd.read_csv(RUTAS['original']).set_index('instancia')
    return o


def valor_en(c, inst, t, ub):
    """Mejor makespan de la configuración c en la instancia antes del instante t (o ub)."""
    r = c.loc[inst]
    mejor = ub
    for ti, m in r['tray']:
        if ti <= t:
            mejor = min(mejor, m)
    return mejor


def optimo_en(c, inst, t):
    r = c.loc[inst]
    return bool(r['optimo']) and r['t_fin'] <= t


def gap(m, b):
    return 100.0 * (m - b) / b


def cargar_caracteristicas(conjunto='ambas'):
    """Características por instancia (sin normalizar).
    'mzn2feat': las 65 activas de mzn2feat (modelo original); 'propias': las 20 propias del JSSP;
    'ambas': la unión. Los valores no numéricos (-nan, inf) quedan como NaN."""
    partes = []
    if conjunto in ('mzn2feat', 'ambas'):
        f = pd.read_csv(RUTAS['mzn2feat']).set_index('instance')
        meta = pd.read_csv(RUTAS['meta_mzn2feat'])
        act = meta.loc[meta['estado'] == 'ACTIVA', 'feature'].tolist()
        f = f[act].apply(pd.to_numeric, errors='coerce').replace([np.inf, -np.inf], np.nan)
        partes.append(f.add_prefix('mz_'))
    if conjunto in ('propias', 'ambas'):
        partes.append(pd.read_csv(RUTAS['propias']).set_index('instancia'))
    X = pd.concat(partes, axis=1)
    X.index.name = 'instancia'
    return X


def escalar(Xtr, Xte):
    """Imputa con la mediana y lleva cada característica a [-1, 1] con el mínimo y máximo del
    conjunto de entrenamiento (como en SUNNY). Devuelve arrays."""
    med = Xtr.median()
    Xtr = Xtr.fillna(med); Xte = Xte.fillna(med)
    lo, hi = Xtr.min(), Xtr.max()
    rango = (hi - lo).replace(0, 1.0)
    f = lambda X: (2 * (X - lo) / rango - 1).clip(-1, 1).values
    return f(Xtr), f(Xte)
