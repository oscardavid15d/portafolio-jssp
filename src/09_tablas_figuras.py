"""
09_tablas_figuras.py - Tablas (LaTeX, booktabs) y figuras (PDF) para el documento.

Lee solo las salidas de 06, 07 y 08 (y las cotas/BKS); se vuelve a ejecutar cada vez que
cambian los resultados. Escribe en resultados/analisis/latex/tablas/*.tex y resultados/analisis/latex/figuras/*.pdf.
En el documento: \\input{tablas/tab_individual} y \\includegraphics{gap_por_tamano.pdf}.
Uso (desde la raíz del repositorio): python src/09_tablas_figuras.py
"""
import numpy as np, pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from comun import *

OUT_T = SALIDAS / 'latex/tablas'; OUT_F = SALIDAS / 'latex/figuras'
OUT_T.mkdir(parents=True, exist_ok=True); OUT_F.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({'font.family': 'serif', 'font.size': 9, 'axes.spines.top': False, 'axes.spines.right': False})
COL = {'chuffed_v1': '#2a78d6', 'gecode_v1': '#eb6834', 'chuffed_v2': '#1b2a3a', 'vbs': '#2e9e5b', 'cpsat_v1': '#8e44ad'}

I = cargar_instancias()
T = pd.read_csv(SALIDAS / 'por_instancia.csv').set_index('instancia')
G = pd.read_csv(SALIDAS / 'resumen_global.csv').set_index('Unnamed: 0')['valor']
G = pd.Series({k: (float(v) if str(v).replace('.', '', 1).replace('-', '', 1).isdigit() else v) for k, v in G.items()})
PT = pd.read_csv(SALIDAS / 'por_tamano.csv').set_index('tamano')
PF = pd.read_csv(SALIDAS / 'por_familia.csv').set_index('familia')
A = pd.read_csv(SALIDAS / 'anytime.csv')
E = pd.read_csv(SALIDAS / 'efecto_cotas.csv').set_index('solver')
P = pd.read_csv(SALIDAS / 'ml_resumen.csv').set_index('metodo')
PI = pd.read_csv(SALIDAS / 'portafolios_por_instancia.csv')
ML = pd.read_csv(SALIDAS / 'ml_por_instancia.csv').set_index('instancia')
Q = pd.read_csv(SALIDAS / 'ml_calidad_modelos.csv')
SK = pd.read_csv(SALIDAS / 'portafolios_sensibilidad_k.csv')
# los CSV guardan el gap del VBS redondeado a 3 decimales (12.835); se usa el valor exacto
# de resumen_global.csv para que todas las tablas muestren el mismo 12.83
A.loc[A.segundos == A.segundos.max(), 'gap_vbs'] = G['gap_vbs']
P.loc['VBS', 'gap_medio'] = G['gap_vbs']
cfgs = [c for c in ['chuffed_v1', 'gecode_v1', 'chuffed_v2'] if f'{c}_ms' in T]
refs = [c for c in ['cpsat_v1'] if f'{c}_ms' in T]
NT = T[~T.trivial]
FAM = ['ft', 'la', 'abz', 'orb', 'swv', 'yn', 'ta', 'dmu']
FAM_NOM = {'ft': 'ft (Fisher y Thompson)', 'la': 'la (Lawrence)', 'abz': 'abz (Adams, Balas y Zawack)',
           'orb': 'orb (Applegate y Cook)', 'swv': 'swv (Storer, Wu y Vaccari)', 'yn': 'yn (Yamada y Nakano)',
           'ta': 'ta (Taillard)', 'dmu': 'dmu (Demirkol, Mehta y Uzsoy)'}

def f1(x): return f'{x:.1f}'
def f2(x): return f'{x:.2f}'
def tabla(nombre, caption, label, columnas, filas, alineacion, nota=None, fuente=r'\small'):
    L = [r'\begin{table}[H]', r'  \centering', f'  {fuente}', r'  \singlespacing',
         f'  \\caption{{{caption}}}', f'  \\label{{{label}}}', f'  \\begin{{tabular}}{{{alineacion}}}',
         r'    \toprule', '    ' + ' & '.join(columnas) + r' \\', r'    \midrule']
    for fila in filas:
        L.append(r'    \midrule' if fila == '---' else '    ' + ' & '.join(map(str, fila)) + r' \\')
    L += [r'    \bottomrule', r'  \end{tabular}']
    if nota:
        L.append(f'  \\par\\vspace{{2pt}}{{\\footnotesize {nota}}}')
    L.append(r'\end{table}')
    (OUT_T / f'{nombre}.tex').write_text('\n'.join(L) + '\n', encoding='utf-8')

