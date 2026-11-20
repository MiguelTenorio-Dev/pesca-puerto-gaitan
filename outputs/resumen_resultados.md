# Resumen de resultados

Generado por `python scripts/correr_todo.py`. El informe toma sus cifras solo de aquí. Etiquetas: **MEDIDO** (Google Earth/KML), **OFICIAL** (SEPEC, SIPSA), **SIMULADO** (supuestos del proyecto, en `src/pesca/datos/parametros.yaml`). Las cifras con Monte Carlo se dan como media e intervalo del 90 %.

## R1. Red, calibración y búsqueda

El grafo oficial, su calibración con M01–M10 y la comparación Dijkstra / A* / BFS están en la sección «Grafo y acopios». Las simulaciones de R2 a R6 usan una red de trabajo con la misma geometría (las mismas trazas KML del equipo y las mismas trazas aproximadas): 84 nodos y 178 aristas.

## R2. Diagnóstico de hoy [SIMULADO, 500 corridas por candidata y temporada]

Candidata base del desembarque de la señora: D01a.

| indicador | aguas bajas | aguas altas |
|---|---|---|
| calidad media (0–1) | 0,46 (90 %: 0,28 a 0,70) | 0,35 (90 %: 0,21 a 0,55) |
| % del valor perdido | 50,0 (90 %: 24,9 a 68,9) | 62,4 (90 %: 43,3 a 78,0) |
| COP perdidos al mes | 42,9 M (90 %: 13,8 M a 77,2 M) | 52,4 M (90 %: 21,2 M a 89,6 M) |
| precio base (COP/kg) | 10.316 (90 %: 7.407 a 13.689) | 10.316 (90 %: 7.407 a 13.689) |
| COP/kg perdidos en la faena | 87 (90 %: 15 a 223) | 79 (90 %: 16 a 179) |
| COP/kg perdidos en el río | 173 (90 %: 10 a 728) | 87 (90 %: 12 a 287) |
| COP/kg perdidos en la espera | 4.582 (90 %: 1.893 a 7.355) | 5.941 (90 %: 3.509 a 8.727) |
| COP/kg perdidos por congelación lenta | 156 (90 %: 25 a 428) | 146 (90 %: 26 a 373) |
| COP/kg perdidos en la carretera | 162 (90 %: 49 a 321) | 193 (90 %: 61 a 362) |
| COP/kg que recibe el pescador | 5.156 (90 %: 2.901 a 8.367) | 3.871 (90 %: 2.089 a 6.363) |
| espera / río (veces) | 121 (90 %: 5 a 376) | 171 (90 %: 21 a 458) |
| % corridas con espera > río | 100,0 % | 100,0 % |

Sensibilidad a la ubicación de la señora, aguas bajas (verano): La ubicación no cambia la conclusión: en las 4 candidatas la espera pesa más que el río. El valor perdido varía 1,3 puntos entre candidatas.

Sensibilidad a la ubicación de la señora, aguas altas (invierno): La ubicación no cambia la conclusión: en las 4 candidatas la espera pesa más que el río. El valor perdido varía 6,4 puntos entre candidatas.

## R3. Recomendador y reparto óptimo [SIMULADO, población de ejemplo, aguas bajas]

- Pérdida + viaje con lo que hacen hoy: 2,1 M COP/día.
- Con el reparto óptimo (mismos acopios de hoy): 1,3 M COP/día (39 % menos).
- kg sin destino posible: 23,3 de 245 kg/día.

## R4. Acopios [SIMULADO, 500 corridas]

Regla: vale la pena si VPN > 0 en al menos el 70 % de las corridas.

| acopio | VPN a 5 años | % VPN > 0 | veredicto |
|---|---|---|---|
| San Miguel | 122,5 M (90 %: -116,4 M a 537,3 M) | 66 % | no vale la pena |
| La Cristalina | -70,2 M (90 %: -93,2 M a -47,4 M) | 0 % | no vale la pena |
| Los tres (Puerto Gaitán + San Miguel + La Cristalina) | 52,3 M (90 %: -189,6 M a 474,3 M) | 49 % | no vale la pena |

Reubicación de los acopios: p-mediana sobre los centros poblados del grafo, en la sección «Grafo y acopios».

## R5. Bimodal, frío e inversión [SIMULADO, 100 corridas]

