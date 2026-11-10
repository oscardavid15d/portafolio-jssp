# Resumen de la campaña con el modelo con cotas

- Instancias: 242 (6 con lb = ub, óptimo probado sin solvers: la06, la10, la12, la14, swv16, swv18); se analizan 236.
- Configuraciones: Chuffed, Gecode, Chuffed V2.

| | Chuffed | Gecode | Chuffed V2 | VBS | Heurística |
|---|---|---|---|---|---|
| Óptimos | 36 | 6 | 18 | 36 | — |
| Gap medio (%) | 16.76 | 21.68 | 15.08 | 12.83 | 26.96 |
| PAR10 (s) | 2550 | 2924 | 2774 | 2550 | — |
| Gana (estricto) | 100 | 3 | 100 | — | — |
| Sin solución | 12 | 65 | 24 | — | — |

Mejor configuración individual: Chuffed V2. Margen del portafolio (mejor individual - VBS): 2.24 puntos de gap.

- Chuffed gana en: abz5, abz7, abz9, dmu02, dmu03, dmu04, dmu05, dmu09, dmu11, dmu15, dmu22, dmu25, dmu35, dmu37, dmu41, dmu42, dmu43, ft10, ft20, la11, la15, la21, la22, la24, la25, la26, la27, la29, la30, la31, la32, la33, la34, la35, la36, la37, la38, la39, la40, orb01, orb03, orb04, orb05, orb06, orb08, orb10, swv01, swv02, swv03, swv04, swv05, swv06, swv07, swv08, swv09, ta01js, ta02js, ta03js, ta04js, ta05js, ta06js, ta07js, ta08js, ta09js, ta10js, ta12js, ta13js, ta14js, ta15js, ta16js, ta17js, ta18js, ta19js, ta20js, ta21js, ta22js, ta23js, ta24js, ta25js, ta26js, ta27js, ta28js, ta29js, ta30js, ta32js, ta34js, ta35js, ta37js, ta39js, ta40js, ta41js, ta44js, ta45js, ta48js, ta56js, ta59js, ta62js, ta65js, yn3, yn4
- Gecode gana en: ta42js, ta57js, ta68js
- Chuffed V2 gana en: abz8, dmu01, dmu06, dmu07, dmu08, dmu10, dmu12, dmu13, dmu14, dmu16, dmu17, dmu18, dmu19, dmu20, dmu21, dmu23, dmu24, dmu26, dmu27, dmu28, dmu29, dmu30, dmu31, dmu32, dmu34, dmu36, dmu38, dmu39, dmu40, dmu44, dmu45, dmu46, dmu47, dmu48, dmu49, dmu50, dmu51, dmu52, dmu53, dmu54, dmu55, dmu56, dmu57, dmu58, dmu59, dmu60, dmu61, dmu62, dmu63, dmu64, dmu65, dmu66, dmu67, dmu68, dmu69, dmu70, dmu71, dmu72, dmu73, dmu74, dmu75, dmu76, dmu77, dmu78, dmu79, dmu80, la28, swv10, swv11, swv12, swv13, swv14, swv15, swv17, swv19, ta11js, ta31js, ta33js, ta36js, ta38js, ta43js, ta46js, ta47js, ta49js, ta50js, ta51js, ta52js, ta53js, ta54js, ta55js, ta58js, ta61js, ta63js, ta66js, ta67js, ta69js, ta70js, ta73js, yn1, yn2

Ver por_tamano.csv, por_familia.csv, anytime.csv y efecto_cotas.csv.