def rango(s):
    return f'{s.min()}' if s.min() == s.max() else f'{s.min()}--{s.max()}'

# ---------------------------------------------------------------- capítulo 4: instancias y cotas
# La tabla de familias ya está en el capítulo 4 (tab:familias); aquí solo la de cotas.
filas = []
for f in FAM + ['Total']:
    g = I if f == 'Total' else I[I.familia == f]
    if f == 'Total': filas.append('---')
    filas.append([f if f != 'Total' else 'Total', len(g), f1((100 * g.lb / g.bks).mean()),
                  f1((100 * (g.ub - g.bks) / g.bks).mean()), f1((g.horizonte / g.bks).mean()),
                  int(g.trivial.sum()), g.regla_ub.mode().iat[0]])
tabla('tab_cotas', 'Calidad de las cotas por familia.', 'tab:cotas',
      ['Familia', 'Inst.', r'lb/BKS (\%)', r'Gap de ub (\%)', r'$H$/BKS', r'lb $=$ ub', 'Regla más frecuente'],
      filas, 'lrrrrrl',
      nota=r'lb: cota inferior; ub: mejor programa de Giffler-Thompson; $H$: horizonte del modelo original (suma de duraciones).')

filas = []
for s, nom in [('chuffed', 'Chuffed'), ('gecode', 'Gecode'), ('cpsat', 'CP-SAT (ref.)')]:
    if s not in E.index: continue
    e = E.loc[s]
    filas.append([nom, f1(e.gap_original), f1(e.gap_cotas), int(e.opt_original), int(e.opt_cotas),
                  int(e.opt_nuevos), f1(e.t_mediano_original), f1(e.t_mediano_cotas),
                  int(e.mejora_sobre_original), int(e.peor_que_original)])
tabla('tab_efecto_cotas', 'Efecto de las cotas en el modelo (236 instancias, 300\\,s).', 'tab:efecto_cotas',
      ['\\textit{Solver}', r'\multicolumn{2}{c}{Gap medio (\%)}', r'\multicolumn{3}{c}{Óptimos}',
       r'\multicolumn{2}{c}{$t$ mediano (s)}', 'Mejora', 'Empeora'],
      [['', 'Original', 'Cotas', 'Original', 'Cotas', 'Nuevos', 'Original', 'Cotas', '', '']] + ['---'] + filas,
      'lrrrrrrrrr',
      nota=r'$t$ mediano: tiempo hasta probar el óptimo en las instancias donde ambos modelos lo prueban. '
           r'Mejora/Empeora: instancias con menor/mayor \textit{makespan} que con el modelo original.')
# corrección: la tabla anterior usa una fila de subencabezado; se reescribe con cmidrule
txt = (OUT_T / 'tab_efecto_cotas.tex').read_text(encoding='utf-8')
txt = txt.replace("    \\midrule\n     & Original", "    \\cmidrule(lr){2-3}\\cmidrule(lr){4-6}\\cmidrule(lr){7-8}\n     & Original", 1)
(OUT_T / 'tab_efecto_cotas.tex').write_text(txt, encoding='utf-8')

# ---------------------------------------------------------------- capítulo 7: solvers individuales
cols = cfgs + ['vbs']
filas = [['Óptimos probados'] + [int(G[f'opt_{c}']) for c in cols] + ['--'] + [int(G[f'opt_{c}']) for c in refs],
         [r'Gap medio (\%)'] + [f2(G[f'gap_{c}']) for c in cols] + [f2(G['gap_heuristica'])] + [f2(G[f'gap_{c}']) for c in refs],
         ['PAR10 (s)'] + [f'{G[f"par10_{c}"]:.0f}' for c in cols] + ['--'] + [f'{G[f"par10_{c}"]:.0f}' for c in refs],
         ['Instancias donde gana'] + [int(G[f'gana_{c}']) for c in cfgs] + ['--', '--'] + ['--'] * len(refs),
         ['Sin solución'] + [int(G[f'sin_sol_{c}']) for c in cfgs] + ['--', '--'] + [int(G[f'sin_sol_{c}']) for c in refs]]
tabla('tab_individual', 'Desempeño de las configuraciones con el modelo con cotas (236 instancias, 300\\,s).',
      'tab:individual', [''] + [NOMBRES[c] for c in cfgs] + ['VBS', 'Heurística'] + [f'{NOMBRES[c]} (ref.)' for c in refs],
      filas, 'l' + 'r' * (len(cols) + 1 + len(refs)),
      nota=r'Se excluyen las 6 instancias con lb $=$ ub. Sin solución: el resultado es la ub. '
           r'VBS: la mejor configuración del portafolio en cada instancia.')

