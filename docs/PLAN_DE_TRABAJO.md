# Plan de trabajo por fases

**Todo funcional:** domingo 15 nov 2026 · **Presentación:** lunes 16 en la mañana · **Inicio:** viernes 13 nov · **Zona horaria:** Bogotá · **Equipo:** Nobara 44 + Claude Code

**Historia que vamos a contar:** problema → **diagnóstico** (hoy) → **solución** (rutas, acopios, bimodal y frío) → **hoy vs propuesta** → demostración de la app.

**Cómo se usa:**
- Una fase = una sesión de Claude Code: modo plan → aprobar → implementar → verificar → commit + push → `/clear`.
- Los prompts están en `docs/PROMPTS_POR_FASE.md`. La terminal y GitHub, en `docs/GUIA_TERMINAL_Y_GITHUB.md`.

**Regla de oro:** al final de cada fase la app abre y funciona.

**Ruta crítica:** 0 → 1 → 2 → 3. Las fases 4 y 5 dependen de la 3, pero no entre sí. La 6 cierra todo.

## Dónde quedamos

> Claude Code actualiza esta sección cada vez que se cierra una sesión (prompt "Cierre de sesión").

- **Última actualización:** 14 nov 2026
- **Fase actual:** 2 cerrada (commit 4805a39, en GitHub) + ajuste: venta río abajo cuando el bote no remonta (pendiente commit)
- **Qué quedó a medias:** geometría del KML para las trazas. El usuario tiene en mente cambios a la Fase 1 y decide al final del proyecto
- **Siguiente paso concreto:** cerrar la Fase 3 (commit) y seguir con la Fase 4 (acopios)
- **Datos pendientes del equipo:** KML de M01–M04; coordenadas de A02, A03, X01 y C01 (el tramo Yucao → boca del Manacacías necesita ×1,86 y la vía a Puente Arimena da 91 km frente al km 68 de la ANI); a qué río desembocan los caños P08–P12 (D5); si Puente Arimena está sobre el Muco y si el Planas y el Guarrojo cruzan la vía. **No habrá datos** de la ubicación real de la señora ni del comprador: quedan simulados

---

## Calendario

| bloque | fase | lo que se ve al final |
|---|---|---|
| Vie 11:00–13:00 | 0. Terminal, repo y esqueleto | `pesca-gaitan` abre la app de inicio; el repo existe en GitHub |
| Vie 14:00–17:00 | 1. Red multimodal y algoritmos de búsqueda (R1) | "Mapa de la red" + "Laboratorio de algoritmos" |
| Vie 17:30–21:30 | 2. **Diagnóstico de hoy** (R2) ★ | "Diagnóstico": **el problema queda demostrado** |
| Sáb 08:00–11:30 | 3. **Recomendador y asignación óptima** (R3) ★ | "¿A dónde llevo mi pescado?" |
| Sáb 12:00–16:00 | 4. Acopios: viabilidad y reubicación (R4) | "Centros de acopio" |
| Sáb 16:30–20:00 | 5. Bimodal, cadena de frío e inversión (R5) | "Bimodal y cadena de frío" |
| Sáb 20:00–22:00 | *colchón* | |
| Dom 08:00–11:00 | 6. Hoy vs propuesta, cartilla, pulido y release (R6) | app final, tag `v1.0` |
| Dom 11:30–16:00 | 7. Informe y presentación | proyecto completo |
| Dom 16:00–20:00 | *colchón + ensayo general* | |
| **Lun mañana** | **presentación** | |

> El domingo en la tarde queda libre como colchón y para ensayar. El lunes no se programa trabajo nuevo.

**Tú, en paralelo, mientras avanza el proyecto:** ir entregando las coordenadas o el KML de los puntos y, si aparece, cualquier dato de §4.6 (congeladores de la señora, cortes de luz, precio en la plaza). Cada dato nuevo se integra con el prompt "datos nuevos".

---

## Fase 0. Terminal, repo y esqueleto

**Tú:**
- Sigue la guía en Nobara: `nobara-sync cli`, `sudo dnf install git gh python3.12`, `gh auth login`.
- Crea el repo público con `gh repo create`.
- Responde D6 (¿individual o en equipo?), o deja el valor por defecto.
- Corrige en Google Earth las coordenadas que proponga Claude (20–30 min).

