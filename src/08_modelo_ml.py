"""
08_modelo_ml.py - Schedule construido con modelos de aprendizaje automático (validación LOO).

Configuraciones: Chuffed, Gecode y, si existen sus resultados, Chuffed V2 (modelo con estrategia
de búsqueda).

Modelos (Random Forest; entrada: características de la instancia [+ configuración]):
  1. Clasificador de resolución: ¿la configuración prueba el óptimo antes de T = 300 s?
  2. Regresor de tiempo condicional: log(tiempo hasta probar el óptimo), entrenado solo con
     las ejecuciones que lo prueban.
  3. Clasificador de la mejor configuración: ¿cuál obtiene el menor makespan a los 300 s?
     (en un empate, la que lo alcanza primero). Con dos configuraciones equivale a
     "¿gana Gecode?".

Construcción del schedule para una instancia nueva:
  a. Las configuraciones con probabilidad de resolver >= 0.5 van primero, ordenadas por su
     tiempo predicho; cada una recibe 2 x tiempo predicho (sin exceder el tiempo restante).
  b. El tiempo restante R se reparte según la probabilidad p_c de que cada configuración sea
     la mejor: cada una recibe max(minimo_c, p_c * R), donde minimo_c es el tiempo que el
     schedule estático elegido en el entrenamiento (07) le da a esa configuración. Las
     asignaciones se reescalan para sumar R y se ejecutan de menor a mayor tiempo.
Cada instancia se evalúa con modelos entrenados en las otras 235 (leave-one-out).

Salidas (en resultados/analisis/): ml_resumen.csv, ml_por_instancia.csv, ml_calidad_modelos.csv
Uso (desde la raíz del repositorio): python src/08_modelo_ml.py
"""
import warnings, itertools
import numpy as np, pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import roc_auc_score, mean_absolute_error
from comun import *
warnings.filterwarnings('ignore')

I = cargar_instancias(); C = cargar_corridas()
CFG = [c for c in ['chuffed_v1', 'gecode_v1', 'chuffed_v2'] if c in C]
NT = I[~I.trivial]; inst = list(NT.index)
UB = NT['ub'].to_dict(); BKS = NT['bks'].to_dict()
X = cargar_caracteristicas('ambas').loc[inst]
SEMILLA = 0

def simular(i, schedule):
    mejor, opt, t_opt, acum = UB[i], False, PENAL, 0.0
    for c, t in schedule:
        if t <= 0: continue
        mejor = min(mejor, valor_en(C[c], i, t, UB[i]))
        if not opt and optimo_en(C[c], i, t):
            opt, t_opt = True, acum + C[c].at[i, 't_fin']
        acum += t
    return mejor, opt, t_opt

MS = pd.DataFrame({c: [simular(i, [(c, LIMITE)])[0] for i in inst] for c in CFG}, index=inst)
RES = pd.DataFrame({c: [optimo_en(C[c], i, LIMITE) for i in inst] for c in CFG}, index=inst)
TFIN = pd.DataFrame({c: [C[c].at[i, 't_fin'] for i in inst] for c in CFG}, index=inst)
def t_alcanza(c, i, obj):
    if MS.at[i, c] > obj: return np.inf
    tr = [t for t, m in C[c].at[i, 'tray'] if m <= obj]
    return min(tr) if tr else 0.0
BEST = MS.min(axis=1)
MEJOR = pd.Series({i: min([c for c in CFG if MS.at[i, c] == BEST[i]], key=lambda c: t_alcanza(c, i, BEST[i]))
                   for i in inst})

# schedules estáticos candidatos (mismos que 07)
GRID_X = [0, 2, 5, 10, 15, 20, 30, 45, 60, 90, 120, 150, 200, 300]
GRID_Y = [30, 60, 90, 120, 150, 180]
CANDS = [(('gecode_v1', x), ('chuffed_v1', LIMITE - x)) for x in GRID_X]
if len(CFG) > 2:
    for a, b in itertools.permutations(CFG, 2):
        CANDS += [((a, x), (b, LIMITE - x)) for x in GRID_X if 0 < x < LIMITE]
    otros = [c for c in CFG if c != 'gecode_v1']
    for a, b in itertools.permutations(otros, 2):
        CANDS += [(('gecode_v1', 2), (a, y), (b, LIMITE - 2 - y)) for y in GRID_Y]
CANDS = list(dict.fromkeys(CANDS))
EST = {s: pd.Series({i: gap(simular(i, list(s))[0], BKS[i]) for i in inst}) for s in CANDS}

def apilar(Xs, n):
    """Una fila por (instancia, configuración), con la configuración como característica."""
    return np.vstack([np.hstack([Xs, np.full((n, 1), k)]) for k, _ in enumerate(CFG)])

