"""
07_portafolios.py - Evaluación de portafolios con validación leave-one-out (LOO).

Cada instancia se resuelve con un presupuesto total de T = 300 s, usando lo aprendido en las
otras 235. El resultado de un schedule se simula de forma exacta con las trayectorias: si una
configuración recibe t segundos, su resultado es la mejor solución que tenía a los t segundos
(o la cota superior, si no tenía ninguna). Las configuraciones de un schedule se ejecutan una
tras otra y de forma independiente; el resultado es la mejor solución entre todas.

Métodos:
  Individual      cada configuración sola con 300 s.
  SBS             la mejor configuración individual en el entrenamiento (gap medio).
  Regla tamaño    Gecode si n*m >= umbral, si no Chuffed; umbral aprendido en el entrenamiento.
  Estático        un mismo schedule para todas: Gecode x s y luego Chuffed 300-x s;
                  x elegido en el entrenamiento.
  WTA k-NN        Winner Takes All: la configuración con menor gap medio entre los k vecinos.
  SUNNY k-NN      SUNNY (Amadini et al.) adaptado a optimización: entre los k vecinos, el
                  subconjunto mínimo de configuraciones que alcanza el mejor valor en más
                  vecinos; tiempo proporcional a los vecinos que cubre cada una, el resto a la
                  configuración de respaldo (mejor gap medio entre los vecinos); orden por
                  tiempo medio en alcanzar ese valor.
  VBS             oráculo: la mejor configuración de cada instancia, con 300 s.

Métricas: gap medio frente a BKS, óptimos probados, PAR10 y fracción de la brecha SBS-VBS
cerrada = (gap SBS - gap método) / (gap SBS - gap VBS).
Uso (desde la raíz del repositorio): python src/07_portafolios.py
"""
import itertools
import numpy as np, pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from comun import *

I = cargar_instancias()
C = cargar_corridas()
CFG = [c for c in ['chuffed_v1', 'gecode_v1', 'chuffed_v2'] if c in C]
NT = I[~I.trivial].copy()
inst = list(NT.index)
UB = NT['ub'].to_dict(); BKS = NT['bks'].to_dict()

# ---------------------------------------------------------------- simulación de un schedule
def simular(i, schedule):
    """schedule: lista de (configuración, segundos). Devuelve (makespan, óptimo, tiempo PAR10)."""
    mejor, opt, t_opt, acum = UB[i], False, PENAL, 0.0
    for c, t in schedule:
        if t <= 0:
            continue
        mejor = min(mejor, valor_en(C[c], i, t, UB[i]))
        if not opt and optimo_en(C[c], i, t):
            opt, t_opt = True, acum + C[c].at[i, 't_fin']
        acum += t
    return mejor, opt, t_opt

# tablas completas a 300 s (para entrenar los métodos)
MS = pd.DataFrame({c: [simular(i, [(c, LIMITE)])[0] for i in inst] for c in CFG}, index=inst)
GAP = MS.apply(lambda col: gap(col, NT['bks']))
BEST = MS.min(axis=1)
# tiempo en alcanzar el mejor valor del portafolio (para ordenar el schedule de SUNNY)
def t_alcanza(c, i):
    obj = BEST[i]
    if MS.at[i, c] > obj:
        return np.inf
    if obj == UB[i] and not any(m <= obj for _, m in C[c].at[i, 'tray']):
        return 0.0
    return min(t for t, m in C[c].at[i, 'tray'] if m <= obj)
TREACH = pd.DataFrame({c: [t_alcanza(c, i) for i in inst] for c in CFG}, index=inst)

# ---------------------------------------------------------------- métodos
def sbs(tr):
    return GAP.loc[tr].mean().idxmin()

def regla_tamano(tr, te):
    """Una configuración para las instancias pequeñas y otra para las grandes: se eligen el par y
    el umbral de número de operaciones que minimizan el gap medio del entrenamiento."""
    ops = NT['ops']
    mejores = []
    for chica, grande in itertools.permutations(CFG, 2):
        for u in sorted(set(ops.loc[tr])) + [np.inf]:
            sel = np.where(ops.loc[tr] >= u, grande, chica)
            mejores.append((GAP.loc[tr].values[np.arange(len(tr)), [CFG.index(s) for s in sel]].mean(), u, chica, grande))
    _, u, chica, grande = min(mejores, key=lambda r: r[:2])
    return [(grande if ops[te] >= u else chica, LIMITE)]

