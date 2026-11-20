# Resumen de resultados

Generado por `python scripts/correr_todo.py`. El informe toma sus cifras solo de aquí. Etiquetas: **MEDIDO** (Google Earth/KML), **OFICIAL** (SEPEC, SIPSA), **SIMULADO** (supuestos del proyecto, en `src/pesca/datos/parametros.yaml`). Las cifras con Monte Carlo se dan como media e intervalo del 90 %.

## R1. Red, calibración y búsqueda

El grafo oficial, su calibración con M01–M10 y la comparación Dijkstra / A* / BFS están en la sección «Grafo y acopios». Las simulaciones de R2 a R6 usan una red de trabajo con la misma geometría (las mismas trazas KML del equipo y las mismas trazas aproximadas): 84 nodos y 178 aristas.

## R2. Diagnóstico de hoy [SIMULADO, 500 corridas por candidata y temporada]

Candidata base del desembarque de la señora: D01a.

| indicador | aguas bajas | aguas altas |
|---|---|---|
| calidad media (0–1) | 0,46 (90 %: 0,28 a 0,70) | 0,36 (90 %: 0,21 a 0,54) |
| % del valor perdido | 50,1 (90 %: 25,9 a 68,8) | 62,0 (90 %: 41,8 a 78,4) |
| COP perdidos al mes | 41,8 M (90 %: 13,3 M a 74,1 M) | 50,7 M (90 %: 21,4 M a 87,7 M) |
| precio base (COP/kg) | 10.129 (90 %: 7.317 a 13.180) | 10.129 (90 %: 7.317 a 13.180) |
| COP/kg perdidos en la faena | 92 (90 %: 17 a 228) | 84 (90 %: 17 a 207) |
| COP/kg perdidos en el río | 178 (90 %: 13 a 791) | 87 (90 %: 12 a 349) |
| COP/kg perdidos en la espera | 4.493 (90 %: 1.964 a 7.293) | 5.781 (90 %: 3.375 a 8.542) |
| COP/kg perdidos por congelación lenta | 146 (90 %: 17 a 394) | 137 (90 %: 19 a 355) |
| COP/kg perdidos en la carretera | 161 (90 %: 52 a 338) | 188 (90 %: 64 a 378) |
| COP/kg que recibe el pescador | 5.059 (90 %: 2.777 a 8.101) | 3.853 (90 %: 2.000 a 6.281) |
| espera / río (veces) | 119 (90 %: 4 a 322) | 173 (90 %: 16 a 436) |
| % corridas con espera > río | 100,0 % | 100,0 % |

Sensibilidad a la ubicación de la señora, aguas bajas (verano): La ubicación no cambia la conclusión: en las 4 candidatas la espera pesa más que el río. El valor perdido varía 1,2 puntos entre candidatas.

Sensibilidad a la ubicación de la señora, aguas altas (invierno): La ubicación no cambia la conclusión: en las 4 candidatas la espera pesa más que el río. El valor perdido varía 6,6 puntos entre candidatas.

## R3. Recomendador y reparto óptimo [SIMULADO, población de ejemplo, aguas bajas]

- Pérdida + viaje con lo que hacen hoy: 2,1 M COP/día.
- Con el reparto óptimo (mismos acopios de hoy): 1,3 M COP/día (39 % menos).
- kg sin destino posible: 23,3 de 245 kg/día.

## R4. Acopios [SIMULADO, 500 corridas]

Regla: vale la pena si VPN > 0 en al menos el 70 % de las corridas.

| acopio | VPN a 5 años | % VPN > 0 | veredicto |
|---|---|---|---|
| San Miguel | 90,7 M (90 %: -122,1 M a 452,5 M) | 61 % | no vale la pena |
| La Cristalina | -69,7 M (90 %: -93,8 M a -46,7 M) | 0 % | no vale la pena |
| Los tres (Puerto Gaitán + San Miguel + La Cristalina) | 21,0 M (90 %: -196,7 M a 398,3 M) | 43 % | no vale la pena |

Reubicación de los acopios: p-mediana sobre los centros poblados del grafo, en la sección «Grafo y acopios».

## R5. Bimodal, frío e inversión [SIMULADO, 100 corridas]

| presupuesto | recomendado | inversión | valor salvado al año | VPN a 5 años | % VPN > 0 |
|---|---|---|---|---|---|
| 100,0 M | Rehabilitar San Miguel + Mejorar el desembarque de la señora | 65,0 M | 78,4 M (90 %: 7,6 M a 161,0 M) | 106,2 M | 71 % |
| 250,0 M | Rehabilitar San Miguel + Mejorar el desembarque de la señora | 65,0 M | 78,4 M (90 %: 7,6 M a 161,0 M) | 106,2 M | 71 % |
| 500,0 M | Rehabilitar San Miguel + Mejorar el desembarque de la señora | 65,0 M | 78,4 M (90 %: 7,6 M a 161,0 M) | 106,2 M | 71 % |

Cada medida sola:

| medida | inversión | valor salvado al año | VPN a 5 años | % VPN > 0 |
|---|---|---|---|---|
| Cajas térmicas con hielo | 12,9 M | 11,6 M | 13,6 M | 24 % |
| Cajas térmicas con hielo + Fábrica de hielo (hielo a bordo) | 78,5 M | 11,7 M | -158,3 M | 7 % |
| Rehabilitar San Miguel | 48,1 M | 64,8 M | 98,4 M | 64 % |
| Rehabilitar La Cristalina | 24,6 M | 0,0 M | -68,1 M | 0 % |
| Camión refrigerado con ruta (todos los días) | 191,6 M | 183,4 M | -462,0 M | 16 % |
| Camión refrigerado con ruta (cada 3 días) | 191,6 M | 28,5 M | -472,8 M | 3 % |
| Camión refrigerado con ruta (cada 7 días) | 191,6 M | 1,5 M | -413,7 M | 0 % |
| Subsidio de motor | 44,8 M | 27,4 M | 53,9 M | 53 % |
| Mejorar el desembarque de la señora | 28,6 M | 15,8 M | 15,8 M | 33 % |