nc = len(cfgs)
ab = {'chuffed_v1': 'C', 'gecode_v1': 'G', 'chuffed_v2': 'C2'}
nota_ab = 'C: ' + NOMBRES[cfgs[0]] + '; G: ' + NOMBRES[cfgs[1]] + ('; C2: Chuffed V2' if nc > 2 else '') + '.'
def agrupar(nombre, rangos):
    txt = (OUT_T / f'{nombre}.tex').read_text(encoding='utf-8')
    cm = ''.join(f'\\cmidrule(lr){{{a}-{b}}}' for a, b in rangos)
    txt = txt.replace('    \\midrule\n     & ', '    ' + cm + '\n     & ', 1)
    (OUT_T / f'{nombre}.tex').write_text(txt, encoding='utf-8')

filas = []
for t, r in PT.iterrows():
    filas.append([t.replace('x', r'$\times$'), int(r.instancias)] + [f2(r[f'gap_{c}']) for c in cfgs] +
                 [f2(r.gap_vbs), f2(r.margen_gap)] + [int(r[f'gana_{c}']) for c in cfgs])
cab = ['Tamaño', 'Inst.', f'\\multicolumn{{{nc + 2}}}{{c}}{{Gap medio (\\%)}}', f'\\multicolumn{{{nc}}}{{c}}{{Gana}}']
sub = ['', ''] + [ab[c] for c in cfgs] + ['VBS', 'Margen'] + [ab[c] for c in cfgs]
tabla('tab_por_tamano', 'Gap medio (\\%) por tamaño de instancia.', 'tab:por_tamano', cab,
      [sub] + ['---'] + filas, 'lr' + 'r' * (2 * nc + 2),
      nota=nota_ab + r' Margen: gap de la mejor configuración individual del grupo menos gap del VBS.')
agrupar('tab_por_tamano', [(3, 4 + nc), (5 + nc, 4 + 2 * nc)])

filas = []
for f, r in PF.iterrows():
    filas.append([f, int(r.instancias)] + [int(r[f'opt_{c}']) for c in cfgs] + [f2(r[f'gap_{c}']) for c in cfgs] +
                 [f2(r.gap_vbs)] + [int(r[f'gana_{c}']) for c in cfgs] + [int(r[f'sin_sol_{c}']) for c in cfgs])
sub = ['', ''] + [ab[c] for c in cfgs] + [ab[c] for c in cfgs] + ['VBS'] + [ab[c] for c in cfgs] + [ab[c] for c in cfgs]
c0 = 3
rangos = [(c0, c0 + nc - 1), (c0 + nc, c0 + 2 * nc), (c0 + 2 * nc + 1, c0 + 3 * nc), (c0 + 3 * nc + 1, c0 + 4 * nc)]
cab = ['Familia', 'Inst.', f'\\multicolumn{{{nc}}}{{c}}{{Óptimos}}', f'\\multicolumn{{{nc + 1}}}{{c}}{{Gap medio (\\%)}}',
       f'\\multicolumn{{{nc}}}{{c}}{{Gana}}', f'\\multicolumn{{{nc}}}{{c}}{{Sin solución}}']
tabla('tab_por_familia', 'Resultados por familia de instancias.', 'tab:por_familia', cab,
      [sub] + ['---'] + filas, 'lr' + 'r' * (4 * nc + 1),
      nota='C: ' + NOMBRES[cfgs[0]] + '; G: ' + NOMBRES[cfgs[1]] + ('; C2: Chuffed V2' if nc > 2 else '') + '.')
txt = (OUT_T / 'tab_por_familia.tex').read_text(encoding='utf-8')
cm = ''.join(f'\\cmidrule(lr){{{a}-{b}}}' for a, b in rangos)
txt = txt.replace('    \\midrule\n     & ', '    ' + cm + '\n     & ', 1)
(OUT_T / 'tab_por_familia.tex').write_text(txt, encoding='utf-8')

filas = [[int(r.segundos)] + [f2(r[f'gap_{c}']) for c in cfgs] + [f2(r.gap_vbs)] + [int(r[f'opt_{c}']) for c in cfgs]
         for _, r in A.iterrows()]
cab = ['Tiempo (s)', f'\\multicolumn{{{nc + 1}}}{{c}}{{Gap medio (\\%)}}', f'\\multicolumn{{{nc}}}{{c}}{{Óptimos probados}}']
sub = [''] + [ab[c] for c in cfgs] + ['VBS'] + [ab[c] for c in cfgs]
tabla('tab_anytime', 'Gap medio (\\%) y óptimos probados según el tiempo transcurrido.', 'tab:anytime', cab,
      [sub] + ['---'] + filas, 'r' + 'r' * (2 * nc + 1), nota=nota_ab)
