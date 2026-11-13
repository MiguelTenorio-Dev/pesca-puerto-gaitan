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

- **Última actualización:** —
- **Fase actual:** 0 (sin empezar)
- **Qué quedó a medias:** —
- **Siguiente paso concreto:** seguir la guía de terminal y pegar el prompt de la Fase 0
- **Datos pendientes del equipo:** coordenadas o KML de los puntos; ubicación del desembarque de la señora

---

## Calendario

| bloque | fase | lo que se ve al final |
|---|---|---|
| Vie 11:00–13:00 | 0. Terminal, repo y esqueleto | `pesca-gaitan` abre la app de inicio; el repo existe en GitHub |
| Vie 14:00–17:00 | 1. Red multimodal y algoritmos de búsqueda (R1) | "Mapa de la red" + "Laboratorio de algoritmos" |
| Vie 17:30–21:30 | 2. **Diagnóstico de hoy** (R2) ★ | "Diagnóstico": **el problema queda demostrado** |
| Sáb 08:00–11:30 | 3. **Recomendador y asignación óptima** (R3) ★ | "¿A dónde llevo mi pescado?" + **primer despliegue público** |
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
- [ ] `pip install -e ".[dev]"` funciona en Python 3.12.
- [ ] `pytest -q` pasa.
- [ ] `pesca-gaitan` abre la app.
- [ ] Hay primer push al repo público.
- [ ] Las decisiones abiertas están en el registro.

---

## Fase 1. Red multimodal y algoritmos de búsqueda (R1)

**Claude Code:**
- `red.py`: ríos con `punto_rio`, confluencias, carretera, transbordos y calibración con M01–M04 (y KML si hay).
- `transporte.py`: velocidad por tipo y sentido, e infactibilidad con su motivo.
- `busqueda.py`: **Dijkstra, A\* y BFS propios**, más la comparación.
- Pantallas "Mapa de la red" (aristas por fuente del dato) y "Laboratorio de algoritmos" (ruta y nodos explorados en el mapa, tabla comparativa).

**Tú:** ¿los ríos y la carretera se ven bien? ¿Los acopios quedan donde son? ¿La comparación de algoritmos se entiende para presentarla?

**Hecho cuando:**
- [ ] Tests: el grafo reproduce M01–M04 (±1 %); aguas abajo < aguas arriba; motor < remo; sin río entre cuencas.
- [ ] Dijkstra propio = `networkx`; A\* da el mismo costo con igual o menos nodos explorados.
- [ ] Existe la tabla Dijkstra vs A\* vs BFS.
- [ ] Commit y push `fase 1: red multimodal y busqueda (R1)`.

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
- [ ] Tests: calidad monótona, RRS(0) = 1, RRS(−18) = 0, la pérdida por etapa suma el total y misma semilla da el mismo resultado.
- [ ] El volumen simulado reproduce el SEPEC 2022 × `factor_subregistro`.
- [ ] El inventario del congelador nunca supera su capacidad: el exceso aparece como desborde a icopor.
- [ ] Las cifras tienen intervalo y se distingue lo medido de lo simulado.
- [ ] Commit y push `fase 2: diagnostico (R2)`.

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
- **Despliega en Streamlit Community Cloud** (guía, sección 5).

**Hecho cuando:**
- [ ] Tests: conservación de flujo, capacidades, caso 2 × 2 a mano y **prueba de sentido**.
- [ ] La explicación menciona la corriente y el transbordo.
- [ ] **La app está pública con link.**
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
- [ ] La app pública está actualizada.
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
| | D4 | | |
| | D5 | | |
| | D6 | | |
| 13 nov | D10 | El desembarque de la señora está a la orilla del río, ubicación exacta desconocida: se usan candidatas con sensibilidad | equipo |