| presupuesto | recomendado | inversión | valor salvado al año | VPN a 5 años | % VPN > 0 |
|---|---|---|---|---|---|
| 100,0 M | Rehabilitar San Miguel | 40,0 M | 74,7 M (90 %: 0,0 M a 194,7 M) | 137,8 M | 66 % |
| 250,0 M | Rehabilitar San Miguel | 40,0 M | 74,7 M (90 %: 0,0 M a 194,7 M) | 137,8 M | 66 % |
| 500,0 M | Rehabilitar San Miguel | 40,0 M | 74,7 M (90 %: 0,0 M a 194,7 M) | 137,8 M | 66 % |

Cada medida sola:

| medida | inversión | valor salvado al año | VPN a 5 años | % VPN > 0 |
|---|---|---|---|---|
| Cajas térmicas con hielo | 13,6 M | 8,3 M | -0,1 M | 15 % |
| Cajas térmicas con hielo + Fábrica de hielo (hielo a bordo) | 77,8 M | 8,3 M | -171,7 M | 3 % |
| Rehabilitar San Miguel | 47,3 M | 74,7 M | 137,8 M | 66 % |
| Puntos fríos en pueblos de la ruta (La Cristalina y los que elija el algoritmo) | 40,2 M | 0,0 M | -64,1 M | 0 % |
| Acopio en el Manacacías (reemplaza a La Cristalina) | 94,2 M | 4,5 M | -165,4 M | 0 % |
| Camión refrigerado con ruta (todos los días) | 187,9 M | 196,6 M | -430,7 M | 14 % |
| Camión refrigerado con ruta (cada 3 días) | 187,9 M | 27,3 M | -478,7 M | 1 % |
| Camión refrigerado con ruta (cada 7 días) | 187,9 M | 1,0 M | -412,7 M | 0 % |
| Subsidio de motor | 47,2 M | 25,2 M | 43,8 M | 60 % |

## R6. Hoy vs propuesta [SIMULADO, población de ejemplo]

Propuesta: Rehabilitar San Miguel + Acopio en el Manacacías (reemplaza a La Cristalina) + Puntos fríos en pueblos de la ruta (La Cristalina y los que elija el algoritmo), con los pescadores siguiendo el recomendador.

**Aguas bajas (verano)**

| indicador | hoy | propuesta |
|---|---|---|
| COP recibidos al día | $1.356.227 | $2.283.999 |
| COP netos al día (menos el viaje) | $469.194 | $1.527.389 |
| % del valor perdido | 46,4 | 9,8 |
| kg perdidos al día | 41,0 | 18,4 |
| calidad media (0–1) | 0,63 | 0,80 |
| horas hasta la venta | 81,3 | 35,0 |
| km por río | 19,7 | 17,2 |

**Aguas altas (invierno)**

| indicador | hoy | propuesta |
|---|---|---|
| COP recibidos al día | $877.729 | $2.039.412 |
| COP netos al día (menos el viaje) | $15.951 | $1.320.485 |
| % del valor perdido | 65,3 | 19,4 |
| kg perdidos al día | 125,0 | 18,4 |
| calidad media (0–1) | 0,70 | 0,74 |
| horas hasta la venta | 80,2 | 43,8 |
| km por río | 19,7 | 25,2 |

En aguas bajas, la mejora de $1.057.327/día se reparte así: $806.645/día por solo seguir el recomendador (R3, sin invertir) y $250.682/día por la inversión (R5).

Valor salvado al año con la propuesta (Monte Carlo de R5): 79,2 M (90 %: 0,0 M a 207,8 M); VPN -91,7 M, positivo en el 33 % de las corridas (la regla de R4 pide 70 %).

## Grafo y acopios

Grafo construido desde `datos/grafo/` (fuentes: DATO, MEDIDO, SIMULADO): 55 nodos y 58 arcos en el CSV; 61 nodos y 121 arcos dirigidos en el grafo (con inversos y nodos divididos).

| tipo de nodo | n |
|---|---|
| punto_rio | 22 |
| punto_via | 11 |
| zona_pesca | 9 |
| centro_poblado | 6 |
| embarcadero | 5 |
| mercado | 1 |
| comunidad | 1 |

| tipo de arco | n |
|---|---|
| rio | 21 |
| via | 17 |
| acceso | 14 |
| transbordo | 5 |
| venta | 1 |

**Calibración (Dijkstra por distancia):**