agrupar('tab_anytime', [(2, 2 + nc), (3 + nc, 2 + 2 * nc)])

# ---------------------------------------------------------------- portafolios y ML
orden = [NOMBRES[c] for c in cfgs] + ['Regla por tamaño', 'WTA k-NN (mzn2feat)', 'WTA k-NN (propias)', 'WTA k-NN (ambas)',
         'SUNNY (mzn2feat)', 'SUNNY (propias)', 'SUNNY (ambas)', 'Schedule estático', 'Schedule ML (híbrido)', 'VBS']
nom_tex = {'Schedule estático': r'\textit{Schedule} estático', 'Schedule ML (híbrido)': r'\textit{Schedule} con ML (híbrido)',
           'WTA k-NN (mzn2feat)': r'WTA $k$-NN (mzn2feat)', 'WTA k-NN (propias)': r'WTA $k$-NN (propias)',
           'WTA k-NN (ambas)': r'WTA $k$-NN (ambas)'}
# filas sin cotas: Chuffed y Gecode con el modelo original (campaña de 300 s) y su VBS
O = pd.read_csv(RUTAS['original']).set_index('instancia')
Tn = T[~T.trivial.astype(bool)]
O = O.loc[Tn.index]
sc = {}
for s_, c in [('chuffed', 'chuffed_v1'), ('gecode', 'gecode_v1')]:
    sc[NOMBRES[c]] = pd.DataFrame({'ms': O[f'{s_}_makespan'].astype(float), 'opt': O[f'{s_}_optimo'].astype(bool),
                                   't': O[f'{s_}_tiempo'].where(O[f'{s_}_optimo'].astype(bool), PENAL)})
sc['VBS'] = pd.DataFrame({'ms': pd.concat([d.ms for d in sc.values()], axis=1).min(axis=1),
                          'opt': pd.concat([d.opt for d in sc.values()], axis=1).any(axis=1),
                          't': pd.concat([d.t for d in sc.values()], axis=1).min(axis=1)})
sbs_c = [c for c in cfgs if NOMBRES[c] == P.loc[[NOMBRES[c] for c in cfgs], 'gap_medio'].idxmin()][0]
sbs_ms = Tn[f'{sbs_c}_ms']
filas = []
for nom, d in sc.items():
    filas.append([nom + ' (sin cotas)', f2((100 * (d.ms - Tn.bks) / Tn.bks).mean()), int(d.opt.sum()), f'{d.t.mean():.0f}', '--',
                  int((d.ms < sbs_ms).sum()), int((d.ms > sbs_ms).sum())])
filas.append('---')
for m in orden:
    if m not in P.index: continue
    r = P.loc[m]
    if m in ('Regla por tamaño', 'Schedule estático', 'VBS'): filas.append('---')
    filas.append([nom_tex.get(m, m), f2(r.gap_medio), int(r.optimos), f'{r.par10:.0f}',
                  '--' if m in [NOMBRES[c] for c in cfgs] else f'{r["brecha_cerrada_%"]:.0f}',
                  int(r.mejor_que_SBS), int(r.peor_que_SBS)])
tabla('tab_portafolios', 'Comparación de los \\textit{solvers} sin cotas y con cotas y de los enfoques de portafolio (236 instancias, 300\\,s por instancia, validación \\textit{leave-one-out}).',
      'tab:portafolios', ['Método', r'Gap (\%)', 'Óptimos', 'PAR10 (s)', r'Brecha cerrada (\%)', 'Mejor', 'Peor'],
      filas, 'lrrrrrr',
      nota=r'Cada fila es un método. Gap: \textit{gap} medio frente a la mejor solución conocida. '
           r'Óptimos: instancias en que se prueba la optimalidad. PAR10: tiempo medio hasta probar el óptimo, '
           r'contando 3000\,s si no se prueba. En Gap y PAR10, un valor menor es mejor. '
           r'Brecha cerrada: parte de la distancia entre el SBS (' + P.loc[[NOMBRES[c] for c in cfgs], 'gap_medio'].idxmin() + r') y el VBS '
           r'que recupera el método, $100\cdot(\mathrm{gap}_{SBS}-\mathrm{gap})/(\mathrm{gap}_{SBS}-\mathrm{gap}_{VBS})$ (0 = SBS, 100 = VBS). '
           r'Mejor/Peor: instancias con menor/mayor \textit{makespan} que el SBS. '
           r'Sin cotas: Chuffed y Gecode con el modelo original y su VBS, es decir, el portafolio planteado al inicio '
           r'del trabajo; Chuffed V2 no tiene fila sin cotas porque se definió como configuración del modelo con cotas. '
           r'Las demás filas usan el modelo con cotas.')

