# Resumen de resultados

Generado por `python scripts/correr_todo.py`. El informe toma sus cifras solo de aquí. Etiquetas: **MEDIDO** (Google Earth/KML), **OFICIAL** (SEPEC, SIPSA), **SIMULADO** (supuestos del proyecto, en `src/pesca/datos/parametros.yaml`). Las cifras con Monte Carlo se dan como media e intervalo del 90 %.

## R1. Red y calibración [MEDIDO → CALIBRADO]

| ruta | modo | km medidos | km del grafo | error |
|---|---|---|---|---|
| M01 | via | 15,14 | 15,14 | 0,000 % |
| M02 | rio | 17,38 | 17,38 | 0,000 % |
| M03 | via | 38,90 | 38,90 | 0,000 % |
| M04 | rio | 41,65 | 41,65 | 0,000 % |

Sinuosidad calibrada: río 1,11, carretera 1,27. Grafo: 70 nodos, 150 aristas.

Dijkstra vs A* vs BFS (madera con motor, aguas bajas, peso = pérdida de calidad):

| ruta | algoritmo | nodos explorados | tramos | % peor que Dijkstra |
|---|---|---|---|---|
| Meta bajo → Puerto Gaitán, plaza de mercado | Dijkstra | 19 | 5 | 0,0 % |
| Meta bajo → Puerto Gaitán, plaza de mercado | A* | 16 | 5 | 0,0 % |
| Meta bajo → Puerto Gaitán, plaza de mercado | BFS | 15 | 5 | 0,0 % |
| Meta alto → Puerto Gaitán, plaza de mercado | Dijkstra | 22 | 7 | 0,0 % |
| Meta alto → Puerto Gaitán, plaza de mercado | A* | 18 | 7 | 0,0 % |
| Meta alto → Puerto Gaitán, plaza de mercado | BFS | 18 | 7 | 0,0 % |
| Yucao → Puerto Gaitán, plaza de mercado | Dijkstra | 21 | 7 | 0,0 % |
| Yucao → Puerto Gaitán, plaza de mercado | A* | 16 | 7 | 0,0 % |
| Yucao → Puerto Gaitán, plaza de mercado | BFS | 17 | 7 | 0,2 % |
| caño Chayva → Puerto Gaitán, plaza de mercado | Dijkstra | 17 | 6 | 0,0 % |
| caño Chayva → Puerto Gaitán, plaza de mercado | A* | 17 | 6 | 0,0 % |
| caño Chayva → Puerto Gaitán, plaza de mercado | BFS | 13 | 6 | 0,0 % |
| Manacacías → San Miguel | Dijkstra | 49 | 8 | 0,0 % |
| Manacacías → San Miguel | A* | 33 | 8 | 0,0 % |
| Manacacías → San Miguel | BFS | 30 | 8 | 0,0 % |
| San Miguel → Malecón de Puerto Gaitán | Dijkstra | 22 | 5 | 0,0 % |
| San Miguel → Malecón de Puerto Gaitán | A* | 16 | 5 | 0,0 % |
| San Miguel → Malecón de Puerto Gaitán | BFS | 23 | 5 | 0,0 % |
| Muco → Puerto Gaitán, plaza de mercado | Dijkstra | 15 | 9 | 0,0 % |
| Muco → Puerto Gaitán, plaza de mercado | A* | 10 | 9 | 0,0 % |
| Muco → Puerto Gaitán, plaza de mercado | BFS | 11 | 9 | 0,0 % |
| Planas → La Cristalina | Dijkstra | 60 | 9 | 0,0 % |
| Planas → La Cristalina | A* | 16 | 9 | 0,0 % |
| Planas → La Cristalina | BFS | 11 | 9 | 0,0 % |

Nodos explorados en total: Dijkstra 225, A* 142 (37 % menos), BFS 138. A* da siempre el mismo costo que Dijkstra; BFS (menos tramos) queda en promedio 0,0 % peor (máximo 0,2 %).

