# Schedule de ejecución basado en portafolios para el Job Shop clásico

Repositorio del trabajo de grado *Schedule de ejecución basado en portafolios para el problema
del Job Shop clásico* (modalidad Trabajo Profesional), Escuela de Ingeniería de Sistemas y
Computación, Universidad del Valle.

- **Autor:** Oscar David Imbachi Ordoñez
- **Directores:** Ph.D. Robinson Andrey Duque Agudelo y Ph.D. Alejandro Arbeláez Rodríguez

El repositorio contiene las instancias, los modelos de MiniZinc, el código, los resultados de
todas las campañas y los programas que generan las tablas y figuras del documento.

## Resumen del trabajo

El portafolio decide, para cada instancia, qué configuraciones ejecutar, en qué orden y durante
cuánto tiempo. Sus configuraciones son Chuffed y Gecode con el modelo con cotas y Chuffed con el
modelo con cotas y estrategia de búsqueda (Chuffed V2). OR-Tools CP-SAT se usa como solver de
referencia, fuera del portafolio. Se comparan la selección de una configuración (WTA k-NN),
SUNNY, un schedule estático y un schedule construido con tres modelos de bosques aleatorios,
con validación leave-one-out sobre 236 instancias y 300 s por instancia.

## Estructura

```
instancias/
  txt/            242 instancias clásicas (abz, dmu, ft, la, orb, swv, ta, yn)
  dzn/            las mismas instancias en formato de datos de MiniZinc
  dzn_cotas/      instancias con la cota inferior (lb) y superior (ub) agregadas
  cotas.csv       lb, ub, horizonte y regla de despacho que dio la ub, por instancia
  bks.csv         mejores soluciones conocidas y cotas de la literatura (ver "Fuentes")
modelos/
  jssp.mzn                  modelo original (dominios de 0 al horizonte)
  jssp_cotas.mzn            modelo con cotas
  jssp_cotas_busqueda.mzn   modelo con cotas y estrategia de búsqueda (Chuffed V2)
src/
  01_convertir_instancias.py     .txt -> .dzn
  02_generar_cotas.py            lb y ub (heurística de Giffler-Thompson con 6 reglas)
  03_caracteristicas_mzn2feat.py características de mzn2feat (requiere sunny-cp)
  04_caracteristicas_propias.py  20 características propias del JSSP
  05_ejecutor/                   ejecución de los solvers y registro de resultados
  comun.py                       rutas y funciones compartidas por 06-09
  06_analisis_campana.py         base de conocimiento y análisis descriptivo de la campaña
  07_portafolios.py              SBS, regla por tamaño, schedule estático, WTA k-NN, SUNNY, VBS
  08_modelo_ml.py                schedule con aprendizaje automático (3 bosques aleatorios)
  09_tablas_figuras.py           tablas (.tex) y figuras (.pdf) del documento
  historico/                     scripts con los que se generó la campaña con el modelo original
resultados/
  campana_modelo_original/  Chuffed, Gecode y CP-SAT con jssp.mzn, 300 s, 242 instancias
  campana_cotas/            campaña con los modelos con cotas, 300 s:
                              D_campana.csv     Chuffed y Gecode (242 instancias)
                              D_chuffed_v2.csv  Chuffed V2 (236 instancias)
                              D_cpsat.csv       CP-SAT, referencia (236 instancias)
  caracteristicas/          características de mzn2feat y propias
  analisis/                 salidas de 06-08 (CSV y figuras PNG)
```

## Requisitos

- Python 3.9 o superior y los paquetes de `requirements.txt`.
- MiniZinc 2.9.1 con Chuffed 0.13.2, Gecode 6.3.0 y OR-Tools CP-SAT 9.12.4544, solo para
  repetir las campañas.
- mzn2feat (incluido en el contenedor Docker `jacopomauro/sunny-cp`), solo para extraer de nuevo
  las características de mzn2feat.

Todos los comandos se ejecutan desde la raíz del repositorio.

## Reproducción

1. **Instancias.** `python src/01_convertir_instancias.py` regenera `instancias/dzn/`.
2. **Cotas.** `python src/02_generar_cotas.py instancias/dzn instancias/dzn_cotas instancias/cotas.csv`
   calcula, para cada instancia:
   - lb = máximo entre la duración del trabajo más largo y la carga de la máquina más ocupada;
   - ub = mejor makespan de un programa activo de Giffler-Thompson con las reglas SPT, LPT,
     MWKR, LWKR, MOR y FIFO (cada programa se valida antes de aceptarlo).

   Reproduce exactamente `instancias/cotas.csv`. En 6 instancias (la06, la10, la12, la14, swv16 y
   swv18) lb = ub, de modo que el óptimo queda probado sin ejecutar ningún solver.