def nq(modelo, metrica):
    """Nombre del modelo y de la métrica para la tabla de calidad."""
    mod = modelo.replace(', resueltas', '')
    met = {'AUC': 'AUC', 'exactitud': r'Exactitud (\%)', 'MAE (s)': 'Error absoluto medio (s)',
           'mediana error relativo': r'Error relativo mediano (\%)'}[metrica]
    return mod, met
filas = []
for _, r in Q.iterrows():
    a, b = nq(r.modelo, r.metrica)
    v = r.valor * 100 if ('%' in b) else r.valor
    filas.append([a, b, f2(v) if 'AUC' in b else f1(v)])
tabla('tab_ml_calidad', 'Calidad de los modelos de aprendizaje automático (predicciones fuera de muestra, \\textit{leave-one-out}).',
      'tab:ml_calidad', ['Modelo', 'Métrica', 'Valor'], filas, 'llr')

E2 = PI[PI.metodo == 'Schedule estático'].set_index('instancia').loc[ML.index]
d = 100 * (ML.makespan - E2.makespan) / I.loc[ML.index, 'bks']
rng = np.random.default_rng(0); bs = [rng.choice(d.values, len(d)).mean() for _ in range(10000)]
try:
    from scipy.stats import wilcoxon
    pw = wilcoxon(d[d != 0]).pvalue
except Exception:
    pw = np.nan
filas = [['Instancias con resultado distinto', int((d != 0).sum())],
         ['ML mejor / peor', f'{int((d < 0).sum())} / {int((d > 0).sum())}'],
         [r'Diferencia media de gap (puntos)', f'{d.mean():+.3f}'],
         [r'Intervalo de confianza del 95\,\% (\textit{bootstrap})', f'[{np.percentile(bs, 2.5):+.3f}, {np.percentile(bs, 97.5):+.3f}]'],
         ['Mayor ganancia / mayor pérdida (puntos)', f'{(-d).max():.2f} / {d.max():.2f}'],
         ['Prueba de Wilcoxon ($p$)', f'{pw:.3f}']]
tabla('tab_ml_vs_estatico', '\\textit{Schedule} con ML frente al \\textit{schedule} estático (diferencia ML $-$ estático).',
      'tab:ml_vs_estatico', ['', 'Valor'], filas, 'lr')

# comparación pareada de WTA k-NN (ambas) con los demás métodos, y pérdida frente al VBS
MK = PI.pivot(index='instancia', columns='metodo', values='makespan')
MK['Schedule ML (híbrido)'] = ML['makespan']
GK = MK.apply(lambda c: 100 * (c - I.loc[MK.index, 'bks']) / I.loc[MK.index, 'bks'])
def comparar(a, b):
    x = GK[a] - GK[b]
    r = np.random.default_rng(0); bs = [r.choice(x.values, len(x)).mean() for _ in range(10000)]
    try:
        from scipy.stats import wilcoxon
        p = wilcoxon(x[MK[a] != MK[b]]).pvalue
    except Exception:
        p = np.nan
    return x.mean(), np.percentile(bs, 2.5), np.percentile(bs, 97.5), int((MK[a] < MK[b]).sum()), int((MK[a] > MK[b]).sum()), p
ref = 'WTA k-NN (ambas)'
filas = []
for b in ['SUNNY (ambas)', 'Schedule ML (híbrido)', 'Schedule estático', 'Regla por tamaño']:
    m, lo, hi, mej, peo, p = comparar(ref, b)
    filas.append([nom_tex.get(b, b), f'${m:+.2f}$', f'$[{lo:+.2f}, {hi:+.2f}]$', f'{mej} / {peo}'])
tabla('tab_comparaciones', r'Comparación pareada de WTA $k$-NN (ambas) con otros métodos en las 236 instancias.',
      'tab:comparaciones', ['Frente a', 'Diferencia', r'IC 95\,\%', 'WTA mejor / peor'], filas, 'lrcr',
      nota=r'Diferencia: \textit{gap} medio de WTA menos el del otro método, en puntos porcentuales; un valor negativo '
           r'favorece a WTA. IC 95\,\%: intervalo de confianza de esa diferencia, obtenido por \textit{bootstrap} con '
           r'10\,000 remuestreos de las instancias; si no incluye el cero, la diferencia es significativa. '
           r'WTA mejor / peor: instancias en que WTA obtiene un \textit{makespan} menor / mayor que el otro método.')
