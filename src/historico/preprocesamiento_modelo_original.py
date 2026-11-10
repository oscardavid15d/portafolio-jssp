"""
preprocesamiento_a10.py

Actividad A10: Preprocesamiento y preparación del conjunto de datos final.
Proyecto de Grado - Universidad del Valle
Autor: Oscar David Imbachi Ordoñez

Pasos ejecutados:
1. Carga y cruce de datos:
   - features.csv (95 características de mzn2feat).
   - resultados_solvers_300s.csv (242 instancias, Chuffed, Gecode, CP-SAT a 300s).
   - bks_completo.csv (242 instancias con Best Known Solutions y cotas inferiores de JSPLib/OR-Library).
2. Cálculo de métricas de calidad y Gaps:
   - Gap porcentual relativo para cada solver: Gap(%) = ((Makespan - BKS) / BKS) * 100
   - Gap del Virtual Best Solver (VBS) y VBS Clásico (Chuffed + Gecode).
3. Preprocesamiento de características estructurales:
   - Limpieza de valores textuales no numéricos (-nan, inf, nan).
   - Detección y eliminación de características con varianza cero (constantes).
   - Imputación con mediana.
   - Normalización formal al rango [-1, 1] (estándar de SUNNY).
4. Generación de artefactos finales:
   - dataset_final_jssp.csv: Base de datos consolidada completa con metadata, BKS, solvers y features.
   - knowledge_base_sunny_normalizada.csv: Matriz de entrada para el modelo k-NN de SUNNY.
   - metadata_features_a10.csv: Inventario de las 95 features (activas vs descartadas).
"""

import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.preprocessing import MinMaxScaler
from sklearn.feature_selection import VarianceThreshold
from sklearn.impute import SimpleImputer

def normalize_name(name):
    n = str(name).strip().lower()
    if n.startswith('ta') and n.endswith('js'):
        return n[:-2]
    return n

