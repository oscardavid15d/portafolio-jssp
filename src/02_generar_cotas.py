"""
generar_cotas.py  (herramienta de preparación; NO va en el paquete del operador)
Para cada instancia .dzn calcula:
  - cota inferior LB = max(trabajo más largo, máquina más cargada)
  - cota superior UB = mejor makespan entre programas activos de Giffler-Thompson
    construidos con varias reglas de despacho (SPT, LPT, MWKR, LWKR, MOR, FIFO)
y escribe un .dzn nuevo con los parámetros extra `lb` y `ub` (más la regla usada
como comentario). Cada programa heurístico se valida antes de aceptarlo.
Uso: python generar_cotas.py <carpeta_dzn_origen> <carpeta_dzn_destino> [salida_csv]
"""
import re, sys, csv
from pathlib import Path

def leer_dzn(p):
    t = Path(p).read_text()
    n = int(re.search(r'n_jobs\s*=\s*(\d+)', t).group(1))
    m = int(re.search(r'n_machines\s*=\s*(\d+)', t).group(1))
    def mat(name):
        body = re.search(name + r'\s*=\s*\[\|(.*?)\|\]', t, re.S).group(1)
        filas = [list(map(int, f.replace(',', ' ').split())) for f in body.split('|')]
        assert len(filas) == n and all(len(f) == m for f in filas), name
        return filas
    return n, m, mat('machines'), mat('durations'), t

def giffler_thompson(n, m, M, P, regla):
    nxt = [0]*n                    # próxima operación de cada trabajo
    job_ready = [0]*n              # instante en que el trabajo queda libre
    mach_ready = [0]*m
    rem = [sum(P[j]) for j in range(n)]
    start = [[None]*m for _ in range(n)]
    hechas = 0
    while hechas < n*m:
        cand = [j for j in range(n) if nxt[j] < m]
        # operación con menor tiempo de finalización posible
        def ect(j):
            o = nxt[j]; return max(job_ready[j], mach_ready[M[j][o]]) + P[j][o]
        jstar = min(cand, key=ect)
        cmin = ect(jstar); mstar = M[jstar][nxt[jstar]]
        conflicto = [j for j in cand if M[j][nxt[j]] == mstar
                     and (max(job_ready[j], mach_ready[mstar]) < cmin or j == jstar)]
        def prio(j):
            o = nxt[j]; p = P[j][o]
            return {'SPT': p, 'LPT': -p, 'MWKR': -rem[j], 'LWKR': rem[j],
                    'MOR': -(m-o), 'FIFO': job_ready[j]}[regla]
        j = min(conflicto, key=lambda j: (prio(j), j))
        o = nxt[j]; s = max(job_ready[j], mach_ready[mstar])
        start[j][o] = s
        job_ready[j] = mach_ready[mstar] = s + P[j][o]
        rem[j] -= P[j][o]; nxt[j] += 1; hechas += 1
    return max(job_ready), start

def validar(n, m, M, P, start, cmax):
    for j in range(n):
        for o in range(m-1):
            assert start[j][o] + P[j][o] <= start[j][o+1]
    for k in range(m):
        ops = sorted((start[j][o], start[j][o]+P[j][o]) for j in range(n) for o in range(m) if M[j][o] == k)
        for a, b in zip(ops, ops[1:]):
            assert a[1] <= b[0]
    assert cmax == max(start[j][m-1] + P[j][m-1] for j in range(n))

def main(src, dst, salida=None):
    src, dst = Path(src), Path(dst); dst.mkdir(parents=True, exist_ok=True)
    filas = []
    for p in sorted(src.glob('*.dzn')):
        n, m, M, P, texto = leer_dzn(p)
        lb = max(max(sum(r) for r in P),
                 max(sum(P[j][o] for j in range(n) for o in range(m) if M[j][o] == k) for k in range(m)))
        mejor = None
        for regla in ['SPT', 'LPT', 'MWKR', 'LWKR', 'MOR', 'FIFO']:
            cmax, st = giffler_thompson(n, m, M, P, regla)
            validar(n, m, M, P, st, cmax)
            if mejor is None or cmax < mejor[0]:
                mejor = (cmax, regla)
        ub, regla = mejor
        assert lb <= ub
        (dst / p.name).write_text(texto.rstrip() + f"\n% Cotas agregadas por generar_cotas.py (regla {regla})\nlb = {lb};\nub = {ub};\n")
        filas.append({'instancia': p.stem, 'n': n, 'm': m, 'horizonte': sum(map(sum, P)),
                      'lb': lb, 'ub': ub, 'regla_ub': regla})
    if salida:
        with open(salida, 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(filas[0])); w.writeheader(); w.writerows(filas)
    return filas

if __name__ == '__main__':
    main(*sys.argv[1:])