## R2. Diagnóstico de hoy [SIMULADO, 500 corridas por candidata y temporada]

Candidata base del desembarque de la señora: D01a.

| indicador | aguas bajas | aguas altas |
|---|---|---|
| calidad media (0–1) | 0,45 (90 %: 0,28 a 0,69) | 0,35 (90 %: 0,19 a 0,55) |
| % del valor perdido | 50,8 (90 %: 26,3 a 69,2) | 62,3 (90 %: 41,8 a 79,3) |
| COP perdidos al mes | 42,3 M (90 %: 13,4 M a 74,9 M) | 51,0 M (90 %: 21,5 M a 88,5 M) |
| precio base (COP/kg) | 10.129 (90 %: 7.317 a 13.180) | 10.129 (90 %: 7.317 a 13.180) |
| COP/kg perdidos en la faena | 91 (90 %: 16 a 220) | 83 (90 %: 16 a 195) |
| COP/kg perdidos en el río | 183 (90 %: 12 a 809) | 89 (90 %: 12 a 361) |
| COP/kg perdidos en la espera | 4.535 (90 %: 2.027 a 7.473) | 5.794 (90 %: 3.322 a 8.499) |
| COP/kg perdidos por congelación lenta | 142 (90 %: 15 a 424) | 133 (90 %: 16 a 360) |
| COP/kg perdidos en la carretera | 176 (90 %: 60 a 364) | 199 (90 %: 69 a 364) |
| COP/kg que recibe el pescador | 5.002 (90 %: 2.612 a 8.239) | 3.831 (90 %: 1.897 a 6.351) |
| espera / río (veces) | 122 (90 %: 4 a 322) | 172 (90 %: 15 a 428) |
| % corridas con espera > río | 99,8 % | 100,0 % |

Sensibilidad a la ubicación de la señora, aguas bajas (verano): La ubicación no cambia la conclusión: en las 4 candidatas la espera pesa más que el río. El valor perdido varía 1,4 puntos entre candidatas.

Sensibilidad a la ubicación de la señora, aguas altas (invierno): La ubicación no cambia la conclusión: en las 4 candidatas la espera pesa más que el río. El valor perdido varía 6,8 puntos entre candidatas.

## R3. Recomendador y reparto óptimo [SIMULADO, población de ejemplo, aguas bajas]

- Pérdida + viaje con lo que hacen hoy: 2,2 M COP/día.
- Con el reparto óptimo (mismos acopios de hoy): 1,2 M COP/día (42 % menos).
- kg sin destino posible: 30,9 de 245 kg/día.

## R4. Acopios [SIMULADO, 500 corridas]

Regla: vale la pena si VPN > 0 en al menos el 70 % de las corridas.

| acopio | VPN a 5 años | % VPN > 0 | veredicto |
|---|---|---|---|
| San Miguel | 93,2 M (90 %: -124,9 M a 474,4 M) | 60 % | no vale la pena |
| La Cristalina | -69,7 M (90 %: -93,8 M a -46,7 M) | 0 % | no vale la pena |
| Los tres (Puerto Gaitán + San Miguel + La Cristalina) | 23,5 M (90 %: -203,1 M a 379,5 M) | 45 % | no vale la pena |

Reubicación de los acopios: p-mediana sobre los centros poblados del grafo, en la sección «Grafo y acopios».

## R5. Bimodal, frío e inversión [SIMULADO, 100 corridas]

| presupuesto | recomendado | inversión | valor salvado al año | VPN a 5 años | % VPN > 0 |
|---|---|---|---|---|---|
| 100,0 M | Rehabilitar San Miguel + Mejorar el desembarque de la señora | 65,0 M | 76,0 M (90 %: 5,2 M a 150,5 M) | 97,8 M | 69 % |
| 250,0 M | Rehabilitar San Miguel + Mejorar el desembarque de la señora | 65,0 M | 76,0 M (90 %: 5,2 M a 150,5 M) | 97,8 M | 69 % |
| 500,0 M | Rehabilitar San Miguel + Mejorar el desembarque de la señora | 65,0 M | 76,0 M (90 %: 5,2 M a 150,5 M) | 97,8 M | 69 % |