filas = []
for m in ['SBS', 'Regla por tamaño', 'WTA k-NN (ambas)', 'SUNNY (ambas)', 'Schedule ML (híbrido)', 'Schedule estático']:
    L = GK[m] - GK['VBS']
    nombre = f'SBS ({P.loc[[NOMBRES[c] for c in cfgs], "gap_medio"].idxmin()})' if m == 'SBS' else nom_tex.get(m, m)
    filas.append([nombre, f2(L.mean()), f2(L.quantile(.9)), f2(L.max()), int((L > 2).sum()), int((L > 5).sum())])
tabla('tab_robustez', r'Pérdida frente al VBS (puntos de \textit{gap}) en las 236 instancias.', 'tab:robustez',
      ['Método', 'Media', 'Percentil 90', 'Máxima', r'$> 2$ puntos', r'$> 5$ puntos'], filas, 'lrrrrr')

filas = []
for k in sorted(SK.k.unique()):
    s = SK[SK.k == k].set_index('metodo')
    filas.append([k, f2(s.at['WTA', 'gap_medio']), f2(s.at['SUNNY', 'gap_medio'])])
tabla('tab_sensibilidad_k', 'Sensibilidad al número de vecinos $k$ (características: ambas).', 'tab:sensibilidad_k',
      ['$k$', r'Gap WTA (\%)', r'Gap SUNNY (\%)'], filas, 'rrr')

# ---------------------------------------------------------------- anexo: resultados por instancia
cab = ['Instancia', r'$n\times m$', 'lb', 'ub', 'BKS'] + [NOMBRES[c] for c in cfgs] + [NOMBRES[c] for c in refs] + ['Estático', 'ML']
L = [r'{\scriptsize', r'\begin{longtable}{l' + 'r' * (len(cab) - 1) + '}',
     r'\caption{Resultados por instancia (\textit{makespan} a 300\,s; * óptimo probado; $\dagger$ sin solución, se reporta ub).}\label{tab:anexo_instancias}\\',
     r'\toprule', ' & '.join(cab) + r' \\', r'\midrule', r'\endfirsthead', r'\toprule', ' & '.join(cab) + r' \\', r'\midrule', r'\endhead',
     r'\bottomrule', r'\endfoot']
EST = PI[PI.metodo == 'Schedule estático'].set_index('instancia')
for i in sorted(T.index, key=lambda i: (FAM.index(T.at[i, 'familia']), i)):
    r = T.loc[i]
    def cel(c):
        v = f'{int(r[f"{c}_ms"])}'
        if r.trivial: return v
        return v + ('*' if r[f'{c}_opt'] else '') + (r'$^\dagger$' if r[f'{c}_sin_sol'] else '')
    fila = [i.replace('js', ''), f'{int(r.n)}$\\times${int(r.m)}', int(r.lb), int(r.ub), int(r.bks)] + \
           [cel(c) for c in cfgs + refs]
    fila += ([int(r.ub), int(r.ub)] if r.trivial else [int(EST.at[i, 'makespan']), int(ML.at[i, 'makespan'])])
    L.append(' & '.join(map(str, fila)) + r' \\')
L += [r'\end{longtable}', '}']
(OUT_T / 'anexo_por_instancia.tex').write_text('\n'.join(L) + '\n', encoding='utf-8')

# ---------------------------------------------------------------- comparación con CP-SAT (referencia)
if 'cpsat_v1' in refs:
    NTc = T[~T.trivial].copy()
    NTc['wta'] = MK.loc[NTc.index, 'WTA k-NN (ambas)']
    NTc['wta_gap'] = 100 * (NTc.wta - NTc.bks) / NTc.bks
    NTc['grupo'] = pd.cut(NTc.ops, [0, 150, 300, 600, 10**6], labels=['Hasta 150', '151 a 300', '301 a 600', 'Más de 600'])
    sbs = P.loc[[NOMBRES[c] for c in cfgs], 'gap_medio'].idxmin()
    sbs_c = [c for c in cfgs if NOMBRES[c] == sbs][0]
    filas = []
    for g, d in list(NTc.groupby('grupo', observed=True)) + [('Total', NTc)]:
        if g == 'Total': filas.append('---')
        filas.append([g, len(d), f2(d.cpsat_v1_gap.mean()), f2(d[f'{sbs_c}_gap'].mean()), f2(d.wta_gap.mean()), f2(d.vbs_gap.mean()),
                      int(d.cpsat_v1_opt.sum()), int(d.vbs_opt.sum()), int((d.vbs_ms < d.cpsat_v1_ms).sum())])
    tabla('tab_cpsat', r'CP-SAT frente al portafolio por número de operaciones (modelo con cotas, 300\,s).', 'tab:cpsat',
          ['Operaciones', 'Inst.', r'\multicolumn{4}{c}{Gap medio (\%)}', r'\multicolumn{2}{c}{Óptimos}', 'VBS mejor'],
          [['', '', 'CP-SAT', 'SBS', r'WTA $k$-NN', 'VBS', 'CP-SAT', 'VBS', '']] + ['---'] + filas, 'lrrrrrrrr',
          nota=f'SBS: {sbs}. ' + r'VBS mejor: instancias en que la mejor configuración del portafolio obtiene un \textit{makespan} menor que CP-SAT.')
    txt = (OUT_T / 'tab_cpsat.tex').read_text(encoding='utf-8')
    txt = txt.replace("    \\midrule\n     & ", "    \\cmidrule(lr){3-6}\\cmidrule(lr){7-8}\n     & ", 1)
    (OUT_T / 'tab_cpsat.tex').write_text(txt, encoding='utf-8')