**Claude Code:**
- Crear la estructura de la especificación §9.1:
  - `pyproject.toml` (networkx, pandas, numpy, matplotlib, folium, streamlit, streamlit-folium, pulp, pyyaml; extra `dev` con pytest) y el comando `pesca-gaitan`;
  - `requirements.txt`, `LICENSE` MIT, `.gitignore` y README mínimo.
- Escribir `parametros.yaml` (desde §10) y `nodos.csv`: acopios, las 3–4 ubicaciones candidatas del desembarque de la señora, comunidad y zonas, todo con `validado = no`.
- Conservar `distancias_medidas.csv`, `sepec_desembarcos_2022.csv` y `precios_referencia.csv`.
- Crear `config.py` y `escenario.py`.
- App mínima: Inicio + "Supuestos y datos" (yaml, distancias medidas con sus capturas).
- Tests de configuración.

**Hecho cuando:**
- [x] `pip install -e ".[dev]"` funciona en Python 3.12.
- [x] `pytest -q` pasa.
- [x] `pesca-gaitan` abre la app.
- [x] Hay primer push al repo público.
- [x] Las decisiones abiertas están en el registro.

---

## Fase 1. Red multimodal y algoritmos de búsqueda (R1)

**Claude Code:**
- `red.py`: ríos con `punto_rio`, confluencias, carretera, transbordos y calibración con M01–M04 (y KML si hay).
- `transporte.py`: velocidad por tipo y sentido, e infactibilidad con su motivo.
- `busqueda.py`: **Dijkstra, A\* y BFS propios**, más la comparación.
- Pantallas "Mapa de la red" (aristas por fuente del dato) y "Laboratorio de algoritmos" (ruta y nodos explorados en el mapa, tabla comparativa).

**Tú:** ¿los ríos y la carretera se ven bien? ¿Los acopios quedan donde son? ¿La comparación de algoritmos se entiende para presentarla?

**Hecho cuando:**
- [x] Tests: el grafo reproduce M01–M04 (±1 %); aguas abajo < aguas arriba; motor < remo; sin río entre cuencas.
- [x] Dijkstra propio = `networkx`; A\* da el mismo costo con igual o menos nodos explorados.
- [x] Existe la tabla Dijkstra vs A\* vs BFS.
- [x] Commit y push `fase 1: red multimodal y busqueda (R1)`.
- [x] Revisión del usuario: los mapas se ven bien y se actualizan con la ruta y el algoritmo elegidos.

---

## Fase 2. Diagnóstico de hoy (R2) ★

**Claude Code:**
- `degradacion.py`: RRS (0 por debajo de −10 °C), estados de conservación (ambiente, icopor con hielo, congelado, falla), calidad por etapas y factor de precio.
- `poblacion.py`: pescadores sintéticos sobre el río real, con volúmenes calibrados al SEPEC 2022 × `factor_subregistro`.
- `cadena_actual.py`:
  - la cadena faena → río → desembarque → espera de 7–15 días → carretera → plaza;
  - una **simulación día a día del congelador** de la señora (capacidad, desborde a icopor, cortes de luz);
  - Monte Carlo;
  - sensibilidad a la ubicación del desembarque.
- Pantalla "Diagnóstico: la situación hoy":
  - mapa de recorridos;
  - indicadores con intervalo;
  - **pérdida por etapa**;
  - distribución por zona.

**Tú:**
- Revisa si el diagnóstico se parece a lo que han visto en campo. Si conseguiste datos de la señora o de los pescadores, este es el momento de ponerlos.
- Esta pantalla es la base de la primera parte de tu presentación.

**Hecho cuando:**
- [x] Tests: calidad monótona, RRS(0) = 1, RRS(−18) = 0, la pérdida por etapa suma el total y misma semilla da el mismo resultado.
- [x] El volumen simulado reproduce el SEPEC 2022 × `factor_subregistro`.
- [x] El inventario del congelador nunca supera su capacidad: el exceso aparece como desborde a icopor.
- [x] Las cifras tienen intervalo y se distingue lo medido de lo simulado.
- [x] Commit y push `fase 2: diagnostico (R2)`.

> **Hito del viernes:** el problema queda demostrado con números y mapa.

---

## Fase 3. Recomendador y asignación óptima (R3) ★

