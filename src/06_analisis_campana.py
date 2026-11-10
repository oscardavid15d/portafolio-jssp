"""
06_analisis_campana.py - Análisis de la campaña con el modelo con cotas (300 s, 242 instancias).

Genera en resultados/analisis/:
  por_instancia.csv    una fila por instancia con cotas, BKS y resultado de cada configuración
  resumen_global.csv   óptimos, gap medio, PAR10, victorias y ejecuciones sin solución
  por_tamano.csv, por_familia.csv   el mismo resumen por grupo
  anytime.csv          gap medio y óptimos de cada configuración a 10, 30, 60, 120 y 300 s
  efecto_cotas.csv     Chuffed, Gecode y CP-SAT con el modelo original frente al modelo con cotas
  figuras/*.png        gap por tamaño, perfil anytime, victorias por familia, efecto de las cotas
  RESUMEN.md           cifras principales
Uso (desde la raíz del repositorio): python src/06_analisis_campana.py
"""
import numpy as np, pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from comun import *

SALIDAS.mkdir(exist_ok=True); (SALIDAS / 'figuras').mkdir(exist_ok=True)
I = cargar_instancias()
C = cargar_corridas()
O = cargar_original()
cfgs = [c for c in ['chuffed_v1', 'gecode_v1', 'chuffed_v2'] if c in C]   # miembros del portafolio
refs = [c for c in ['cpsat_v1'] if c in C]                                 # referencia externa
for c in cfgs + refs:
    assert set(C[c].index) >= set(I.index[~I.trivial]), f'faltan instancias en {c}'
    # verificación: el makespan final coincide con la última solución de la trayectoria
    for i, r in C[c].iterrows():
        if not np.isnan(r['makespan']):
            assert r['tray'] and min(m for _, m in r['tray']) == r['makespan'], (c, i)

# ---------------------------------------------------------------- tabla por instancia
T = I[['familia', 'tamano', 'n', 'm', 'ops', 'lb', 'ub', 'bks', 'trivial']].copy()
for c in cfgs + refs:
    d = C[c].reindex(T.index)
    T[f'{c}_sin_sol'] = d['makespan'].isna() & ~T.trivial
    T[f'{c}_ms'] = d['makespan'].fillna(T['ub']).clip(upper=T['ub'])
    T[f'{c}_opt'] = d['optimo'].fillna(False).astype(bool)
    T[f'{c}_t'] = np.where(T[f'{c}_opt'], d['t_pared'], PENAL)
    T.loc[T.trivial, f'{c}_ms'] = T['ub']; T.loc[T.trivial, f'{c}_opt'] = True; T.loc[T.trivial, f'{c}_t'] = 0.0
    T[f'{c}_gap'] = gap(T[f'{c}_ms'], T['bks'])
T['vbs_ms'] = T[[f'{c}_ms' for c in cfgs]].min(axis=1)
T['vbs_opt'] = T[[f'{c}_opt' for c in cfgs]].any(axis=1)
T['vbs_t'] = T[[f'{c}_t' for c in cfgs]].min(axis=1)
T['vbs_gap'] = gap(T['vbs_ms'], T['bks'])
T['heur_gap'] = gap(T['ub'], T['bks'])
for c in cfgs:
    otros = [f'{o}_ms' for o in cfgs if o != c]
    T[f'{c}_gana'] = T[f'{c}_ms'] < T[otros].min(axis=1)
T['empate'] = ~T[[f'{c}_gana' for c in cfgs]].any(axis=1)
for s in ['chuffed', 'gecode', 'cpsat']:
    T[f'{s}_original_ms'] = O[f'{s}_makespan'].reindex(T.index)
    T[f'{s}_original_opt'] = O[f'{s}_optimo'].reindex(T.index).astype(str).str.lower() == 'true'
    T[f'{s}_original_gap'] = gap(T[f'{s}_original_ms'], T['bks'])
T.round(4).to_csv(SALIDAS / 'por_instancia.csv')

# ---------------------------------------------------------------- resúmenes
NT = T[~T.trivial]
def resumen(g):
    f = {'instancias': len(g)}
    for c in cfgs + ['vbs']:
        f[f'opt_{c}'] = int(g[f'{c}_opt'].sum())
        f[f'gap_{c}'] = g[f'{c}_gap'].mean()
        f[f'par10_{c}'] = g[f'{c}_t'].mean()
    for c in cfgs:
        f[f'gana_{c}'] = int(g[f'{c}_gana'].sum())
        f[f'sin_sol_{c}'] = int(g[f'{c}_sin_sol'].sum())
    f['empates'] = int(g['empate'].sum())
    for c in refs:
        f[f'opt_{c}'] = int(g[f'{c}_opt'].sum()); f[f'gap_{c}'] = g[f'{c}_gap'].mean()
        f[f'par10_{c}'] = g[f'{c}_t'].mean(); f[f'sin_sol_{c}'] = int(g[f'{c}_sin_sol'].sum())
    f['gap_heuristica'] = g['heur_gap'].mean()
    mejor = min(cfgs, key=lambda c: g[f'{c}_gap'].mean())
    f['mejor_individual'] = mejor
    f['margen_gap'] = g[f'{mejor}_gap'].mean() - g['vbs_gap'].mean()
    return pd.Series(f)
