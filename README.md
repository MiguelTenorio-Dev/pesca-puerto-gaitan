# Pesca en Puerto Gaitán: transporte y cadena de frío

Proyecto universitario de ingeniería. En Puerto Gaitán (Meta) el pescado pierde valor entre la captura y la venta:
el viaje por río es largo y a veces contra la corriente, no hay cadena de frío y en el desembarque el pescado
**espera de 7 a 15 días** a que llegue el comprador. El proyecto diagnostica cuánto se pierde y dónde, y propone
rutas, acopios, rutas bimodales río + carretera e inversión en frío, con grafos y optimización.

**App:** _(link de Streamlit Community Cloud, pendiente de despliegue)_

## Lo que encuentra

Todas las cifras, con su intervalo del 90 % y su etiqueta, están en [`outputs/resumen_resultados.md`](outputs/resumen_resultados.md).

- **La espera pesa más que el río**: en el 100 % de las corridas de Monte Carlo y con las 4 ubicaciones posibles del desembarque informal.
- **Reacomodo de acopios con algoritmos de búsqueda** (BFS para los candidatos, Dijkstra para los costos, p-mediana por enumeración, ILP y búsqueda local, búsqueda exhaustiva, A\* y DFS para verificar): **San Miguel y Puerto Gaitán**. San Miguel es el acopio clave: atiende las zonas del Meta, que en aguas altas no pueden remontar a Puerto Gaitán a remo.
- **Propuesta del equipo:** San Miguel rehabilitado, La Cristalina como **punto frío** (donde se recoge hielo) y un acopio nuevo junto al **Manacacías** (pueblo por confirmar). En aguas bajas el valor perdido baja de ≈ 46 % a ≈ 10 %.
  - El modelo no encuentra pérdida evitada por el acopio del Manacacías ni por los puntos fríos: casi toda la mejora la pone San Miguel, que solo tiene VPN positivo en el 66 % de las corridas; la propuesta completa, en el 33 %.

## Pantallas

**Grafo y acopios (modelo de grafos):**

1. **Del dato a la decisión.** Los cinco pasos, del archivo con coordenadas a la elección de acopios, con un ejemplo numérico del escenario.
2. **Datos del grafo.** Centros poblados del DANE, nodos y arcos, cada uno con la fuente de su dato.
3. **Cómo se construye el grafo.** Grafo dirigido río + carretera desde archivos, calibrado con las rutas medidas, y su validación (BFS, DFS).
4. **Cómo se calculan los pesos.** Pérdida de calidad de cada arco paso a paso: corriente, tiempo y hielo que se acaba.
5. **Laboratorio de algoritmos.** Dijkstra, A\* y BFS propios sobre el grafo por capas de conservación (hielo y frío).
6. **Centros de acopio.** El reacomodo paso a paso: BFS, Dijkstra, p-mediana, búsqueda exhaustiva del acopio del Manacacías y de los puntos fríos, A\* y DFS; hoy frente a la propuesta.
7. **Hoy vs propuesta.** Todas las instalaciones de hoy y de la propuesta en el mapa, pescador por pescador, y la cartilla de rutas (PDF y CSV).

**Cadena de hoy y propuesta:**

8. **Diagnóstico: la situación hoy.** Pérdida por etapa, pescador por pescador, con Monte Carlo.
9. **Mapa de la red, Bimodal y cadena de frío.** Red y medidas I1–I8 con frontera de Pareto.
10. **Supuestos y datos.** Todos los parámetros, con su etiqueta y su fuente.

El grafo usa las rutas que el equipo trazó en Google Earth (el Meta desde Puerto Gaitán hasta El Porvenir y las vías a
San Pedro de Arimena, El Porvenir, La Cristalina y Domo Planas) y trazas aproximadas para el Meta alto, el Yucao y los caños.

## Instalar y abrir (Python 3.12)

Desde GitHub:

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install git+https://github.com/MiguelTenorio-Dev/pesca-puerto-gaitan
pesca-gaitan
```

Para desarrollar:

```bash
git clone https://github.com/MiguelTenorio-Dev/pesca-puerto-gaitan && cd pesca-puerto-gaitan
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q                          # pruebas
pesca-gaitan                       # app (o: streamlit run src/pesca/app/Inicio.py)
python scripts/correr_todo.py      # recalcula Monte Carlo, p-mediana y portafolios (~20 min) y el resumen
python scripts/correr_todo.py --solo resumen   # solo regenera outputs/resumen_resultados.md
```

Los resultados pesados ya vienen precalculados en `src/pesca/datos/precalculado/`, así que la app abre sin recalcular.

## Datos

| etiqueta | qué es | ejemplos |
|---|---|---|
| **MEDIDO** | medido por el equipo en Google Earth (rutas y puntos KML) | M01–M04, San Miguel, malecón |
| **OFICIAL** | fuentes públicas | desembarcos SEPEC/AUNAP 2022; precios SIPSA/DANE |
| **DATO** | contado por el equipo | espera de 7–15 días, cuarto frío de San Miguel |
| **SIMULADO** | supuestos del proyecto, en `src/pesca/datos/parametros.yaml` | velocidades, costos, número de pescadores |

Prioridad para las distancias: KML medido > `distancias_medidas.csv` > calibrado > simulado. Las coordenadas con `validado = no` son aproximadas.

No hay datos personales de pescadores ni de nadie más.

## Limitaciones

- Casi todo lo que no es distancia ni volumen oficial es **simulado**. Las conclusiones se dan con Monte Carlo (media e intervalo del 90 %), no como valores exactos.
- La ubicación real del desembarque informal no se conoce: se usan 4 candidatas y se reporta la sensibilidad.
- El modelo de deterioro (RRS, Ratkowsky) se calibró sobre todo con pescado de aguas templadas.
- La boca del Manacacías y varias trazas de ríos son aproximadas.
- Los criaderos para la veda quedan como trabajo futuro.

## Estructura

```
src/pesca/            motor: red, busqueda (Dijkstra/A*/BFS propios), transporte, degradacion,
                      cadena_actual (R2), asignacion (R3), ubicacion (R4), frio_bimodal (R5), comparacion (R6)
src/pesca/app/        app Streamlit (las páginas no tienen lógica)
src/pesca/datos/      parametros.yaml, nodos, trazas, datos oficiales, KML y precalculado/
scripts/correr_todo.py  precálculo y resumen
outputs/              resumen_resultados.md (fuente de las cifras del informe)
docs/                 contexto del problema y evidencias de las mediciones
tests/                pruebas (pytest)
```

## Documentos

- [Contexto del problema](docs/contexto_original.md): la problemática de la pesca en Puerto Gaitán y lo que el proyecto se propuso resolver.
- [Evidencias de las mediciones](docs/evidencias/): capturas de Google Earth de las rutas M01–M04.
- Supuestos y parámetros, con su rango y su etiqueta: [`src/pesca/datos/parametros.yaml`](src/pesca/datos/parametros.yaml) y la pantalla «Supuestos y datos» de la app.

Licencia MIT.