Cada medida sola:

| medida | inversión | valor salvado al año | VPN a 5 años | % VPN > 0 |
|---|---|---|---|---|
| Cajas térmicas con hielo | 12,9 M | 12,7 M | 17,3 M | 25 % |
| Cajas térmicas con hielo + Fábrica de hielo (hielo a bordo) | 78,5 M | 12,7 M | -154,6 M | 9 % |
| Rehabilitar San Miguel | 48,1 M | 62,8 M | 91,2 M | 60 % |
| Rehabilitar La Cristalina | 24,6 M | 0,0 M | -68,1 M | 0 % |
| Camión refrigerado con ruta (todos los días) | 191,6 M | 180,8 M | -507,2 M | 15 % |
| Camión refrigerado con ruta (cada 3 días) | 191,6 M | 29,0 M | -483,0 M | 3 % |
| Camión refrigerado con ruta (cada 7 días) | 191,6 M | 2,4 M | -415,7 M | 0 % |
| Subsidio de motor | 45,1 M | 25,9 M | 48,5 M | 50 % |
| Mejorar el desembarque de la señora | 28,6 M | 15,9 M | 16,1 M | 36 % |

## R6. Hoy vs propuesta [SIMULADO, población de ejemplo]

Propuesta: Rehabilitar San Miguel + Mejorar el desembarque de la señora, con los pescadores siguiendo el recomendador.

**Aguas bajas (verano)**

| indicador | hoy | propuesta |
|---|---|---|
| COP recibidos al día | $1.342.861 | $2.144.346 |
| COP netos al día (menos el viaje) | $379.909 | $1.514.775 |
| % del valor perdido | 46,9 | 15,3 |
| kg perdidos al día | 41,0 | 18,3 |
| calidad media (0–1) | 0,62 | 0,90 |
| horas hasta la venta | 81,7 | 86,2 |
| km por río | 20,6 | 15,7 |

**Aguas altas (invierno)**

| indicador | hoy | propuesta |
|---|---|---|
| COP recibidos al día | $896.270 | $2.046.697 |
| COP netos al día (menos el viaje) | $7.112 | $1.332.879 |
| % del valor perdido | 64,6 | 19,1 |
| kg perdidos al día | 118,5 | 18,3 |
| calidad media (0–1) | 0,68 | 0,84 |
| horas hasta la venta | 84,1 | 48,5 |
| km por río | 21,0 | 25,0 |

En aguas bajas, la mejora de $1.135.030/día se reparte así: $906.551/día por solo seguir el recomendador (R3, sin invertir) y $228.479/día por la inversión (R5).

Valor salvado al año con la propuesta (Monte Carlo de R5): 76,0 M (90 %: 5,2 M a 150,5 M); VPN 97,8 M, positivo en el 69 % de las corridas (la regla de R4 pide 70 %).

## Grafo y acopios

Grafo construido desde `datos/grafo/` (fuentes: DATO, MEDIDO, SIMULADO): 53 nodos y 56 arcos en el CSV; 59 nodos y 117 arcos dirigidos en el grafo (con inversos y nodos divididos).

| tipo de nodo | n |
|---|---|
| punto_rio | 20 |
| punto_via | 11 |
| zona_pesca | 9 |
| centro_poblado | 6 |
| embarcadero | 5 |
| mercado | 1 |
| comunidad | 1 |

| tipo de arco | n |
|---|---|
| rio | 19 |
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

**Búsqueda sobre el grafo por capas** (8 pares, madera a remo, icopor deteriorado): Dijkstra expande 179 estados y A* 126 (30 % menos) con el mismo costo; BFS expande 378. Caso documentado (Meta bajo → plaza, sin hielo): BFS usa 9 tramos y pierde 0,90 de calidad; Dijkstra usa 11 tramos (por San Miguel y camión refrigerado) y pierde 0,17.