# ---------------------------------------------------------------- anexo: catálogo de características
def num(v):
    v = float(v)
    if v == int(v) and abs(v) < 1e6:
        return str(int(v))
    return f'{v:.3g}'
def tt(x):
    return r'\texttt{' + x.replace('_', r'\_') + '}'
prop = cargar_caracteristicas('propias')
L = [r'{\small', r'\singlespacing', r'\begin{longtable}{>{\ttfamily}l r r r r}',
     r'\caption{Estadísticos de las características propias del JSSP (242 instancias).}\label{tab:anexo_propias}\\',
     r'\toprule', r'\normalfont\textbf{Característica} & \textbf{Media} & \textbf{Desv. est.} & \textbf{Mínimo} & \textbf{Máximo} \\',
     r'\midrule', r'\endfirsthead', r'\toprule',
     r'\normalfont\textbf{Característica} & \textbf{Media} & \textbf{Desv. est.} & \textbf{Mínimo} & \textbf{Máximo} \\',
     r'\midrule', r'\endhead', r'\bottomrule', r'\endfoot']
for c in prop.columns:
    x = prop[c]
    L.append(' & '.join([c.replace('_', r'\_'), num(x.mean()), num(x.std()), num(x.min()), num(x.max())]) + r' \\')
L += [r'\end{longtable}', '}']
(OUT_T / 'anexo_caracteristicas_propias.tex').write_text('\n'.join(L) + '\n', encoding='utf-8')

# ---------------------------------------------------------------- anexo B compacto: características activas
meta = pd.read_csv(RUTAS['meta_mzn2feat'])
act = meta[meta.estado == 'ACTIVA'].feature.tolist()
grupos = [('v\\_', 'Variables'), ('d\\_', 'Tipos de dominio'), ('c\\_', 'Restricciones'),
          ('gc\\_', 'Restricciones globales'), ('o\\_', 'Función objetivo')]
L = [r'\begin{table}[H]', r'  \centering', r'  \scriptsize', r'  \singlespacing',
     r'  \caption{Características de \texttt{mzn2feat} usadas (65 activas).}', r'  \label{tab:anexo_activas}',
     r'  \begin{tabularx}{\textwidth}{>{\raggedright\arraybackslash}p{2.6cm} >{\raggedright\arraybackslash}X}',
     r'    \toprule', r'    \textbf{Grupo} & \textbf{Características} \\', r'    \midrule']
for pre, nom in grupos:
    xs = [f for f in act if f.startswith(pre.replace('\\', ''))]
    L.append(f'    {nom} ({len(xs)}) & ' + ', '.join(r'\texttt{' + f.replace('_', r'\_') + '}' for f in xs) + r' \\')
L += [r'    \bottomrule', r'  \end{tabularx}', r'\end{table}']
(OUT_T / 'anexo_caracteristicas_activas.tex').write_text('\n'.join(L) + '\n', encoding='utf-8')

# ---------------------------------------------------------------- figuras (PDF)
x = np.arange(len(PT)); w = 0.8 / (len(cfgs) + 2)
fig, ax = plt.subplots(figsize=(6.3, 3.2))
for k, c in enumerate(cfgs + ['vbs']):
    ax.bar(x + k * w, PT[f'gap_{c}'], w, label=NOMBRES.get(c, 'VBS'), color=COL[c])
ax.bar(x + (len(cfgs) + 1) * w, PT['gap_heuristica'], w, label='Heurística (ub)', color='#b8b5aa')
ax.set_xticks(x + w * (len(cfgs) + 1) / 2, [t.replace('x', '×') for t in PT.index], rotation=60, fontsize=8)
ax.set_ylabel('Gap medio (%)'); ax.set_xlabel('Tamaño (trabajos × máquinas)'); ax.legend(frameon=False, ncol=4, fontsize=8)
fig.tight_layout(); fig.savefig(OUT_F / 'gap_por_tamano.pdf'); plt.close(fig)

