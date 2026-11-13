# Prompts para Claude Code, fase por fase

## Rutina de cada fase

1. **Pestaña 1** (Konsole, en la carpeta del proyecto, con el `.venv` activo): `claude -n fase-N`. Al ponerle nombre a la sesión, puedes volver a ella con `claude --resume fase-N`.
2. Pega el prompt de la fase. El `/plan` del inicio activa el modo plan para ese mensaje (también puedes pulsar **Shift+Tab** hasta ver `⏸ plan mode on`). En modo plan, Claude no edita nada hasta que apruebes.
3. Lee el plan y corrige **antes** de aprobar.
4. Aprueba. Claude implementa.
5. **Pestaña 2:** deja `pesca-gaitan` corriendo y recarga el navegador para ver los cambios.
6. Revisa: `pytest -q` y la pantalla nueva.
7. "Haz commit y push de la fase N". Aprueba los comandos de git.
8. `/clear` antes de la siguiente fase.

Si algo falla, pega el error tal cual (al final hay un prompt para eso).

---

## Fase 0. Arranque

```
/plan Lee @docs/ESPECIFICACION.md, @docs/PLAN_DE_TRABAJO.md, @docs/contexto_original.md y los CSV de @src/pesca/datos/ (distancias medidas, desembarcos SEPEC 2022 y precios SIPSA).

Todavía no escribas código. Responde:
1. En 8–10 líneas: el problema, la cadena de hoy, qué propone el proyecto y cómo se conectan el motor y la app.
2. Ambigüedades o vacíos que veas. Para las decisiones abiertas (D4, D5, D6), dame tu recomendación. Propón las 3–4 ubicaciones candidatas del desembarque de la señora (D10).
3. Tu plan para la Fase 0: la estructura de §9.1, pyproject.toml con el comando pesca-gaitan (Python 3.12), requirements.txt para Streamlit Cloud, parametros.yaml desde §10, nodos.csv con coordenadas aproximadas (validado = no), config.py, escenario.py, la app mínima (Inicio + "Supuestos y datos") y los tests.

Estoy en Nobara 44 (Fedora). Uso python3.12 en un .venv; no toques el python3 del sistema.
Para las coordenadas, dime cuáles conoces con confianza y cuáles son estimaciones, para corregirlas en Google Earth. Recuerda: San Miguel queda río abajo de Puerto Gaitán, a 41,65 km por río.
```

Cuando termine y hayas corregido las coordenadas:

```
Ya corregí src/pesca/datos/nodos.csv. Decisiones: D4 = ..., D6 = ...
Anótalas en el Registro de decisiones, ajusta la especificación y el yaml donde cambie algo, corre pytest, abre la app para confirmar que carga y haz commit y push de la fase 0.
```

---

## Fase 1. Red multimodal y algoritmos de búsqueda (R1)

```
/plan Fase 1 del plan (R1). Implementa solo esta fase, con sus dos pantallas: "Mapa de la red" y "Laboratorio de algoritmos".

Antes de codificar muéstrame:
- cómo construyes el grafo río + carretera + transbordo a partir de nodos.csv (y de los KML si hay);
- cómo calibras para reproducir M01–M04 (±1 %) y cómo derivas la sinuosidad de los ríos sin medir;
- las firmas de dijkstra, a_estrella y bfs en busqueda.py, qué devuelven (ruta, costo, nodos explorados, orden de exploración) y la heurística de A* con el argumento de por qué es admisible;
- cómo vas a mostrar la exploración en el mapa del laboratorio;
- la lista de tests, incluida la validación contra networkx.
```

---

## Fase 2. Diagnóstico de hoy (R2) ★

```
/plan Fase 2 (R2): el diagnóstico de la situación de hoy. Implementa degradacion.py, poblacion.py, cadena_actual.py y la pantalla "Diagnóstico: la situación hoy".

Antes de codificar muéstrame:
- cómo calibras los volúmenes con sepec_desembarcos_2022.csv × factor_subregistro, y cómo generas los pescadores sintéticos a partir de eso (ubicación sobre el río real, embarcación, kg por faena, días de pesca, desembarque habitual, estado de la nevera de icopor);
- los estados de conservación (ambiente, icopor con hielo, congelado, falla) y las transiciones entre ellos;
- la simulación día a día del congelador de la señora durante un ciclo de 7–15 días: capacidad, desborde a icopor, cortes de luz y descongelación;
- cómo haces la sensibilidad a la ubicación candidata del desembarque;
- qué variables van a Monte Carlo y con qué distribuciones;
- el boceto de la pantalla: indicadores, mapa de recorridos, gráfico de pérdida por etapa y distribución por zona;
- un ejemplo numérico de un pescador del Meta bajo, etapa por etapa.
```

---

## Fase 3. Recomendador y asignación (R3) ★

```
/plan Fase 3 (R3): el recomendador "¿A dónde llevo mi pescado?" y "Toda la flota".

Antes de codificar muéstrame:
- la firma y el retorno de recomendar(...), incluidas las rutas bimodales (río → transbordo → carretera);
- un ejemplo de la explicación para un pescador del Meta bajo a remo y sin hielo;
- cómo resuelves el problema de transporte con capacidades y sin_destino (NetworkX con enteros o PuLP; justifica);
- el boceto de la pantalla (clic en el mapa, tarjeta, ruta coloreada: verde a favor, rojo en contra, gris por carretera; alternativas). Debe verse bien en celular;
- los tests, incluida la prueba de sentido de R3.
```