filas = []
for n, i in enumerate(inst):
    tr = [j for j in inst if j != i]
    Xtr, Xte = escalar(X.loc[tr], X.loc[[i]])
    # 1. clasificador de resolución
    Ytr = np.concatenate([RES.loc[tr, c].values for c in CFG]).astype(int)
    Xa = apilar(Xtr, len(tr))
    clf = RandomForestClassifier(300, min_samples_leaf=2, random_state=SEMILLA, n_jobs=-1).fit(Xa, Ytr)
    p_res = {c: clf.predict_proba(np.hstack([Xte, [[k]]]))[0][list(clf.classes_).index(1)] if 1 in clf.classes_ else 0.0
             for k, c in enumerate(CFG)}
    # 2. tiempo condicional (log), solo ejecuciones que prueban el óptimo
    Ta = np.concatenate([TFIN.loc[tr, c].values for c in CFG])
    reg = RandomForestRegressor(300, min_samples_leaf=2, random_state=SEMILLA, n_jobs=-1).fit(Xa[Ytr == 1], np.log1p(Ta[Ytr == 1]))
    t_hat = {c: float(np.expm1(reg.predict(np.hstack([Xte, [[k]]]))[0])) for k, c in enumerate(CFG)}
    # 3. clasificador de la mejor configuración
    cb = RandomForestClassifier(300, min_samples_leaf=2, random_state=SEMILLA, n_jobs=-1).fit(Xtr, MEJOR.loc[tr].values)
    pr = cb.predict_proba(Xte)[0]
    p_mejor = {c: (pr[list(cb.classes_).index(c)] if c in cb.classes_ else 0.0) for c in CFG}
    # schedule
    est = min(CANDS, key=lambda s: EST[s].loc[tr].mean())
    minimo = {c: 0.0 for c in CFG}
    for c, d in est:
        minimo[c] = d if d < LIMITE / 2 else 0.0     # solo los tramos cortos del estático actúan como mínimo
    sched, resto = [], LIMITE
    for c in sorted([c for c in CFG if p_res[c] >= 0.5], key=lambda c: t_hat[c]):
        d = min(resto, 2 * t_hat[c]); sched.append((c, d)); resto -= d
    if resto > 0:
        asig = {c: max(minimo[c], p_mejor[c] * resto) for c in CFG}
        tot = sum(asig.values())
        asig = {c: resto * v / tot for c, v in asig.items() if v > 0}
        sched += sorted(asig.items(), key=lambda kv: kv[1])
    m, o, t = simular(i, sched)
    filas.append(dict(instancia=i, makespan=m, optimo=o, t=t, gap=gap(m, BKS[i]),
                      schedule=' + '.join(f'{NOMBRES[c]} {d:.0f}s' for c, d in sched if d > 0.5),
                      **{f'p_res_{c}': p_res[c] for c in CFG}, **{f't_hat_{c}': t_hat[c] for c in CFG},
                      **{f'p_mejor_{c}': p_mejor[c] for c in CFG}, real_mejor=MEJOR[i],
                      **{f'real_res_{c}': RES.at[i, c] for c in CFG},
                      **{f'real_t_{c}': (TFIN.at[i, c] if RES.at[i, c] else np.nan) for c in CFG}))
    if n % 40 == 0: print(f'{n}/{len(inst)}', flush=True)

D = pd.DataFrame(filas).set_index('instancia')
D.round(4).to_csv(SALIDAS / 'ml_por_instancia.csv')

# calidad de los modelos (predicciones fuera de muestra)
q = []
for c in CFG:
    y = D[f'real_res_{c}'].astype(bool)
    if y.nunique() > 1:
        q.append(dict(modelo=f'Resolución ({NOMBRES[c]})', metrica='AUC', valor=roc_auc_score(y, D[f'p_res_{c}'])))
    q.append(dict(modelo=f'Resolución ({NOMBRES[c]})', metrica='exactitud', valor=((D[f'p_res_{c}'] >= .5) == y).mean()))
s = D[D.real_res_chuffed_v1.astype(bool)]
q.append(dict(modelo='Tiempo condicional (Chuffed, resueltas)', metrica='MAE (s)', valor=mean_absolute_error(s.real_t_chuffed_v1, s.t_hat_chuffed_v1)))
q.append(dict(modelo='Tiempo condicional (Chuffed, resueltas)', metrica='mediana error relativo',
              valor=(np.abs(s.t_hat_chuffed_v1 - s.real_t_chuffed_v1) / s.real_t_chuffed_v1).median()))
pm = D[[f'p_mejor_{c}' for c in CFG]].values
pred = np.array(CFG)[pm.argmax(axis=1)]
q.append(dict(modelo='Mejor configuración', metrica='exactitud', valor=(pred == D.real_mejor.values).mean()))
for c in CFG:
    y = (D.real_mejor == c)
    if y.nunique() > 1:
        q.append(dict(modelo=f'Mejor configuración ({NOMBRES[c]} vs resto)', metrica='AUC', valor=roc_auc_score(y, D[f'p_mejor_{c}'])))
Q = pd.DataFrame(q); Q.round(4).to_csv(SALIDAS / 'ml_calidad_modelos.csv', index=False)

# comparación con los demás métodos (07)
P = pd.read_csv(SALIDAS / 'portafolios_resumen.csv').set_index('metodo')
sbs = pd.read_csv(SALIDAS / 'portafolios_por_instancia.csv').query("metodo == 'SBS'").set_index('instancia')['makespan']
fila = dict(gap_medio=D.gap.mean(), optimos=int(D.optimo.sum()), par10=D.t.mean())
fila['brecha_cerrada_%'] = 100 * (P.at['SBS', 'gap_medio'] - fila['gap_medio']) / (P.at['SBS', 'gap_medio'] - P.at['VBS', 'gap_medio'])
fila['mejor_que_SBS'] = int((D.makespan < sbs.loc[D.index]).sum()); fila['peor_que_SBS'] = int((D.makespan > sbs.loc[D.index]).sum())
P.loc['Schedule ML (híbrido)'] = fila
P.round(3).to_csv(SALIDAS / 'ml_resumen.csv')
print(Q.round(3).to_string(index=False)); print(); print(P.round(2).to_string())
print('\nSchedules más frecuentes:\n', D.schedule.value_counts().head(8).to_string())