**Reacomodo de los acopios (p-mediana sobre centros poblados, curva del codo):**

| p | S | f |
|---|---|---|
| 1 | Puerto Gaitán | 6,460 |
| 2 | Puerto Gaitán, San Miguel | 6,043 |
| 3 | Puerto Gaitán, La Cristalina, San Miguel | 6,043 |
| 4 | Puerto Gaitán, La Cristalina, San Miguel, Domo Planas | 6,043 |
| 5 | Puerto Gaitán, La Cristalina, San Miguel, Domo Planas, San Pedro de Arimena | 6,043 |
| 6 | Puerto Gaitán, La Cristalina, San Miguel, Domo Planas, San Pedro de Arimena, El Porvenir | 6,043 |

**Qué hace cada acopio de hoy** (kg/día de las zonas que atiende y pérdida que evita, en kg equivalentes/día):

| nombre | kg_dia | perdida_evitada_kg_dia |
|---|---|---|
| Puerto Gaitán | 116,433 | 17,250 |
| San Miguel | 22,351 | 0,418 |
| La Cristalina | 0,000 | 0,000 |

- San Miguel en el grafo (comparado con ir directo a la plaza): VPN medio -10,6 M COP, positivo en el 37 % de 200 corridas [SIMULADO].

**Candidatos (centros poblados):** Puerto Gaitán, La Cristalina, San Miguel, Domo Planas, San Pedro de Arimena, El Porvenir. Excluidos: Puente Arimena (sin coordenadas); Murujuy (76 habitantes < P_min = 100; sin acceso confirmado por río ni por vía; sin coordenadas); Puerto Trujillo (58 habitantes < P_min = 100; sin acceso confirmado por río ni por vía; sin coordenadas).

**Acopios elegidos (`S*`, p = 2 en el codo):** Puerto Gaitán, San Miguel, con 6,043 kg equivalentes perdidos por día [SIMULADO].

| metodo | S | f | gap_pct |
|---|---|---|---|
| enumeracion | Puerto Gaitán, San Miguel | 6,043 | 0,000 |
| ilp | Puerto Gaitán, San Miguel | 6,043 | 0,000 |
| busqueda_local | Puerto Gaitán, San Miguel | 6,043 | 0,000 |

- Costo de exigir pueblos (`S*` − p-mediana libre): 0,002 kg/día.
- Centroide de las zonas (confluencia de río Meta y río Meta (traza KML de el porvenir)): 23,580 kg/día, contra 6,460 de la p-mediana con 1 acopio.
- Acopios de hoy (Puerto Gaitán, San Miguel, La Cristalina): 6,043 kg/día.

**Sensibilidad:**

| variable | valor | candidatos | p | S | f | cambia |
|---|---|---|---|---|---|---|
| P_min | 0 | 6 | 2 | Puerto Gaitán, San Miguel | 6,043 | no |
| P_min | 100 | 6 | 2 | Puerto Gaitán, San Miguel | 6,043 | no |
| P_min | 200 | 6 | 2 | Puerto Gaitán, San Miguel | 6,043 | no |
| P_min | 500 | 3 | 2 | Puerto Gaitán, San Miguel | 6,043 | no |
| criterio_acceso | estricto | 6 | 2 | Puerto Gaitán, San Miguel | 6,043 | no |
| criterio_acceso | permisivo | 6 | 2 | Puerto Gaitán, San Miguel | 6,043 | no |
| temporada | aguas_altas | 6 | 2 | Puerto Gaitán, San Miguel | 16,058 | no |
| temporada | aguas_bajas | 6 | 2 | Puerto Gaitán, San Miguel | 6,043 | no |
| embarcacion | madera_remo | 6 | 2 | Puerto Gaitán, San Miguel | 7,220 | no |
| embarcacion | madera_motor | 6 | 1 | Puerto Gaitán | 1,573 | sí |
| embarcacion | aluminio_motor | 6 | 1 | Puerto Gaitán | 1,022 | sí |

`S*` cambia con: embarcacion.

