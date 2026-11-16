# Resumen de resultados

Generado por `python scripts/correr_todo.py`. El informe toma sus cifras solo de aquí. Etiquetas: **MEDIDO** (Google Earth/KML), **OFICIAL** (SEPEC, SIPSA), **SIMULADO** (supuestos del proyecto, §10). Las cifras con Monte Carlo se dan como media e intervalo del 90 %.

## R1. Red y calibración [MEDIDO → CALIBRADO]

| ruta | modo | km medidos | km del grafo | error |
|---|---|---|---|---|
| M01 | via | 15,14 | 15,14 | 0,000 % |
| M02 | rio | 17,38 | 17,38 | 0,000 % |
| M03 | via | 38,90 | 38,90 | 0,000 % |
| M04 | rio | 41,65 | 41,65 | 0,000 % |

Sinuosidad calibrada: río 1,11, carretera 1,27. Grafo: 69 nodos, 148 aristas.

## R2. Diagnóstico de hoy [SIMULADO, 500 corridas por candidata y temporada]

Candidata base del desembarque de la señora: D01a.

| indicador | aguas bajas | aguas altas |
|---|---|---|
| calidad media (0–1) | 0,47 (90 %: 0,29 a 0,70) | 0,35 (90 %: 0,20 a 0,55) |
| % del valor perdido | 49,6 (90 %: 24,4 a 68,6) | 62,3 (90 %: 41,7 a 78,3) |
| COP perdidos al mes | 42,1 M (90 %: 13,9 M a 79,6 M) | 51,7 M (90 %: 24,1 M a 91,6 M) |
| COP/kg perdidos en el río | 199 (90 %: 10 a 844) | 101 (90 %: 14 a 374) |
| COP/kg perdidos en la espera | 4.508 (90 %: 1.981 a 7.377) | 5.924 (90 %: 3.625 a 8.657) |
| COP/kg perdidos en la carretera | 184 (90 %: 55 a 389) | 209 (90 %: 66 a 409) |
| espera / río (veces) | 124 (90 %: 5 a 351) | 165 (90 %: 16 a 403) |
| % corridas con espera > río | 100,0 % | 100,0 % |

Sensibilidad a la ubicación de la señora, aguas bajas (verano): La ubicación no cambia la conclusión: en las 4 candidatas la espera pesa más que el río. El valor perdido varía 1.2 puntos entre candidatas.

Sensibilidad a la ubicación de la señora, aguas altas (invierno): La ubicación no cambia la conclusión: en las 4 candidatas la espera pesa más que el río. El valor perdido varía 6.2 puntos entre candidatas.

## R3. Recomendador y reparto óptimo [SIMULADO, población de ejemplo, aguas bajas]

- Pérdida + viaje con lo que hacen hoy: 2,1 M COP/día.
- Con el reparto óptimo (mismos acopios de hoy): 1,2 M COP/día (42 % menos).
- kg sin destino posible: 30,9 de 245 kg/día.

## R4. Acopios [SIMULADO, 500 corridas]

Regla: vale la pena si VPN > 0 en al menos el 70 % de las corridas.

| acopio | VPN a 5 años | % VPN > 0 | veredicto |
|---|---|---|---|
| San Miguel | 100,4 M (90 %: -129,3 M a 492,4 M) | 61 % | no vale la pena |
| Puente Arimena | -48,2 M (90 %: -90,0 M a 34,4 M) | 10 % | no vale la pena |
| Los tres (Puerto Gaitán + San Miguel + Puente Arimena) | 52,1 M (90 %: -197,5 M a 482,4 M) | 49 % | no vale la pena |

p-mediana: con los 3 acopios de hoy, 1,1 M COP/día; agregando uno en R_META_03, 0,8 M COP/día.

## R5. Bimodal, frío e inversión [SIMULADO, 100 corridas]

| presupuesto | recomendado | inversión | valor salvado al año | VPN a 5 años | % VPN > 0 |
|---|---|---|---|---|---|
| 100,0 M | Acopio nuevo (R4) | 90,0 M | 57,8 M (90 %: 0,0 M a 189,1 M) | 28,4 M | 45 % |
| 250,0 M | Rehabilitar San Miguel + Acopio nuevo (R4) | 130,0 M | 111,5 M (90 %: 8,4 M a 280,9 M) | 85,9 M | 52 % |
| 500,0 M | Rehabilitar San Miguel + Acopio nuevo (R4) | 130,0 M | 111,5 M (90 %: 8,4 M a 280,9 M) | 85,9 M | 52 % |

Cada medida sola:

| medida | inversión | valor salvado al año | VPN a 5 años | % VPN > 0 |
|---|---|---|---|---|
| Cajas térmicas con hielo | 13,5 M | 9,8 M | 5,7 M | 15 % |
| Cajas térmicas con hielo + Fábrica de hielo (hielo a bordo) | 78,5 M | 10,0 M | -165,2 M | 7 % |
| Rehabilitar San Miguel | 49,3 M | 69,2 M | 113,2 M | 61 % |
| Rehabilitar Puente Arimena | 24,9 M | 6,9 M | -44,0 M | 15 % |
| Acopio nuevo (R4) | 94,0 M | 57,8 M | 28,4 M | 45 % |
| Camión refrigerado con ruta (todos los días) | 188,4 M | 153,6 M | -630,7 M | 7 % |
| Camión refrigerado con ruta (cada 3 días) | 188,4 M | 23,7 M | -507,5 M | 1 % |
| Camión refrigerado con ruta (cada 7 días) | 188,4 M | 2,4 M | -415,5 M | 0 % |
| Subsidio de motor | 41,4 M | 18,3 M | 24,5 M | 54 % |
| Mejorar el desembarque de la señora | 28,0 M | 14,9 M | 12,5 M | 33 % |

## R6. Hoy vs propuesta [SIMULADO, población de ejemplo]

Propuesta: Rehabilitar San Miguel + Acopio nuevo (R4), con los pescadores siguiendo el recomendador.

**Aguas bajas (verano)**

| indicador | hoy | propuesta |
|---|---|---|
| COP recibidos al día | $1.364.844 | $2.309.419 |
| COP netos al día (menos el viaje) | $401.893 | $1.734.166 |
| % del valor perdido | 46,1 | 8,7 |
| kg perdidos al día | 41,0 | 18,3 |
| calidad media (0–1) | 0,63 | 0,81 |
| horas hasta la venta | 81,7 | 29,7 |
| km por río | 20,6 | 14,2 |

**Aguas altas (invierno)**

| indicador | hoy | propuesta |
|---|---|---|
| COP recibidos al día | $912.549 | $2.282.294 |
| COP netos al día (menos el viaje) | $23.390 | $1.778.186 |
| % del valor perdido | 63,9 | 9,8 |
| kg perdidos al día | 118,5 | 18,3 |
| calidad media (0–1) | 0,69 | 0,83 |
| horas hasta la venta | 84,1 | 23,4 |
| km por río | 21,0 | 15,6 |

En aguas bajas, la mejora de $1.332.437/día se reparte así: $884.568/día por solo seguir el recomendador (R3, sin invertir) y $447.869/día por la inversión (R5).

Valor salvado al año con la propuesta (Monte Carlo de R5): 111,5 M (90 %: 8,4 M a 280,9 M); VPN 85,9 M, positivo en el 52 % de las corridas (la regla de R4 pide 70 %).