G = resumen(NT); G.to_frame('valor').to_csv(SALIDAS / 'resumen_global.csv')
orden_t = NT.groupby('tamano')['ops'].first().sort_values().index
PT = NT.groupby('tamano').apply(resumen).loc[orden_t]; PT.round(3).to_csv(SALIDAS / 'por_tamano.csv')
PF = NT.groupby('familia').apply(resumen).loc[['ft', 'la', 'abz', 'orb', 'swv', 'yn', 'ta', 'dmu']]
PF.round(3).to_csv(SALIDAS / 'por_familia.csv')

# ---------------------------------------------------------------- perfil anytime
cortes = [10, 30, 60, 120, 300]
filas = []
for t in cortes:
    f = {'segundos': t}
    vals = {}
    for c in cfgs:
        v = [valor_en(C[c], i, t, I.at[i, 'ub']) for i in NT.index]
        vals[c] = np.array(v)
        f[f'gap_{c}'] = gap(vals[c], NT['bks'].values).mean()
        f[f'opt_{c}'] = sum(optimo_en(C[c], i, t) for i in NT.index)
    f['gap_vbs'] = gap(np.min(list(vals.values()), axis=0), NT['bks'].values).mean()
    filas.append(f)
A = pd.DataFrame(filas); A.round(3).to_csv(SALIDAS / 'anytime.csv', index=False)

# ---------------------------------------------------------------- efecto de las cotas
E = []
for s, c in [('chuffed', 'chuffed_v1'), ('gecode', 'gecode_v1'), ('cpsat', 'cpsat_v1')]:
    ambos = NT[NT[f'{s}_original_opt'] & NT[f'{c}_opt']]
    t0 = O.loc[ambos.index, f'{s}_tiempo'].astype(float)
    t1 = ambos[f'{c}_t']
    E.append(dict(solver=s, gap_original=NT[f'{s}_original_gap'].mean(), gap_cotas=NT[f'{c}_gap'].mean(),
                  opt_original=int(NT[f'{s}_original_opt'].sum()), opt_cotas=int(NT[f'{c}_opt'].sum()),
                  opt_nuevos=int((NT[f'{c}_opt'] & ~NT[f'{s}_original_opt']).sum()),
                  opt_perdidos=int((~NT[f'{c}_opt'] & NT[f'{s}_original_opt']).sum()),
                  t_mediano_original=t0.median() if len(ambos) else np.nan,
                  t_mediano_cotas=t1.median() if len(ambos) else np.nan,
                  mejora_sobre_original=int((NT[f'{c}_ms'] < NT[f'{s}_original_ms']).sum()),
                  peor_que_original=int((NT[f'{c}_ms'] > NT[f'{s}_original_ms']).sum())))
pd.DataFrame(E).round(3).to_csv(SALIDAS / 'efecto_cotas.csv', index=False)

# ---------------------------------------------------------------- figuras
col = {'chuffed_v1': '#2a78d6', 'gecode_v1': '#eb6834', 'chuffed_v2': '#1b2a3a', 'vbs': '#2e9e5b'}
x = np.arange(len(PT))
fig, ax = plt.subplots(figsize=(10, 4.5))
w = 0.8 / (len(cfgs) + 2)
for k, c in enumerate(cfgs + ['vbs']):
    ax.bar(x + k * w, PT[f'gap_{c}'], w, label=NOMBRES.get(c, 'VBS'), color=col[c])
ax.bar(x + (len(cfgs) + 1) * w, PT['gap_heuristica'], w, label='Heurística (ub)', color='#b8b5aa')
ax.set_xticks(x + w * (len(cfgs) + 1) / 2, PT.index, rotation=45); ax.set_ylabel('Gap medio frente a BKS (%)')
ax.set_xlabel('Tamaño (trabajos x máquinas)'); ax.legend(frameon=False, ncol=3); ax.spines[['top', 'right']].set_visible(False)
fig.tight_layout(); fig.savefig(SALIDAS / 'figuras/gap_por_tamano.png', dpi=200); plt.close(fig)