| id | modo | km_medido | km_grafo | error_pct | manda |
|---|---|---|---|---|---|
| M01 | via | 15,140 | 15,140 | 0,001 | medición |
| M02 | rio | 17,380 | 17,380 | 0,001 | medición |
| M03 | via | 38,900 | 38,900 | 0,001 | medición |
| M04 | rio | 41,650 | 40,484 | -2,799 | KML |
| M05 | rio | 73,030 | 72,266 | -1,046 | KML |
| M06 | via | 67,250 | 67,988 | 1,097 | KML |
| M07 | rio | 100,800 | 100,866 | 0,065 | KML |
| M08 | via | 98,140 | 99,096 | 0,974 | KML |
| M09 | via | 75,840 | 75,116 | -0,955 | KML |
| M10 | via | 117,080 | 117,066 | -0,012 | KML |

**Peso de una arista** (San Miguel → Puerto Gaitán por río, 41,65 km contra la corriente, madera a remo, aguas bajas): v_e = 2 km/h, τ = 20,825 h; nevera buena: ΔQ = 0,1134 (Q = 0,887); icopor deteriorado: ΔQ = 0,4978 (Q = 0,502); sin hielo: ΔQ = 1,0204 (Q = 0,000). En aguas altas el tramo es infactible a remo. El mismo trayecto en camión refrigerado por carretera (1,111 h): ΔQ = 0,0061.

**Búsqueda sobre el grafo por capas** (8 pares, madera a remo, icopor deteriorado): Dijkstra expande 185 estados y A* 132 (29 % menos) con el mismo costo; BFS expande 388. Caso documentado (Meta bajo → plaza, sin hielo): BFS usa 9 tramos y pierde 0,74 de calidad; Dijkstra usa 12 tramos (por San Miguel y camión refrigerado) y pierde 0,15.

**Reacomodo de los acopios (p-mediana sobre centros poblados, curva del codo):**

| p | S | f |
|---|---|---|
| 1 | San Miguel | 29,454 |
| 2 | Puerto Gaitán, San Miguel | 23,874 |
| 3 | Puerto Gaitán, San Miguel, Domo Planas | 23,874 |
| 4 | Puerto Gaitán, San Miguel, Domo Planas, San Pedro de Arimena | 23,874 |
| 5 | Puerto Gaitán, San Miguel, Domo Planas, San Pedro de Arimena, El Porvenir | 23,874 |

**Qué hace cada acopio de hoy** (kg/día de las zonas que atiende y pérdida que evita, en kg equivalentes/día):

| nombre | kg_dia | perdida_evitada_kg_dia |
|---|---|---|
| Puerto Gaitán | 34,625 | 5,580 |
| San Miguel | 144,862 | 24,538 |
| La Cristalina | 0,000 | 0,000 |

- San Miguel en el grafo (comparado con ir directo a la plaza): VPN medio 94,2 M COP, positivo en el 47 % de 200 corridas [SIMULADO].
- Acopio del Manacacías (Puerto Trujillo / Murujuy) [CONFIRMAR] en el grafo (comparado con ir directo a la plaza): VPN medio -180,0 M COP, positivo en el 0 % de 200 corridas [SIMULADO].

**Candidatos (centros poblados):** Puerto Gaitán, San Miguel, Domo Planas, San Pedro de Arimena, El Porvenir. Excluidos: La Cristalina (es punto frío (decisión del equipo): ahí se recoge hielo, no se acopia); Puente Arimena (sin coordenadas); Murujuy (76 habitantes < P_min = 100; sin acceso confirmado por río ni por vía; sin coordenadas); Puerto Trujillo (58 habitantes < P_min = 100; sin acceso confirmado por río ni por vía; sin coordenadas).

**Acopios elegidos (`S*`, p = 2 en el codo):** Puerto Gaitán, San Miguel, con 23,874 kg equivalentes perdidos por día [SIMULADO].

| metodo | S | f | gap_pct |
|---|---|---|---|
| enumeracion | Puerto Gaitán, San Miguel | 23,874 | 0,000 |
| ilp | Puerto Gaitán, San Miguel | 23,874 | 0,000 |
| busqueda_local | Puerto Gaitán, San Miguel | 23,874 | 0,000 |

- Costo de exigir pueblos (`S*` − p-mediana libre): 0,016 kg/día.
- Centroide de las zonas (confluencia de río Meta alto y río Meta bajo (traza KML hacia El Porvenir)): 48,541 kg/día, contra 29,454 de la p-mediana con 1 acopio.
- Acopios de hoy (Puerto Gaitán, San Miguel, La Cristalina): 23,874 kg/día.