def main():
    print("=" * 70)
    print("ACTIVIDAD A10: PREPROCESAMIENTO Y PREPARACION DEL DATASET FINAL")
    print("=" * 70)

    # 1. Cargar archivos
    feat_path = Path("features.csv")
    res_path = Path("resultados_solvers_300s.csv")
    bks_path = Path("bks_completo.csv")

    for p in [feat_path, res_path, bks_path]:
        if not p.exists():
            raise FileNotFoundError(f"No se encontro el archivo requerido: {p}")

    df_feat = pd.read_csv(feat_path)
    df_res = pd.read_csv(res_path)
    df_bks = pd.read_csv(bks_path)

    print(f"-> features.csv: {len(df_feat)} filas, {df_feat.shape[1]} columnas.")
    print(f"-> resultados_solvers_300s.csv: {len(df_res)} filas, {df_res.shape[1]} columnas.")
    print(f"-> bks_completo.csv: {len(df_bks)} filas, {df_bks.shape[1]} columnas.")

    # 2. Estandarizar identificadores para el cruce
    feat_id_col = "instance" if "instance" in df_feat.columns else "instancia"
    df_feat['inst_key'] = df_feat[feat_id_col].apply(normalize_name)
    df_res['inst_key'] = df_res['instancia'].apply(normalize_name)
    df_bks['inst_key'] = df_bks['inst.id'].apply(normalize_name)

    # Renombrar columnas BKS relevantes
    df_bks_clean = df_bks[['inst_key', 'inst.jobs', 'inst.machines', 'inst.opt.bound.lower', 'inst.bks']].copy()
    df_bks_clean = df_bks_clean.rename(columns={
        'inst.jobs': 'n_jobs',
        'inst.machines': 'n_machines',
        'inst.opt.bound.lower': 'lower_bound',
        'inst.bks': 'bks_makespan'
    })
    df_bks_clean['lower_bound'] = pd.to_numeric(df_bks_clean['lower_bound'], errors='coerce')
    df_bks_clean['bks_makespan'] = pd.to_numeric(df_bks_clean['bks_makespan'], errors='coerce')

    # 3. Cruzar los 3 datasets
    merged = pd.merge(df_res, df_bks_clean, on='inst_key', how='inner')
    merged = pd.merge(merged, df_feat, on='inst_key', how='inner')
    print(f"-> Cruce exitoso de las 3 fuentes: {len(merged)} instancias consolidadas.")

    if len(merged) != 242:
        raise ValueError(f"Se esperaban 242 instancias cruzadas, se obtuvieron {len(merged)}")

    # 4. Calcular Gaps porcentuales relativos
    # Gap(%) = ((makespan - BKS) / BKS) * 100
    for s in ['chuffed', 'gecode', 'cpsat']:
        m_col = f"{s}_makespan"
        merged[f"{s}_gap_pct"] = np.round(((merged[m_col] - merged['bks_makespan']) / merged['bks_makespan']) * 100, 3)

    # VBS global (los 3 solvers) y VBS clasico (Chuffed + Gecode)
    merged['vbs_makespan'] = merged[['chuffed_makespan', 'gecode_makespan', 'cpsat_makespan']].min(axis=1)
    merged['vbs_gap_pct'] = np.round(((merged['vbs_makespan'] - merged['bks_makespan']) / merged['bks_makespan']) * 100, 3)

    merged['vbs_cg_makespan'] = merged[['chuffed_makespan', 'gecode_makespan']].min(axis=1)
    merged['vbs_cg_gap_pct'] = np.round(((merged['vbs_cg_makespan'] - merged['bks_makespan']) / merged['bks_makespan']) * 100, 3)

    # Identificar solver ganador en makespan por instancia
    def get_best_solver(row):
        m_c = row['chuffed_makespan']
        m_g = row['gecode_makespan']
        m_cp = row['cpsat_makespan']
        m_min = min(m_c, m_g, m_cp)
        winners = []
        if m_c == m_min: winners.append('chuffed')
        if m_g == m_min: winners.append('gecode')
        if m_cp == m_min: winners.append('cpsat')
        return "/".join(winners)

    merged['best_solver'] = merged.apply(get_best_solver, axis=1)

    # 5. Preprocesamiento de Features estructurales
    ignored_cols = ['inst_key', 'instance', 'instancia', 'n_jobs', 'n_machines',
                    'lower_bound', 'bks_makespan', 'best_solver',
                    'vbs_makespan', 'vbs_gap_pct', 'vbs_cg_makespan', 'vbs_cg_gap_pct']
    solver_cols = [c for c in merged.columns if any(c.startswith(s) for s in ['chuffed_', 'gecode_', 'cpsat_'])]
    all_non_features = set(ignored_cols + solver_cols)

    feature_cols = [c for c in merged.columns if c not in all_non_features]
    print(f"\n-> Extraccion inicial de features: {len(feature_cols)} columnas encontradas.")

    X = merged[feature_cols].copy()
    X = X.replace(["-nan", "nan", "inf", "-inf", np.inf, -np.inf], np.nan)
    X = X.apply(pd.to_numeric, errors='coerce')

    # Detectar nulos y varianza cero
    imputer = SimpleImputer(strategy="median")
    X_imp = imputer.fit_transform(X)

    var_selector = VarianceThreshold(threshold=0.0)
    var_selector.fit(X_imp)
    active_mask = var_selector.get_support()
    active_features = [feature_cols[i] for i, act in enumerate(active_mask) if act]
    discarded_features = [feature_cols[i] for i, act in enumerate(active_mask) if not act]

    print(f"-> Features constantes eliminadas (Varianza 0): {len(discarded_features)}")
    print(f"-> Features activas retenidas: {len(active_features)}")

    # Guardar metadata de features
    meta_records = []
    for f in feature_cols:
        is_active = f in active_features
        vals = X[f].dropna()
        meta_records.append({
            "feature": f,
            "estado": "ACTIVA" if is_active else "DESCARTADA_VARIANZA_CERO",
            "tipo": "Float/Numérica",
            "valores_nulos_originales": int(X[f].isna().sum()),
            "media": float(vals.mean()) if not vals.empty else 0.0,
            "desv_estandar": float(vals.std()) if not vals.empty else 0.0,
            "min": float(vals.min()) if not vals.empty else 0.0,
            "max": float(vals.max()) if not vals.empty else 0.0
        })
    df_meta = pd.DataFrame(meta_records)
    meta_csv = Path("metadata_features_a10.csv")
    df_meta.to_csv(meta_csv, index=False)
    print(f"[OK] Metadatos de features guardados en: {meta_csv}")

    # 6. Normalizacion formal al rango [-1, 1] (SUNNY Standard)
    X_active = X[active_features].copy()
    X_active_imp = pd.DataFrame(imputer.fit_transform(X_active), columns=active_features)

    scaler_sunny = MinMaxScaler(feature_range=(-1, 1))
    X_norm = pd.DataFrame(scaler_sunny.fit_transform(X_active_imp), columns=active_features)

    # 7. Exportar Dataset Maestro Final (dataset_final_jssp.csv)
    # Orden de columnas: metadatos de instancia, BKS, rendimiento de solvers, gaps, features activas limpias
    meta_cols_order = ['instancia', 'n_jobs', 'n_machines', 'lower_bound', 'bks_makespan',
                       'chuffed_makespan', 'chuffed_tiempo', 'chuffed_optimo', 'chuffed_estado', 'chuffed_gap_pct',
                       'gecode_makespan', 'gecode_tiempo', 'gecode_optimo', 'gecode_estado', 'gecode_gap_pct',
                       'cpsat_makespan', 'cpsat_tiempo', 'cpsat_optimo', 'cpsat_estado', 'cpsat_gap_pct',
                       'vbs_makespan', 'vbs_gap_pct', 'vbs_cg_makespan', 'vbs_cg_gap_pct', 'best_solver']

    df_final_master = pd.concat([merged[meta_cols_order], X_active_imp], axis=1)
    final_master_csv = Path("dataset_final_jssp.csv")
    df_final_master.to_csv(final_master_csv, index=False)
    print(f"[OK] Dataset Maestro Final guardado en: {final_master_csv} ({df_final_master.shape[0]} filas, {df_final_master.shape[1]} columnas)")

    # 8. Exportar Knowledge Base Normalizada para SUNNY (k-NN)
    kb_sunny = pd.concat([merged[['instancia', 'bks_makespan', 'vbs_makespan', 'vbs_cg_makespan',
                                 'chuffed_tiempo', 'gecode_tiempo', 'cpsat_tiempo',
                                 'chuffed_gap_pct', 'gecode_gap_pct', 'cpsat_gap_pct']],
                          X_norm], axis=1)
    kb_csv = Path("knowledge_base_sunny_normalizada.csv")
    kb_sunny.to_csv(kb_csv, index=False)
    print(f"[OK] Base de Conocimiento Normalizada (SUNNY) guardada en: {kb_csv} ({kb_sunny.shape[0]} filas, {kb_sunny.shape[1]} columnas)")

    # 9. Estadísticas clave para el reporte
    print("\n" + "=" * 70)
    print("ESTADISTICAS DE DESEMPEÑO Y GAP RESPECTO AL BKS (300s):")
    print("=" * 70)
    for s in ['chuffed', 'gecode', 'cpsat', 'vbs_cg', 'vbs']:
        name = "VBS Clásico (Ch+Ge)" if s == 'vbs_cg' else ("VBS Global (3 Solvers)" if s == 'vbs' else s.upper())
        gap_col = f"{s}_gap_pct"
        mean_gap = merged[gap_col].mean()
        median_gap = merged[gap_col].median()
        opt_count = (merged[gap_col] == 0.0).sum()
        print(f"  {name:<25}: Gap Medio = {mean_gap:8.2f}% | Gap Mediano = {median_gap:6.2f}% | Soluciones Óptimas (Gap=0%) = {opt_count:3d}/242")

    print("\n[OK] ACTIVIDAD A10 FINALIZADA CON EXITO TOTAL.")

if __name__ == "__main__":
    main()