Revisión del núcleo, en una **sesión nueva** (`/clear`):

```
Revisa src/pesca/red.py, busqueda.py, transporte.py, degradacion.py, cadena_actual.py y asignacion.py contra @docs/ESPECIFICACION.md (§3–§8, R1–R3). No cambies nada. Lista en orden de gravedad: incumplimientos, errores de unidades o de sentido de la corriente, heurística de A* no admisible, números que no estén en el yaml y textos que un pescador no entendería.
```

Preparar el despliegue:

```
Prepara el repo para Streamlit Community Cloud: verifica que requirements.txt instale el paquete pesca y sus dependencias, que nada pesado se calcule al cargar y que el archivo principal sea src/pesca/app/Inicio.py. Haz una instalación limpia con python3.12 en un .venv temporal fuera del proyecto y abre la app. Luego dime los pasos en share.streamlit.io.
```

---

## Fase 4. Centros de acopio (R4)

```
/plan Fase 4 (R4). Crea montecarlo.py genérico y ubicacion.py con:
(a) la viabilidad de Puerto Gaitán, San Miguel y Puente Arimena: escenarios, kg salvados, uso de capacidad, VPN a 5 años y la regla del 70 % con 500 corridas;
(b) la p-mediana con PuLP en dos modos, "mover los 3" y "mantener y agregar k = 1…3", precalculada.

Muéstrame antes la formulación de la p-mediana (variables, objetivo, restricciones), el tamaño del problema, el tiempo estimado del precálculo y el boceto de la pantalla "Centros de acopio", con el botón "activar en el escenario".
```

---

## Fase 5. Bimodal, cadena de frío e inversión (R5)

```
/plan Fase 5 (R5). Propón:
- cómo modelas cada escenario: bimodal con transbordo y camión refrigerado, hielo a bordo y desembarque mejorado;
- los costos y efectos de I1–I7 (van al yaml como simulados) y cómo cada uno modifica el Escenario;
- la enumeración de portafolios y la frontera de Pareto para 3 presupuestos;
- el boceto de la pantalla "Bimodal y cadena de frío", con el efecto de cada medida sola y combinada.
```

---

## Fase 6. Hoy vs propuesta y publicación (R6)

```
/plan Fase 6 (R6). La propuesta final es: <describe la combinación elegida de R3, R4 y R5>.
1) comparacion.py: hoy vs propuesta, pescador por pescador y en total (km, horas, calidad, COP recibidos, kg perdidos), y la cartilla de rutas por zona y embarcación, descargable para imprimir.
2) La pantalla "Hoy vs propuesta".
3) correr_todo.py completo, que genere outputs/resumen_resultados.md con las cifras clave e intervalos.
4) Un README para el repo público.
5) Revisión de textos, tiempos de carga y datos personales.
6) Los comandos para el release v1.0.
```

---

## Fase 7. Informe

```
Redacta el borrador del informe en docs/informe/informe.md. Usa SOLO cifras de outputs/resumen_resultados.md y cita el archivo de origen al lado de cada una. Estructura: problema → la cadena de hoy → datos (medidos, calibrados, simulados) → modelo (grafo multimodal, corriente, degradación) → algoritmos (Dijkstra, A*, BFS comparados; transporte; p-mediana) → diagnóstico → solución → hoy vs propuesta → la app → limitaciones → trabajo futuro (criaderos, app sin conexión). Tono académico, en español.
```

Revisión final, en una **sesión nueva**:

```
Revisa docs/informe/informe.md contra outputs/resumen_resultados.md y @docs/ESPECIFICACION.md. Lista: cifras que no coinciden, afirmaciones sin respaldo, requerimientos sin responder y supuestos simulados presentados como hechos.
```

---

## Prompts de apoyo

**Cuando algo falla:**
```
Este es el error completo:
<pega el traceback, la salida de pytest o el log de Streamlit Cloud>
Encuentra la causa raíz antes de cambiar código y explícamela en 2–3 líneas. Luego corrígela con el cambio mínimo y vuelve a correr los tests.
```

**Cierre de sesión (antes de apagar el PC o salir de la terminal):**
```
Vamos a parar por ahora.
1) Si hay cambios sin terminar, déjalos en un estado en que la app abra, o dime exactamente qué quedó roto.
2) Actualiza la sección "Dónde quedamos" de @docs/PLAN_DE_TRABAJO.md: fecha y hora, fase actual, qué quedó a medias, siguiente paso concreto y datos pendientes. Marca las casillas que ya se cumplan.
3) Haz commit y push con el mensaje "wip: fase N - <resumen corto>".
```

**Para retomar en una sesión nueva:**
```
Lee la sección "Dónde quedamos" de @docs/PLAN_DE_TRABAJO.md y `git log --oneline -15`. Dime en qué fase vamos, qué casillas faltan y cuál es el siguiente paso concreto. No cambies nada todavía.
```

**Si se está desviando:**
```
Detente. Eso no es parte de la fase actual. Vuelve al "hecho cuando" de R<N> y dime qué falta para cumplirlo.
```

**Cuando consigas datos nuevos (ubicación del desembarque, tiempos, precios, KML):**
```
Agregué o cambié datos: <describe qué y dónde>. Intégralos respetando la prioridad de datos de §4.1, marca su fuente, actualiza la tabla §10 y los tests de calibración, y dime qué resultados del diagnóstico y de la solución cambiaron.
```