GRID_X = [0, 2, 5, 10, 15, 20, 30, 45, 60, 90, 120, 150, 200, 300]
GRID_Y = [30, 60, 90, 120, 150, 180]
def candidatos_estaticos():
    """Schedules fijos candidatos: (1) Gecode x s + Chuffed el resto, como en la versión de dos
    configuraciones; (2) si hay más configuraciones, todo par ordenado (a x s, b el resto) y los
    tríos (Gecode 2 s, a y s, b el resto)."""
    cands = [(('gecode_v1', x), ('chuffed_v1', LIMITE - x)) for x in GRID_X]
    if len(CFG) > 2:
        for a, b in itertools.permutations(CFG, 2):
            cands += [((a, x), (b, LIMITE - x)) for x in GRID_X if 0 < x < LIMITE]
        otros = [c for c in CFG if c != 'gecode_v1']
        for a, b in itertools.permutations(otros, 2):
            cands += [(('gecode_v1', 2), (a, y), (b, LIMITE - 2 - y)) for y in GRID_Y]
    return list(dict.fromkeys(cands))
CANDS = candidatos_estaticos()
_cache_est = {}
def estatico_gap(s):
    if s not in _cache_est:
        _cache_est[s] = pd.Series({i: gap(simular(i, list(s))[0], BKS[i]) for i in inst})
    return _cache_est[s]
def estatico(tr, te):
    return list(min(CANDS, key=lambda s: estatico_gap(s).loc[tr].mean()))

def vecinos(Xs_tr, xs_te, tr, k):
    d = np.sqrt(((Xs_tr - xs_te) ** 2).sum(axis=1))
    return [tr[j] for j in np.argsort(d, kind='stable')[:k]]

def wta(nb):
    return [(GAP.loc[nb].mean().idxmin(), LIMITE)]

def sunny(nb):
    k = len(nb)
    cubre = {c: set(j for j in nb if MS.at[j, c] <= BEST[j]) for c in CFG}
    mejor_sub, mejor_clave = None, None
    for r in range(1, len(CFG) + 1):
        for sub in itertools.combinations(CFG, r):
            cub = set().union(*(cubre[c] for c in sub))
            tiempo = sum(TREACH.loc[list(cubre[c]), c].sum() for c in sub)
            clave = (-len(cub), r, tiempo)
            if mejor_clave is None or clave < mejor_clave:
                mejor_sub, mejor_clave = sub, clave
    sub = list(mejor_sub)
    cub = set().union(*(cubre[c] for c in sub))
    respaldo = GAP.loc[nb].mean().idxmin()
    slots = {c: len(cubre[c]) for c in sub}
    slots[respaldo] = slots.get(respaldo, 0) + (k - len(cub))
    total = sum(slots.values())
    orden = sorted(slots, key=lambda c: TREACH.loc[list(cubre[c]) or nb, c].replace(np.inf, LIMITE).mean())
    return [(c, LIMITE * slots[c] / total) for c in orden if slots[c] > 0]

# ---------------------------------------------------------------- evaluación LOO
def evaluar(nombre, fn_sched):
    filas = []
    for i in inst:
        tr = [j for j in inst if j != i]
        s = fn_sched(tr, i)
        m, o, t = simular(i, s)
        filas.append(dict(metodo=nombre, instancia=i, makespan=m, optimo=o, t=t, gap=gap(m, BKS[i]),
                          schedule=' + '.join(f'{NOMBRES[c]} {d:.0f}s' for c, d in s if d > 0)))
    return filas

def con_knn(fn, conjunto, k):
    X = cargar_caracteristicas(conjunto).loc[inst]
    def f(tr, te):
        Xs_tr, xs_te = escalar(X.loc[tr], X.loc[[te]])
        return fn(vecinos(Xs_tr, xs_te[0], tr, k))
    return f