3. **Características.**
   - `python src/03_caracteristicas_mzn2feat.py --model modelos/jssp.mzn --instances instancias/dzn --output resultados/caracteristicas/mzn2feat_modelo_original.csv`
   - `python src/04_caracteristicas_propias.py` (reproduce exactamente `propias.csv`).
4. **Campañas.** En Windows, doble clic en uno de los archivos de `src/05_ejecutor/`:
   - `EJECUTAR_CAMPANA.bat`: Chuffed y Gecode con `jssp_cotas.mzn` (bloque `D_campana`);
   - `EJECUTAR_CHUFFED_V2.bat`: Chuffed con `jssp_cotas_busqueda.mzn` (bloque `D_chuffed_v2`);
   - `EJECUTAR_CPSAT.bat`: CP-SAT con `jssp_cotas.mzn` (bloque `D_cpsat`);
   - `EJECUTAR_MODELO_ORIGINAL.bat`: Chuffed, Gecode y CP-SAT con `jssp.mzn` (bloque
     `D_original`, 242 instancias; resultados en `resultados/campana_modelo_original_dual/`).

   El ejecutor verifica las versiones de MiniZinc y de los solvers, corre primero una prueba con
   ft06 (bloque `0_humo`, debe dar 55), guarda cada ejecución apenas termina y, si se
   interrumpe, continúa donde quedó al volver a abrirlo. `generar_plan.py` regenera `plan.csv` y
   `config.json`. Las ejecuciones se hacen de a dos, cada una fijada a un núcleo físico distinto,
   con un límite de 300 s.
5. **Análisis.** Con los resultados incluidos en el repositorio no hace falta MiniZinc:
   ```
   python src/06_analisis_campana.py
   python src/07_portafolios.py
   python src/08_modelo_ml.py      # el más lento: entrena 3 modelos por cada una de las 236 particiones
   python src/09_tablas_figuras.py
   ```
   Las salidas quedan en `resultados/analisis/`; `09_tablas_figuras.py` genera además las tablas
   y figuras del documento en `resultados/analisis/latex/`.

## Resultados

Cada fila de `resultados/campana_cotas/D_*.csv` es una ejecución (instancia, configuración) con:
makespan final, si se probó el óptimo, estado (`OPTIMAL`, `SATISFIABLE` o `UNKNOWN` si no hubo
solución), tiempo de pared y de MiniZinc, y la **trayectoria** de soluciones (`t:makespan|...`,
instante en segundos en que se encontró cada mejora). Con las trayectorias se puede evaluar
cualquier schedule sin volver a ejecutar los solvers. `registro.txt` es la bitácora de las
sesiones de la campaña y `equipo_*.json` describe el equipo y las versiones de cada sesión.

Cuando una configuración no encuentra solución con el modelo con cotas, su resultado es la
solución de la heurística (ub), que siempre existe.

Cifras principales (236 instancias, 300 s, gap medio frente a la mejor solución conocida):

| Método | Gap medio |
|---|---|
| Chuffed / Gecode / Chuffed V2 | 16.76 % / 21.68 % / 15.08 % |
| Schedule estático (Gecode 2 s, Chuffed V2 60 s, Chuffed 238 s) | 13.31 % |
| Schedule con aprendizaje automático | 13.28 % |
| SUNNY (k = 15) | 13.20 % |
| WTA k-NN (k = 15) | 13.12 % |
| VBS del portafolio | 12.83 % |
| CP-SAT (referencia) | 3.97 % |

`resultados/campana_modelo_original/` contiene la campaña previa con `jssp.mzn` (Chuffed, Gecode
y CP-SAT), el conjunto de datos consolidado y la base de conocimiento que se usaron en las
primeras etapas del trabajo. Los scripts que la generaron están en `src/historico/`. Para repetir
esa campaña con el mismo protocolo de las demás se puede usar `EJECUTAR_MODELO_ORIGINAL.bat`;
como en toda medición de tiempos, los valores pueden variar ligeramente entre ejecuciones.

## Fuentes

- Instancias, mejores soluciones conocidas y cotas de la literatura (`instancias/txt/`,
  `instancias/bks.csv`): T. Weise, *jsspInstancesAndResults*,
  <https://github.com/thomasWeise/jsspInstancesAndResults> (GPL-3.0), que recopila los mejores
  resultados publicados hasta 2020.
- Características genéricas: mzn2feat (Amadini, Gabbrielli y Mauro, 2014), distribuido con
  sunny-cp.