## R6. Hoy vs propuesta [SIMULADO, población de ejemplo]

Propuesta: Rehabilitar San Miguel + Mejorar el desembarque de la señora, con los pescadores siguiendo el recomendador.

**Aguas bajas (verano)**

| indicador | hoy | propuesta |
|---|---|---|
| COP recibidos al día | $1.346.180 | $2.135.356 |
| COP netos al día (menos el viaje) | $459.147 | $1.539.390 |
| % del valor perdido | 46,8 | 15,6 |
| kg perdidos al día | 41,0 | 18,4 |
| calidad media (0–1) | 0,62 | 0,91 |
| horas hasta la venta | 81,3 | 89,6 |
| km por río | 19,7 | 15,3 |

**Aguas altas (invierno)**

| indicador | hoy | propuesta |
|---|---|---|
| COP recibidos al día | $869.338 | $2.001.283 |
| COP netos al día (menos el viaje) | $7.560 | $1.284.503 |
| % del valor perdido | 65,6 | 20,9 |
| kg perdidos al día | 125,0 | 18,4 |
| calidad media (0–1) | 0,69 | 0,84 |
| horas hasta la venta | 80,2 | 53,7 |
| km por río | 19,7 | 25,6 |

En aguas bajas, la mejora de $1.079.374/día se reparte así: $816.691/día por solo seguir el recomendador (R3, sin invertir) y $262.683/día por la inversión (R5).

Valor salvado al año con la propuesta (Monte Carlo de R5): 78,4 M (90 %: 7,6 M a 161,0 M); VPN 106,2 M, positivo en el 71 % de las corridas (la regla de R4 pide 70 %).

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
| 3 | Puerto Gaitán, La Cristalina, San Miguel | 23,874 |
| 4 | Puerto Gaitán, La Cristalina, San Miguel, Domo Planas | 23,874 |
| 5 | Puerto Gaitán, La Cristalina, San Miguel, Domo Planas, San Pedro de Arimena | 23,874 |
| 6 | Puerto Gaitán, La Cristalina, San Miguel, Domo Planas, San Pedro de Arimena, El Porvenir | 23,874 |

**Qué hace cada acopio de hoy** (kg/día de las zonas que atiende y pérdida que evita, en kg equivalentes/día):

| nombre | kg_dia | perdida_evitada_kg_dia |
|---|---|---|
| Puerto Gaitán | 34,625 | 5,580 |
| San Miguel | 144,862 | 24,538 |
| La Cristalina | 0,000 | 0,000 |

- San Miguel en el grafo (comparado con ir directo a la plaza): VPN medio 49,8 M COP, positivo en el 42 % de 200 corridas [SIMULADO].

**Candidatos (centros poblados):** Puerto Gaitán, La Cristalina, San Miguel, Domo Planas, San Pedro de Arimena, El Porvenir. Excluidos: Puente Arimena (sin coordenadas); Murujuy (76 habitantes < P_min = 100; sin acceso confirmado por río ni por vía; sin coordenadas); Puerto Trujillo (58 habitantes < P_min = 100; sin acceso confirmado por río ni por vía; sin coordenadas).

**Acopios elegidos (`S*`, p = 2 en el codo):** Puerto Gaitán, San Miguel, con 23,874 kg equivalentes perdidos por día [SIMULADO].

| metodo | S | f | gap_pct |
|---|---|---|---|
| enumeracion | Puerto Gaitán, San Miguel | 23,874 | 0,000 |
| ilp | Puerto Gaitán, San Miguel | 23,874 | 0,000 |
| busqueda_local | Puerto Gaitán, San Miguel | 23,874 | 0,000 |

- Costo de exigir pueblos (`S*` − p-mediana libre): 0,016 kg/día.
- Centroide de las zonas (confluencia de río Meta alto y río Meta bajo (traza KML hacia El Porvenir)): 48,541 kg/día, contra 29,454 de la p-mediana con 1 acopio.
- Acopios de hoy (Puerto Gaitán, San Miguel, La Cristalina): 23,874 kg/día.

**Sensibilidad:**

| variable | valor | candidatos | p | S | f | cambia |
|---|---|---|---|---|---|---|
| P_min | 0 | 6 | 2 | Puerto Gaitán, San Miguel | 23,874 | no |
| P_min | 100 | 6 | 2 | Puerto Gaitán, San Miguel | 23,874 | no |
| P_min | 200 | 6 | 2 | Puerto Gaitán, San Miguel | 23,874 | no |
| P_min | 500 | 3 | 2 | Puerto Gaitán, San Miguel | 23,874 | no |
| criterio_acceso | estricto | 6 | 2 | Puerto Gaitán, San Miguel | 23,874 | no |
| criterio_acceso | permisivo | 6 | 2 | Puerto Gaitán, San Miguel | 23,874 | no |
| temporada | aguas_altas | 6 | 2 | Puerto Gaitán, San Miguel | 23,549 | no |
| temporada | aguas_bajas | 6 | 1 | Puerto Gaitán | 8,775 | sí |
| embarcacion | madera_remo | 6 | 2 | Puerto Gaitán, San Miguel | 25,107 | no |
| embarcacion | madera_motor | 6 | 1 | Puerto Gaitán | 2,189 | sí |
| embarcacion | aluminio_motor | 6 | 1 | Puerto Gaitán | 1,380 | sí |

`S*` cambia con: temporada, embarcacion.