R = []
for c in CFG:
    R += evaluar(NOMBRES[c], lambda tr, te, c=c: [(c, LIMITE)])
R += evaluar('SBS', lambda tr, te: [(sbs(tr), LIMITE)])
R += evaluar('Regla por tamaño', regla_tamano)
R += evaluar('Schedule estático', estatico)
K = int(round(np.sqrt(len(inst) - 1)))            # k = raíz del tamaño de entrenamiento (SUNNY)
for conj in ['mzn2feat', 'propias', 'ambas']:
    R += evaluar(f'WTA k-NN ({conj})', con_knn(wta, conj, K))
    R += evaluar(f'SUNNY ({conj})', con_knn(sunny, conj, K))
for i in inst:
    c = MS.loc[i].idxmin()
    m, o, t = MS.at[i, c], any(optimo_en(C[x], i, LIMITE) for x in CFG), \
        min(C[x].at[i, 't_fin'] if optimo_en(C[x], i, LIMITE) else PENAL for x in CFG)
    R.append(dict(metodo='VBS', instancia=i, makespan=m, optimo=o, t=t, gap=gap(m, BKS[i]), schedule=NOMBRES[c]))
D = pd.DataFrame(R)
D.to_csv(SALIDAS / 'portafolios_por_instancia.csv', index=False)

res = D.groupby('metodo', sort=False).agg(gap_medio=('gap', 'mean'), optimos=('optimo', 'sum'), par10=('t', 'mean'))
g_sbs, g_vbs = res.at['SBS', 'gap_medio'], res.at['VBS', 'gap_medio']
res['brecha_cerrada_%'] = 100 * (g_sbs - res['gap_medio']) / (g_sbs - g_vbs)
res['mejor_que_SBS'] = [int((D[D.metodo == m].set_index('instancia')['makespan'] <
                             D[D.metodo == 'SBS'].set_index('instancia')['makespan']).sum()) for m in res.index]
res['peor_que_SBS'] = [int((D[D.metodo == m].set_index('instancia')['makespan'] >
                            D[D.metodo == 'SBS'].set_index('instancia')['makespan']).sum()) for m in res.index]
res.round(3).to_csv(SALIDAS / 'portafolios_resumen.csv')

# sensibilidad a k (características: ambas)
sens = []
for k in [3, 5, 7, 10, K, 20, 30]:
    for nombre, fn in [('WTA', wta), ('SUNNY', sunny)]:
        d = pd.DataFrame(evaluar(nombre, con_knn(fn, 'ambas', k)))
        sens.append(dict(metodo=nombre, k=k, gap_medio=d.gap.mean(), optimos=int(d.optimo.sum()), par10=d.t.mean()))
pd.DataFrame(sens).round(3).to_csv(SALIDAS / 'portafolios_sensibilidad_k.csv', index=False)

# figura
orden = [m for m in res.index if m not in ('SBS',)]
fig, ax = plt.subplots(figsize=(8, 4.5))
cols = ['#b8b5aa' if m in [NOMBRES[c] for c in CFG] else '#2e9e5b' if m == 'VBS' else '#2a78d6' for m in orden]
ax.barh(orden[::-1], res.loc[orden[::-1], 'gap_medio'], color=cols[::-1])
ax.axvline(g_sbs, color='#6b7280', ls='--', lw=1); ax.axvline(g_vbs, color='#2e9e5b', ls='--', lw=1)
lo = res['gap_medio'].min() - 1; ax.set_xlim(lo, res['gap_medio'].max() + 0.5)
ax.set_xlabel('Gap medio frente a BKS (%) — validación leave-one-out'); ax.spines[['top', 'right']].set_visible(False)
fig.tight_layout(); fig.savefig(SALIDAS / 'figuras/portafolios_gap.png', dpi=200); plt.close(fig)

print(f'k = {K}; instancias = {len(inst)}; configuraciones = {CFG}\n')
print(res.round(2).to_string())
print('\nSensibilidad a k:\n', pd.DataFrame(sens).round(2).to_string(index=False))