**Claude Code:**
- `asignacion.py`:
  - `recomendar(...)`, que usa la búsqueda de la Fase 1 e incluye rutas bimodales y explicación en texto;
  - el problema de transporte con capacidades y `sin_destino`.
- Pantallas "¿A dónde llevo mi pescado?" (clic en el mapa, tarjeta, ruta coloreada por modo y sentido, alternativas; que se vea bien en celular) y "Toda la flota".

**Tú:**
- Pruébalo como si fueras pescador.
- ~~Desplegar~~: el despliegue se hace al final, en la Fase 6.

**Hecho cuando:**
- [x] Tests: conservación de flujo, capacidades, caso 2 × 2 a mano y **prueba de sentido**.
- [x] La explicación menciona la corriente y el transbordo.
- [ ] Commit y push `fase 3: recomendador (R3)`.

---

## Fase 4. Acopios: viabilidad y reubicación (R4)

**Claude Code:**
- `montecarlo.py`, genérico.
- `ubicacion.py`:
  - viabilidad de Puerto Gaitán, San Miguel y Puente Arimena (escenarios, VPN y regla del 70 %);
  - p-mediana en dos modos (mover los 3, o mantenerlos y agregar k = 1…3), precalculada.
- Pantalla "Centros de acopio": veredictos, mapa actuales vs propuestos, botón "activar en el escenario" y tabla descargable.

**Hecho cuando:**
- [ ] La regla de decisión es explícita.
- [ ] Las ubicaciones caen sobre el río y la pérdida no aumenta con k.
- [ ] La integración con el recomendador funciona.
- [ ] Commit y push.

## Fase 5. Bimodal, cadena de frío e inversión (R5)

**Claude Code:**
- `frio_bimodal.py`: escenarios bimodales con transbordo, camión refrigerado con ruta de recolección cada N días, hielo a bordo, desembarque mejorado y portafolios I1–I7 con su Pareto.
- Pantalla "Bimodal y cadena de frío".

**Tú:** define los costos de I1–I7 con Claude. Si consigues precios reales (caja térmica, hielo, camión), mejor.

**Hecho cuando:**
- [ ] Ningún portafolio excede su presupuesto.
- [ ] Se ve el efecto de cada medida sola y combinada.
- [ ] Commit y push.

## Fase 6. Hoy vs propuesta, cartilla, pulido y release (R6)

**Claude Code:**
- `comparacion.py`: hoy vs propuesta, pescador por pescador y en total, y la cartilla de rutas descargable.
- `correr_todo.py` completo y `outputs/resumen_resultados.md`.
- README final.
- Revisión de textos, tiempos de carga y números mágicos.

**Tú:**
- Elige la combinación final de la propuesta (R3 + R4 + R5).
- En otra carpeta: `pip install git+https://github.com/<usuario>/pesca-puerto-gaitan`, luego `pesca-gaitan`. Tiene que abrir.
- Revisa la app pública desde el celular.

**Hecho cuando:**
- [ ] La pantalla "Hoy vs propuesta" está lista y la cartilla se descarga.
- [ ] Se instala desde GitHub.
- [ ] El repo pasa a público y la app se despliega en Streamlit Community Cloud con link (decisión del 14 nov: solo al final).
- [ ] Hay release `v1.0`.

## Fase 7. Informe, presentación y ensayo

**Tú + Claude:**
- Informe en `docs/informe/informe.md`, con cifras solo de `resumen_resultados.md`.
- Presentación: problema → diagnóstico → algoritmos → solución → hoy vs propuesta → **demostración en vivo** (un pescador del Meta bajo, antes y después) → limitaciones → trabajo futuro (criaderos, app sin conexión).
- Revisión final por una sesión nueva.

**Hecho cuando:**
- [ ] Cada cifra está respaldada.
- [ ] Las limitaciones están declaradas.
- [ ] La demo está ensayada. Abre la app pública 10 minutos antes.

---

## Si vas atrasado (recortes en orden)

1. **R5:** 4 escenarios fijos en vez del portafolio con Pareto.
2. **R4:** solo el modo "mantener y agregar k = 1…3".
3. **R1:** el laboratorio de algoritmos queda como tabla, sin animación en el mapa.
4. **R6:** la cartilla en CSV en vez de PDF.

**Lo que nunca se recorta:** el diagnóstico, el recomendador, "Hoy vs propuesta", la calibración con lo medido, Dijkstra/A\*/BFS con sus tests y la página de supuestos.

