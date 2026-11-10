"""
04_caracteristicas_propias.py - Calcula 20 características propias del JSSP a partir del
archivo .txt de cada instancia (tamaño, duraciones, carga de máquinas, rutas y cuello de
botella). No requiere MiniZinc ni mzn2feat.

Nota: en las instancias clásicas cada máquina procesa exactamente n operaciones, por lo que
jf_mach_pmean_cv coincide con jf_load_cv. Se conserva para mantener el conjunto evaluado.

Uso (desde la raíz del repositorio):
    python src/04_caracteristicas_propias.py [carpeta_txt] [salida_csv]
Por defecto: instancias/txt -> resultados/caracteristicas/propias.csv
"""
import os, sys, time, math
import numpy as np, pandas as pd
from pathlib import Path

def parse(p):
    t=open(p).read().split(); n,m=int(t[0]),int(t[1]); v=np.array(t[2:2+2*n*m],int).reshape(n,m,2)
    return n,m,v[:,:,0],v[:,:,1]
def ent(x,k):
    c=np.bincount(x,minlength=k)/len(x); c=c[c>0]; return -(c*np.log(c)).sum()/math.log(k)
def feats(n,m,M,P):
    tot=P.sum(); job=P.sum(1); load=np.bincount(M.ravel(),weights=P.ravel(),minlength=m)
    LB=max(job.max(),load.max())
    f=dict(jf_n=n,jf_m=m,jf_ratio_nm=n/m,jf_ops=n*m,
      jf_p_mean=P.mean(),jf_p_cv=P.std()/P.mean(),jf_p_range=(P.max()-P.min())/P.mean(),
      jf_load_cv=load.std()/load.mean(),jf_bottleneck=load.max()/load.mean(),
      jf_job_cv=job.std()/job.mean(),jf_jobmax_rel=job.max()/job.mean(),
      jf_lb_over_horizon=LB/tot, jf_machine_vs_job=load.max()/job.max(),
      jf_lb_over_meanload=LB/load.mean())
    # routing structure
    pos_ent=np.mean([ent(M[:,o],m) for o in range(m)])
    f['jf_route_pos_entropy']=pos_ent
    # flow-shop-ness: mean pairwise Kendall-like agreement of machine order
    rank=np.argsort(M,axis=1)  # rank[j,mach]=position
    iu=np.triu_indices(m,1); agree=[]
    S=np.sign(rank[:,iu[1]]-rank[:,iu[0]])
    tau=(S@S.T)/len(iu[0]); f['jf_route_kendall']=tau[np.triu_indices(n,1)].mean()
    # first/last machine concentration
    f['jf_first_mach_ent']=ent(M[:,0],m); f['jf_last_mach_ent']=ent(M[:,-1],m)
    # per-machine duration heterogeneity (Mirshekarian-style)
    f['jf_mach_pmean_cv']=np.std([P[M==k].mean() for k in range(m)])/P.mean()
    # 2-machine-split proxy: operations on bottleneck in first half of routes
    b=load.argmax(); f['jf_bneck_pos']=np.mean(np.argwhere(M==b)[:,1])/(m-1)
    return f

if __name__ == "__main__":
    src = Path(sys.argv[1] if len(sys.argv) > 1 else "instancias/txt")
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "resultados/caracteristicas/propias.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = []; t0 = time.time()
    for fn in sorted(src.glob("*.txt")):
        n, m, M, P = parse(fn); r = feats(n, m, M, P); r["instancia"] = fn.stem; rows.append(r)
    pd.DataFrame(rows).set_index("instancia").to_csv(out)
    print(f"{len(rows)} instancias en {time.time() - t0:.2f} s -> {out}")