fig, ax = plt.subplots(figsize=(6, 4))
for c in cfgs + ['vbs']:
    ax.plot(A['segundos'], A[f'gap_{c}'], marker='o', label=NOMBRES.get(c, 'VBS'), color=col[c])
ax.set_xscale('log'); ax.set_xticks(cortes, [str(t) for t in cortes]); ax.set_xlabel('Tiempo (s)')
ax.set_ylabel('Gap medio (%)'); ax.legend(frameon=False); ax.spines[['top', 'right']].set_visible(False)
fig.tight_layout(); fig.savefig(SALIDAS / 'figuras/anytime.png', dpi=200); plt.close(fig)

fig, ax = plt.subplots(figsize=(8, 4))
bottom = np.zeros(len(PF))
for c in cfgs:
    ax.bar(PF.index, PF[f'gana_{c}'], bottom=bottom, label=NOMBRES[c], color=col[c]); bottom += PF[f'gana_{c}']
ax.bar(PF.index, PF['empates'], bottom=bottom, label='Empate', color='#dcd9cf')
ax.set_ylabel('Instancias'); ax.legend(frameon=False); ax.spines[['top', 'right']].set_visible(False)
fig.tight_layout(); fig.savefig(SALIDAS / 'figuras/ganador_por_familia.png', dpi=200); plt.close(fig)

fig, ax = plt.subplots(figsize=(6, 4))
e = pd.DataFrame(E).set_index('solver')
ax.bar(np.arange(len(e)) - 0.2, e['gap_original'], 0.4, label='Modelo original', color='#b8b5aa')
ax.bar(np.arange(len(e)) + 0.2, e['gap_cotas'], 0.4, label='Modelo con cotas', color='#2a78d6')
ax.set_xticks(range(len(e)), [{"chuffed": "Chuffed", "gecode": "Gecode", "cpsat": "CP-SAT"}[x] for x in e.index]); ax.set_yscale('log'); ax.set_ylabel('Gap medio (%, escala log)')
ax.legend(frameon=False); ax.spines[['top', 'right']].set_visible(False)
fig.tight_layout(); fig.savefig(SALIDAS / 'figuras/efecto_cotas.png', dpi=200); plt.close(fig)

# ---------------------------------------------------------------- resumen
ganadas = {c: list(NT.index[NT[f'{c}_gana']]) for c in cfgs}
md = [f"# Resumen de la campaña con el modelo con cotas\n",
      f"- Instancias: {len(T)} ({int(T.trivial.sum())} con lb = ub, óptimo probado sin solvers: "
      f"{', '.join(T.index[T.trivial])}); se analizan {len(NT)}.",
      f"- Configuraciones: {', '.join(NOMBRES[c] for c in cfgs)}.\n",
      "| | " + " | ".join(NOMBRES[c] for c in cfgs) + " | VBS | Heurística |",
      "|---|" + "---|" * (len(cfgs) + 2),
      "| Óptimos | " + " | ".join(str(int(G[f'opt_{c}'])) for c in cfgs) + f" | {int(G['opt_vbs'])} | — |",
      "| Gap medio (%) | " + " | ".join(f"{G[f'gap_{c}']:.2f}" for c in cfgs) + f" | {G['gap_vbs']:.2f} | {G['gap_heuristica']:.2f} |",
      "| PAR10 (s) | " + " | ".join(f"{G[f'par10_{c}']:.0f}" for c in cfgs) + f" | {G['par10_vbs']:.0f} | — |",
      "| Gana (estricto) | " + " | ".join(str(int(G[f'gana_{c}'])) for c in cfgs) + f" | — | — |",
      "| Sin solución | " + " | ".join(str(int(G[f'sin_sol_{c}'])) for c in cfgs) + " | — | — |",
      f"\nMejor configuración individual: {NOMBRES[G['mejor_individual']]}. "
      f"Margen del portafolio (mejor individual - VBS): {G['margen_gap']:.2f} puntos de gap.\n"]
for c in cfgs:
    md.append(f"- {NOMBRES[c]} gana en: {', '.join(ganadas[c]) or 'ninguna'}")
md.append("\nVer por_tamano.csv, por_familia.csv, anytime.csv y efecto_cotas.csv.")
(SALIDAS / 'RESUMEN.md').write_text('\n'.join(md), encoding='utf-8')
print('\n'.join(md))
print('\nPor tamaño:\n', PT[['instancias'] + [f'gap_{c}' for c in cfgs] + ['gap_vbs', 'margen_gap'] + [f'gana_{c}' for c in cfgs]].round(2).to_string())
print('\nAnytime:\n', A.round(2).to_string(index=False))
print('\nEfecto cotas:\n', pd.DataFrame(E).round(2).to_string(index=False))