## Si trabajan en equipo

Después de la Fase 3 en `main`, cada persona trabaja en una rama con su propia sesión de Claude Code:
- persona A: R4;
- persona B: R5;
- persona C: el informe.

El núcleo (`red`, `busqueda`, `transporte`, `degradacion`, `asignacion`, `escenario`) queda congelado. Cada rama se integra con `gh pr create`.

---

## Registro de decisiones

| fecha | id | decisión | quién |
|---|---|---|---|
| 13 nov | D2 | Multimodal río + carretera desde el inicio | equipo |
| 13 nov | D3 | La inversión de la alcaldía = infraestructura de cadena de frío (I1–I7) | equipo |
| 13 nov | D7 | Acopios: Puerto Gaitán, San Miguel y Puente Arimena. Yucao = comunidad pescadora | equipo |
| 13 nov | D8 | Alcance: transporte + frío + inversión. Criaderos = trabajo futuro | equipo |
| 13 nov | D9 | Algoritmos: Dijkstra, A\*, BFS, transporte, p-mediana | equipo |
| 13 nov | D1 | Todo funcional el domingo 15; presentación el lunes 16 en la mañana | equipo |
| 13 nov | D4 | Sigue abierta, pero no bloquea: todas las coordenadas de `nodos.csv` van con `validado = no` (estimadas por Claude o leídas de las capturas M02/M04). Se pidió exportar el KML de M01–M04 desde Google Earth. Prioridad para corregir: A02, X01 (boca del Manacacías), C01 (Yucao) y A03 | Claude (Fase 0) |
| 13 nov | D5 | Por defecto, los caños P08–P12 son de la cuenca del Meta (al Meta o al Manacacías), con posición de relleno [CONFIRMAR] | Claude (Fase 0) |
| 13 nov | D6 | Individual, en `main`, hasta la Fase 3. Si se suma alguien, se usa la división R4/R5/informe | confirmado por el usuario |
| 13 nov | D10 | El desembarque de la señora está a la orilla del río, ubicación exacta desconocida: se usan candidatas con sensibilidad | equipo |
| 13 nov | D10 | Candidatas: D01a boca del Manacacías (base), D01b Meta bajo (La Virginia), D01c orilla de Yucao, D01d Manacacías arriba de Puerto Gaitán | Claude (Fase 0) |
| 13 nov | — | Malecón de Puerto Gaitán (SEPEC) = nodo `D_MALECON` (desembarque formal), unido a A01 por un transbordo | Claude (Fase 0) |
| 13 nov | — | `factor_subregistro`: volumen real = SEPEC × factor; la parte (factor − 1) × SEPEC pasa por desembarques informales (la señora y los D02) | Claude (Fase 0) |
| 13 nov | — | Veda: la calibración mensual reproduce el SEPEC tal como está (con mayo–julio). Los 270 días de pesca se usan solo para el VPN anual | Claude (Fase 0) |
| 13 nov | — | San Miguel: se calibra solo el total de 5,5 t, repartido por mes con el perfil del Malecón | Claude (Fase 0) |
| 13 nov | — | Precio base = mezcla cachama/bagre (`precios.mezcla_cachama` = 0,5) [SIMULADO] | Claude (Fase 0) |
| 13 nov | — | Las capturas siguen en `docs/evidencias/`. Si el paquete se instala sin el repo, la app dice "captura disponible en el repositorio" | Claude (Fase 0) |
| 14 nov | D4 | Sin KML todavía: las trazas de ríos y vías (`rios.csv`, `vias.csv`) las estimó Claude (`validado = no`). Si llega un KML M0x, su longitud reemplaza a la del CSV; la geometría se integra con "datos nuevos" | Claude (Fase 1) |
| 14 nov | — | Vichada simplificado: A03 sobre el Muco; el Planas y el Guarrojo salen a la vía por V01 y V02 [CONFIRMAR] | Claude (Fase 1) |
| 14 nov | — | Calibración: sinuosidad por modo = km medidos / línea recta; los tramos compartidos (Manacacías malecón → boca) usan esa sinuosidad y los exclusivos se escalan para reproducir la ruta exacta. Ningún factor < 1 (garantiza la heurística admisible de A\*) | Claude (Fase 1) |
| 14 nov | — | Puerto Gaitán por río = malecón (`D_MALECON`), con acceso vial a la plaza A01. Desembarques sin vía: acceso en línea recta × sinuosidad vial [SIMULADO] | Claude (Fase 1) |
| 14 nov | — | La calidad de la matriz origen × acopio de R1 cuenta solo el viaje; la Fase 2 suma faena y espera | Claude (Fase 1) |
| 14 nov | — | Mapas con teselas OpenStreetMap: CartoDB ahora pide clave | Claude (Fase 1) |
| 14 nov | — | Destino de hoy: lo registrado por el SEPEC desembarca en el Malecón (venta directa) y en San Miguel; lo no registrado va donde la señora (Meta, 85 %) y a los cruces con la vía (Vichada, 15 %) | usuario (Fase 2) |
| 14 nov | — | San Miguel: el cuarto frío se abandonó porque no se pudo pagar la luz. Hoy el pescado espera en icopor; R4 decide si recuperarlo (con costo de energía explícito en el VPN) o moverlo | usuario (Fase 2) |
| 14 nov | — | Vichada incluido en el diagnóstico con el 15 % del volumen informal | usuario (Fase 2) |
| 14 nov | — | Diagnóstico = un ciclo del comprador en un mes típico fuera de veda; los indicadores se ponderan por el volumen mensual de cada sitio. Monte Carlo: 500 corridas por candidata y temporada, uniforme en el `rango` de cada parámetro | Claude (Fase 2) |
| 14 nov | — | COP perdidos por etapa: la congelación lenta es etapa propia; el resto se reparte en proporción a la pérdida de calidad de cada etapa (así suman el total aunque el precio sea escalonado) | Claude (Fase 2) |
| 14 nov | — | ~~Bote que no puede remontar: el lote se pierde~~ Reemplazada por la siguiente | Claude (Fase 2) |
| 14 nov | — | Bote que no puede remontar: vende río abajo, en el centro más cercano que alcanza por río (Malecón, San Miguel, la señora o un cruce del Vichada). Con esto la espera pesa más que el río en el 99,6–100 % de las corridas, en las dos temporadas y con las 4 candidatas | usuario (supuesto) |
| 14 nov | D10 | Resuelta: la ubicación real de la señora no se conocerá; las 4 candidatas quedan como SIMULADO definitivo con su sensibilidad | usuario |
| 14 nov | — | Datos del comprador (ciclo en San Miguel, si trae hielo): no habrá; quedan como SIMULADO definitivo | usuario |
| 14 nov | — | Gráficos del diagnóstico con Altair (`st.altair_chart`) para tener tooltips; paleta de referencia azul/naranja | Claude (Fase 2) |
| 14 nov | — | El repo sigue privado y la app no se despliega hasta la Fase 6. El despliegue y el paso a público salen de la Fase 3 | usuario |
| 14 nov | — | Recomendador: compara plaza por río, desembarques con espera (la señora, San Miguel sin frío, cruces del Vichada) y acopios activos (bimodal: cuarto frío + transbordo + carretera). Ordena por plata recibida (métrica §1); si todo es rechazo, por calidad | Claude (Fase 3) |
| 14 nov | — | Espera esperada en un desembarque = (E[ciclo] + 1)/2 ≈ 6 días; donde la señora, probabilidad de congelador = 1 − desborde del Monte Carlo de la Fase 2 | Claude (Fase 3) |
| 14 nov | — | Transbordo solo donde hay quién siga por carretera: acopio activo (vehículo del escenario), comprador en los desembarques (carro) o acceso a pie en el malecón | Claude (Fase 3) |
| 14 nov | — | Problema de transporte con `networkx.min_cost_flow` (décimas de kg y COP enteros); la señora se parte en congelador (con capacidad) e icopor; `sin_destino` garantiza factibilidad | Claude (Fase 3) |
| 14 nov | — | ~~Limitación: el modelo no cobra combustible ni tiempo del pescador~~ Resuelta en la siguiente | Claude (Fase 3) |
| 14 nov | — | El pescador le deja a la señora por tiempo, distancia y porque no todos tienen motor; además, el pescado que llega peor vale menos (ya modelado). Se agrega el costo del viaje: gasolina (1 800 COP/km con motor), tiempo (7 500 COP/h), ida y vuelta [SIMULADO]. El recomendador y el problema de transporte usan la plata neta | usuario + Claude (Fase 3) |
