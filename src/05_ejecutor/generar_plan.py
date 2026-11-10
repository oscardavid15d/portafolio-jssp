"""
generar_plan.py - Genera plan.csv y config.json para el ejecutor.

Bloques:
  0_humo        ft06 con el modelo con cotas, Chuffed y Gecode, 20 s (debe dar 55, óptimo).
                Se repite al inicio de cada sesión como verificación del entorno.
  D_campana     242 instancias x {Chuffed, Gecode}, modelo con cotas (jssp_cotas.mzn),
                búsqueda libre (-f), 300 s.
  D_chuffed_v2  Chuffed con la estrategia de búsqueda del modelo (jssp_cotas_busqueda.mzn),
                300 s, en las 236 instancias donde la cota inferior y la superior difieren.
  D_cpsat       CP-SAT con el modelo con cotas, búsqueda libre, 300 s, en las mismas 236
                instancias (solver de referencia, fuera del portafolio).
  D_original    242 instancias x {Chuffed, Gecode, CP-SAT}, modelo original (jssp.mzn),
                búsqueda libre (-f), 300 s, con el mismo protocolo de los bloques anteriores.

Uso (desde la raíz del repositorio):
    python src/05_ejecutor/generar_plan.py
La columna estimado_s solo sirve para mostrar el tiempo restante; se toma de la campaña
con el modelo original cuando la instancia se resolvió allí.
"""
import csv, json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
AQUI = Path(__file__).resolve().parent
cot = {r['instancia']: r for r in csv.DictReader(open(RAIZ / 'instancias/cotas.csv', encoding='utf-8'))}
r300 = {r['instancia']: r for r in csv.DictReader(
    open(RAIZ / 'resultados/campana_modelo_original/resultados_solvers_300s.csv', encoding='utf-8'))}
VAR = {'V0_actual': ('jssp.mzn', 1), 'V1_cotas': ('jssp_cotas.mzn', 1), 'V2_cotas_busqueda': ('jssp_cotas_busqueda.mzn', 0)}
filas = []

def add(bloque, inst, solver, limite, estimado, variante='V1_cotas', esperado=''):
    modelo, libre = VAR[variante]
    filas.append(dict(id=f'{bloque}|1|{inst}|{variante}|{solver}', bloque=bloque, rep=1, instancia=inst,
                      variante=variante, modelo=modelo, dzn=f"{'dzn' if variante == 'V0_actual' else 'dzn_cotas'}/{inst}.dzn", solver=solver,
                      busqueda_libre=libre, limite_s=limite, modo='serie',
                      estimado_s=round(min(float(estimado), limite + 2), 1), esperado=esperado))

def estimado(inst, s, limite):
    if cot[inst]['lb'] == cot[inst]['ub']:
        return 2
    r = r300.get(inst)
    if r and r[f'{s}_optimo'].strip().lower() == 'true':
        return min(float(r[f'{s}_tiempo']) + 1.5, limite + 2)
    return limite + 1.5

for s in ('chuffed', 'gecode'):
    add('0_humo', 'ft06', s, 20, 2, esperado='55')
orden = sorted(cot, key=lambda i: (int(cot[i]['n']) * int(cot[i]['m']), i))  # de menor a mayor
for i in orden:
    for s in ('chuffed', 'gecode'):
        add('D_campana', i, s, 300, estimado(i, s, 300))
for i in orden:
    if cot[i]['lb'] != cot[i]['ub']:
        add('D_chuffed_v2', i, 'chuffed', 300, estimado(i, 'chuffed', 300), variante='V2_cotas_busqueda')
for i in orden:
    if cot[i]['lb'] != cot[i]['ub']:
        add('D_cpsat', i, 'cpsat', 300, estimado(i, 'cpsat', 300))

def estimado_original(inst, s, limite):
    r = r300.get(inst)
    if r and r[f'{s}_optimo'].strip().lower() == 'true':
        return min(float(r[f'{s}_tiempo']) + 1.5, limite + 2)
    return limite + 1.5

for i in orden:
    for s in ('chuffed', 'gecode', 'cpsat'):
        add('D_original', i, s, 300, estimado_original(i, s, 300), variante='V0_actual')

with open(AQUI / 'plan.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(filas[0])); w.writeheader(); w.writerows(filas)
json.dump({
    "bloques": ["0_humo", "D_campana"],
    "workers_paralelo": 2,
    "margen_python_s": 20,
    "versiones_esperadas": {"org.chuffed.chuffed": "0.13.2", "org.gecode.gecode": "6.3.0", "cp-sat": "9.12.4544"},
    "minizinc_esperado": "2.9.1",
    "solver_ids": {"chuffed": "org.chuffed.chuffed", "gecode": "org.gecode.gecode", "cpsat": "cp-sat"},
    "carga_cpu_maxima_pct": 101
}, open(AQUI / 'config.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
from collections import Counter
print('plan.csv:', dict(Counter(f['bloque'] for f in filas)))