**Propuesta de reacomodo** (decisión del equipo: La Cristalina pasa a punto frío y su acopio va al Manacacías):

- Hoy: Puerto Gaitán, San Miguel, La Cristalina → 23,874 kg/día.
- Propuesta: Puerto Gaitán, San Miguel, Acopio del Manacacías (Puerto Trujillo / Murujuy) [CONFIRMAR]; puntos fríos: La Cristalina → 23,874 kg/día.

Acopio del Manacacías (búsqueda exhaustiva sobre los puntos del Manacacías, con Puerto Gaitán y San Miguel fijos):

| punto | nombre | f | si_todos |
|---|---|---|---|
| R013 | confluencia de caño Cañomorroco y río Manacacías | 23,874 | 0,379 |
| R018 | confluencia de caño Maiciana y río Manacacías | 23,874 | 0,431 |
| R019 | río Manacacías, km 0.0 de la traza | 23,874 | 0,471 |

Elegido: Acopio del Manacacías (Puerto Trujillo / Murujuy) [CONFIRMAR]; baja la pérdida en 0,000 kg/día.

Puntos fríos (búsqueda exhaustiva sobre pueblo Yucao, San Pedro de Arimena, El Porvenir, con La Cristalina fija):

| p | S | f |
|---|---|---|
| 0 | ninguno | 23,874 |
| 1 | pueblo Yucao | 23,874 |
| 2 | pueblo Yucao, San Pedro de Arimena | 23,874 |
| 3 | pueblo Yucao, San Pedro de Arimena, El Porvenir | 23,874 |

**Rutas de la propuesta: Dijkstra, A\* y BFS** (zona → acopio asignado, bote más común de la flota, escenario base):

| zona | acopio | dq_dijkstra | dq_a_estrella | expandidos_dijkstra | expandidos_a_estrella | tramos_bfs |
|---|---|---|---|---|---|---|
| pueblo Yucao | San Miguel | 0,044 | 0,044 | 27 | 27 | 9 |
| Meta alto | San Miguel | 0,051 | 0,051 | 27 | 27 | 10 |
| Meta bajo | San Miguel | 0,016 | 0,016 | 9 | 9 | 6 |
| Manacacías | Puerto Gaitán | 0,021 | 0,021 | 9 | 9 | 6 |
| Yucao | San Miguel | 0,052 | 0,052 | 27 | 27 | 9 |
| caño Canalete | San Miguel | 0,031 | 0,031 | 13 | 13 | 7 |
| caño Cañomorroco | Puerto Gaitán | 0,013 | 0,013 | 6 | 6 | 5 |
| caño Maiciana | Puerto Gaitán | 0,022 | 0,022 | 9 | 9 | 6 |
| caño Guiva | San Miguel | 0,053 | 0,053 | 27 | 27 | 10 |
| caño Chayva | San Miguel | 0,011 | 0,011 | 6 | 6 | 5 |

DFS: 1 componente(s) conexa(s); Tarjan: 18 puntos de articulación.

**Sensibilidad:**

| variable | valor | candidatos | p | S | f | cambia |
|---|---|---|---|---|---|---|
| P_min | 0 | 5 | 2 | Puerto Gaitán, San Miguel | 23,874 | no |
| P_min | 100 | 5 | 2 | Puerto Gaitán, San Miguel | 23,874 | no |
| P_min | 200 | 5 | 2 | Puerto Gaitán, San Miguel | 23,874 | no |
| P_min | 500 | 2 | 2 | Puerto Gaitán, San Miguel | 23,874 | no |
| criterio_acceso | estricto | 5 | 2 | Puerto Gaitán, San Miguel | 23,874 | no |
| criterio_acceso | permisivo | 5 | 2 | Puerto Gaitán, San Miguel | 23,874 | no |
| temporada | aguas_altas | 5 | 2 | Puerto Gaitán, San Miguel | 23,549 | no |
| temporada | aguas_bajas | 5 | 1 | Puerto Gaitán | 8,775 | sí |
| embarcacion | madera_remo | 5 | 2 | Puerto Gaitán, San Miguel | 25,107 | no |
| embarcacion | madera_motor | 5 | 1 | Puerto Gaitán | 2,189 | sí |
| embarcacion | aluminio_motor | 5 | 1 | Puerto Gaitán | 1,380 | sí |

`S*` cambia con: temporada, embarcacion.

