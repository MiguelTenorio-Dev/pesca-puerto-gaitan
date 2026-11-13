# Proyecto: transporte y cadena de frío del pescado en Puerto Gaitán (Meta)

Proyecto universitario de ingeniería con entrega el domingo 15 de noviembre de 2026.

El pescado pierde valor entre la captura y la venta porque el transporte es largo, a veces va contra la corriente y no hay cadena de frío. El proyecto:
1. **diagnostica** la cadena de hoy, pescador por pescador, con datos casi reales;
2. **propone una solución** con grafos y optimización: rutas, acopios, rutas bimodales río + carretera, frío e inversión;
3. la muestra en una **app web pública en Streamlit**, que incluye un recomendador tipo "Uber" para pescadores.

Responde siempre en español. El código y los comentarios van en español, con nombres sin tildes en snake_case. La interfaz usa español claro, entendible para pescadores.

## Documentos fuente
Léelos antes de planear cualquier fase:
- `docs/ESPECIFICACION.md`: cadena actual, datos, modelos, algoritmos, R1–R6 con su "hecho cuando", pantallas, supuestos y decisiones. Es la fuente de verdad.
- `docs/PLAN_DE_TRABAJO.md`: fases, checklist y registro de decisiones.
- `docs/contexto_original.md`: documento original del curso. Solo referencia. Los criaderos que menciona quedaron fuera de alcance.

## Cómo trabajamos
- Trabajamos una fase a la vez, la que el usuario pida, y cada fase empieza en modo plan.
- Cada fase entrega motor + pruebas + su pantalla. La app tiene que seguir abriendo al final de cada fase.
- Antes de cerrar una fase:
  1. corre `pytest -q` y abre la pantalla de la fase;
  2. compara lo hecho con el "hecho cuando";
  3. marca las casillas del plan y resume lo hecho, los supuestos nuevos y lo pendiente;
  4. propón el commit.
- Si algo es ambiguo, pregunta. Si el usuario no está, toma la opción más simple y anótala en el "Registro de decisiones" del plan.
- Si cambias un supuesto, actualiza la tabla §10 de la especificación.

## Comandos (Nobara 44 / Fedora, Python 3.12 en `.venv`)
- Entorno: `python3.12 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`
- Tests: `pytest -q`. Un archivo: `pytest -q tests/test_busqueda.py`
- App: `pesca-gaitan`, o `streamlit run src/pesca/app/Inicio.py`
- Precalcular resultados pesados: `python scripts/correr_todo.py` (o `--solo r2`)
- Subir cambios: `git add -A && git commit -m "fase N: ..." && git push`
- Nunca uses `sudo pip` ni cambies el `python3` del sistema.

## Reglas de modelado
- La cadena de hoy es: zona de pesca → río (neveras de icopor deterioradas) → desembarque de la señora (congeladores horizontales domésticos, desborde a icopor, cortes de luz) → espera de **7 a 15 días** hasta que llega el comprador → carretera en carro → plaza de Puerto Gaitán. El diagnóstico reporta la pérdida por etapa y verifica la hipótesis de que la espera pesa más que el río.
- Estados de conservación: ambiente, icopor con hielo (mientras dura el hielo), congelado (RRS = 0, con penalización de precio por congelación lenta) y falla del congelador. `RRS(T) = 0` para T < −10 °C.
- La ubicación del desembarque de la señora es desconocida: se usan ubicaciones candidatas y se reporta la sensibilidad.
- Los acopios formales son Puerto Gaitán (la plaza, que funciona), San Miguel y Puente Arimena (los dos con cuarto frío sin uso). El pueblo Yucao es una comunidad pescadora, no un acopio.
- Prioridad de los datos para distancias: KML medido > `distancias_medidas.csv` > calibrado > simulado. El grafo reproduce M01–M04 (±1 %).
- Para volúmenes y precios: oficial (`sepec_desembarcos_2022.csv`, `precios_referencia.csv`) > dato del equipo > simulado calibrado. Los volúmenes simulados reproducen el SEPEC × `factor_subregistro`. Cada arista y cada parámetro guarda su `fuente`.
- Todo número simulado vive en `src/pesca/datos/parametros.yaml`. Semilla fija. No pongas números mágicos en el código.
- El grafo es dirigido y multimodal: río (`v ± corriente`), carretera y transbordo. San Miguel queda río abajo de Puerto Gaitán: de San Miguel a Puerto Gaitán por río es todo contra corriente.
- Hay dos cuencas sin conexión por agua: Meta (Meta, Manacacías, Yucao) y Vichada (Planas, Muco, Guarrojo). Solo se cruza por carretera.
- El peso principal es la pérdida de calidad (RRS, especificación §6). Unidades: km, h, kg, COP. Coordenadas en WGS84.
- Las conclusiones con datos simulados se reportan con Monte Carlo (media e intervalo del 90 %).

## Convenciones de código
- Python 3.12, con layout `src/` y paquete `pesca`, instalable con `pyproject.toml` (comando `pesca-gaitan`). Los datos van dentro del paquete (`src/pesca/datos/`).
- **Dijkstra, A\* y BFS son implementaciones propias** en `busqueda.py`, porque son material del curso. Se validan contra `networkx` en los tests. Para el problema de transporte se usa NetworkX o PuLP; para la p-mediana, PuLP/CBC.
- Las páginas de `src/pesca/app/` no tienen lógica. El objeto `Escenario` (`escenario.py`) vive en `st.session_state` y lo controla la barra lateral.
- Lo pesado (Monte Carlo, p-mediana) lo precalcula `scripts/correr_todo.py` en `src/pesca/datos/precalculado/`, que se versiona en git. Lo liviano se calcula en vivo con `st.cache_data`.
- Mapas con Folium y `streamlit_folium.st_folium`. Figuras con Matplotlib o los gráficos de Streamlit. Todo valor simulado en pantalla lleva su etiqueta.

## Trampas conocidas
- `networkx.min_cost_flow` solo acepta enteros: escala antes.
- El precio por calidad es escalonado: primero se calculan las rutas por par y después se resuelve el transporte.
- La heurística de A\* debe ser admisible: distancia en línea recta / velocidad efectiva máxima × la menor tasa de deterioro posible. Si sobreestima, A\* deja de ser óptimo y el test contra Dijkstra lo detecta.
- `st_folium` vuelve a ejecutar la página en cada clic. Limita `returned_objects` a lo necesario.
- Streamlit Community Cloud instala desde `requirements.txt` y usa unos 1 GB de RAM. Verifica que `import pesca` funcione allá y que nada pesado se calcule al cargar.
- Las coordenadas con `validado = no` son aproximadas. No las presentes como exactas.
- No subas a git `.venv/`, secretos ni datos personales (pescadores, la señora del desembarque).