fig, ax = plt.subplots(figsize=(4.4, 2.8))
for c in cfgs + ['vbs']:
    ax.plot(A.segundos, A[f'gap_{c}'], marker='o', label=NOMBRES.get(c, 'VBS'), color=COL[c])
ax.set_xscale('log'); ax.set_xticks(A.segundos, [str(int(s)) for s in A.segundos]); ax.minorticks_off()
ax.set_xlabel('Tiempo (s)'); ax.set_ylabel('Gap medio (%)')
ax.legend(frameon=False, ncol=4, fontsize=8, loc='upper center', bbox_to_anchor=(0.5, -0.24),
          handlelength=1.5, columnspacing=1.0)
fig.tight_layout(); fig.savefig(OUT_F / 'anytime.pdf', bbox_inches='tight'); plt.close(fig)

fig, ax = plt.subplots(figsize=(5.5, 3))
b = np.zeros(len(PF))
for c in cfgs:
    ax.bar(PF.index, PF[f'gana_{c}'], bottom=b, label=NOMBRES[c], color=COL[c]); b += PF[f'gana_{c}'].values
ax.bar(PF.index, PF['empates'], bottom=b, label='Empate', color='#dcd9cf')
ax.set_ylabel('Instancias'); ax.legend(frameon=False, fontsize=8)
fig.tight_layout(); fig.savefig(OUT_F / 'ganador_por_familia.pdf'); plt.close(fig)

fig, ax = plt.subplots(figsize=(4.2, 3))
ax.bar(np.arange(len(E)) - 0.2, E.gap_original, 0.4, label='Modelo original', color='#b8b5aa')
ax.bar(np.arange(len(E)) + 0.2, E.gap_cotas, 0.4, label='Modelo con cotas', color='#2a78d6')
ax.set_xticks(range(len(E)), [{'chuffed': 'Chuffed', 'gecode': 'Gecode', 'cpsat': 'CP-SAT'}[x] for x in E.index]); ax.set_yscale('log'); ax.set_ylabel('Gap medio (%, escala log.)')
ax.legend(frameon=False, fontsize=8); fig.tight_layout(); fig.savefig(OUT_F / 'efecto_cotas.pdf'); plt.close(fig)

fig, ax = plt.subplots(figsize=(4.0, 3.5))
eje_y = 'chuffed_v2' if 'chuffed_v2' in cfgs else 'gecode_v1'
gan = np.select([NT[f'{c}_gana'] for c in cfgs], cfgs, default='empate')
for c in cfgs + ['empate']:
    s_ = gan == c
    ax.scatter(NT.loc[s_, 'chuffed_v1_gap'], NT.loc[s_, f'{eje_y}_gap'], s=10, alpha=.8,
               color=COL.get(c, '#b8b5aa'), label='Empate' if c == 'empate' else f'Gana {NOMBRES[c]}')
mx = max(NT['chuffed_v1_gap'].max(), NT[f'{eje_y}_gap'].max()) * 1.05
ax.plot([0, mx], [0, mx], color='#6b7280', lw=.8, ls='--'); ax.set_xlim(-1, mx); ax.set_ylim(-1, mx)
ax.set_xlabel('Gap Chuffed (%)'); ax.set_ylabel(f'Gap {NOMBRES[eje_y]} (%)'); ax.legend(frameon=False, fontsize=7)
fig.tight_layout(); fig.savefig(OUT_F / 'dispersion_configuraciones.pdf'); plt.close(fig)

orden_f = [m for m in orden if m in P.index and m != 'SBS']
fig, ax = plt.subplots(figsize=(5.6, 3.4))
cols_f = ['#b8b5aa' if m in [NOMBRES[c] for c in cfgs] else COL['vbs'] if m == 'VBS' else COL['chuffed_v1'] for m in orden_f]
ax.barh(orden_f[::-1], P.loc[orden_f[::-1], 'gap_medio'], color=cols_f[::-1])
ax.set_xlim(P.loc[orden_f, 'gap_medio'].min() - 1, P.loc[orden_f, 'gap_medio'].max() + 0.5)
ax.axvline(P.at['SBS', 'gap_medio'], color='#6b7280', ls='--', lw=.8); ax.axvline(P.at['VBS', 'gap_medio'], color=COL['vbs'], ls='--', lw=.8)
ax.set_xlabel('Gap medio (%)'); ax.tick_params(axis='y', labelsize=8)
fig.tight_layout(); fig.savefig(OUT_F / 'portafolios_gap.pdf'); plt.close(fig)

print('Tablas:', sorted(p.name for p in OUT_T.glob('*.tex')))
print('Figuras:', sorted(p.name for p in OUT_F.glob('*.pdf')))
