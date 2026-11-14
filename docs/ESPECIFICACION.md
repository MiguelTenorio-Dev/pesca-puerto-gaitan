# Especificación: transporte y cadena de frío del pescado en Puerto Gaitán

> **Versión 3.1, 13 nov 2026.** Este documento es la fuente de verdad del proyecto. El contexto original del curso queda intacto en `docs/contexto_original.md`.
>
> Etiquetas de los datos:
> - **[MEDIDO]**: medido por el equipo en Google Earth. Las capturas están en `docs/evidencias/`.
> - **[DATO]**: contexto original, trabajo de campo o fuente citada.
> - **[OFICIAL]**: estadística pública (SEPEC/AUNAP, SIPSA/DANE).
> - **[CALIBRADO]**: derivado de lo medido.
> - **[SIMULADO]**: supuesto del proyecto. Siempre se muestra así.
> - **[CONFIRMAR]**: falta validar.

---

## 1. El proyecto

**Problema.** El pescado pierde valor entre la captura y la venta. Los traslados son largos, muchas veces van contra la corriente y no hay cadena de frío: ni para transportarlo ni para mantenerlo. Cuando llega a la plaza, ya vale menos.

**Lo que hacemos como ingenieros:**
1. **Diagnóstico.** Con datos casi reales (distancias medidas en Google Earth, desembarcos oficiales del SEPEC, precios del SIPSA y una población simulada de pescadores calibrada con ellos) mostramos, pescador por pescador, cuántos kilómetros recorre hoy, cuánto se demora, cuánto va contra la corriente, con qué calidad llega su pescado a la venta y en qué etapa se pierde el valor.
2. **Solución.** Con algoritmos de grafos y optimización evaluamos:
   - a qué acopio debe ir cada pescador y por qué ruta;
   - si los tres acopios actuales están bien ubicados o conviene moverlos o agregar otros;
   - si las rutas bimodales (río + carretera) y la cadena de frío mejoran el resultado;
   - qué inversiones valen la pena.
3. **Resultado.** Una comparación "Hoy vs propuesta" para cada pescador y en total.
4. **Aplicación web.** Muestra el diagnóstico y la solución, e incluye un recomendador tipo "Uber" para pescadores: "Estás aquí; lleva tu pescado allá, por esta ruta". Además genera una **cartilla de rutas imprimible** para las zonas sin señal.

**Métrica central:**

```
valor que recibe el pescador = kg vendidos × precio_base × factor_precio(calidad al momento de la venta)
```

Todas las comparaciones se hacen con esta métrica, con los kg perdidos y con las horas de recorrido.

---

## 2. Entregables: todo funcional el domingo 15 de noviembre; presentación el lunes 16 en la mañana

1. **App web pública** (Streamlit Community Cloud) con link.
2. **Repositorio público en GitHub** con licencia MIT. Se instala con `pip install git+https://github.com/<usuario>/pesca-puerto-gaitan` y se abre con el comando `pesca-gaitan`.
3. **`outputs/resumen_resultados.md`**, generado por código. El informe solo usa cifras de aquí.
4. **Informe y presentación** con esta estructura: problema → diagnóstico → solución → hoy vs propuesta → demostración de la app → limitaciones.

---

## 3. La cadena de hoy

### 3.1 Cómo funciona [DATO, contado por el equipo]

```
zona de pesca ──río──▶ punto de desembarque ──espera──▶ comprador ──carretera──▶ plaza de Puerto Gaitán
            (icopor          (la señora: congelador     (carro; llega a           (venta directa)
             deteriorado)     horizontal o icopor)       los 7–15 días)
```

- Cada pescador tiene su zona de desembarque habitual.
- Una señora montó un **puerto de desembarque informal a la orilla del río**. Los pescadores le llevan el pescado; ella lo arregla y lo guarda en **congeladores horizontales** y, cuando no cabe, en **neveras de icopor**. Luego llama al comprador.
- **El comprador tarda entre 7 y 15 días en llegar** desde que ella llama [DATO, estimado por el equipo]. Se asume que transporta en carro [CONFIRMAR].
- Los pescadores usan **neveras de icopor** que entregan la gobernación o la alcaldía, pero **se deterioran muy rápido** [DATO].
- **Ahí empieza la descomposición:** con días de espera, un corte de luz, un congelador lleno o una nevera de icopor dañada arruinan el lote.
- La venta directa ocurre en la **plaza de mercado de Puerto Gaitán**.

**La cadena de hoy ya es bimodal** (río y luego carretera), pero la espera se mide en días, no en horas, y el frío depende de equipos domésticos.

### 3.2 Dónde se pierde el valor

Esto es lo que el diagnóstico tiene que medir:
1. **La faena**, con el pescado sin hielo o en icopor deteriorado (horas).
2. **El viaje por río:** distancia, tipo de embarcación y corriente (horas).
3. **La espera en el desembarque hasta que llega el comprador (días).**
   - Si el congelador funciona, el pescado se congela y casi no se daña, aunque pierde algo de precio por la congelación lenta.
   - Si hay un corte de luz, el congelador está lleno o el lote quedó en icopor, el daño es grande.
4. **El transporte del comprador** por carretera.

**Hipótesis que el diagnóstico debe comprobar o descartar:** la mayor pérdida no ocurre en el río (horas), sino en la espera (días).

### 3.3 Acopios formales [DATO]

| id | acopio | estado hoy |
|---|---|---|
| A01 | **Puerto Gaitán**: plaza de mercado | Funciona. Unos 8 negocios con refrigeración. Es donde se vende |
| A02 | **San Miguel** | Cuarto frío de 4 m³ que construyó la alcaldía sin calcular el costo de la luz; se dejó de usar porque no se podía pagar la energía [DATO]. Hoy el pescado espera en icopor. R4 evalúa recuperarlo (con el costo de energía explícito) o moverlo |
| A03 | **Puente Arimena** | Cuarto frío pequeño sin uso. Tamaño [CONFIRMAR] |

### 3.4 Puntos de desembarque

| id | punto | lo que sabemos |
|---|---|---|
| D01 | Desembarque de la señora | A la orilla del río, con congeladores horizontales y algunas neveras de icopor [DATO]. **Ubicación exacta desconocida** |
| D02… | Desembarques habituales de cada zona | Sin datos. Se simula uno por zona, en la orilla más cercana a una carretera, porque ahí llega el carro del comprador [SIMULADO] |

**Cómo se maneja la ubicación desconocida de D01:**
- Se definen 3 o 4 ubicaciones candidatas sobre la orilla: cerca de la boca del Manacacías, sobre el Meta bajo y en el pueblo Yucao.
- En la app se elige cuál usar, y el diagnóstico reporta si las conclusiones cambian según la ubicación. Si no cambian, la ubicación exacta no es crítica; si cambian, se dice cuánto.
- Cuando el equipo tenga el punto real, reemplaza a las candidatas.

El **pueblo Yucao** es una comunidad pescadora, no un acopio. Sus rutas medidas a Puerto Gaitán (M01 y M02) describen el recorrido de esa comunidad.

---

## 4. Datos

### 4.1 Prioridad

Para cada tramo se usa la mejor fuente disponible:
1. Ruta medida en KML.
2. `src/pesca/datos/distancias_medidas.csv`.
3. Calibrado a partir de lo medido.
4. Simulado.

Para volúmenes y precios el orden es:
1. Dato oficial (SEPEC, SIPSA, §4.7).
2. Dato del equipo.
3. Simulado calibrado al dato oficial.
4. Simulado.

Cada arista y cada parámetro guarda su `fuente`, y la app la muestra.

### 4.2 Distancias medidas [MEDIDO, Google Earth]

| id | origen → destino | modo | km | sentido del río (origen → destino) |
|---|---|---|---|---|
| M01 | pueblo Yucao → Puerto Gaitán | carretera | 15,14 | — |
| M02 | pueblo Yucao → Puerto Gaitán | río | 17,38 | mixto: Meta aguas abajo hasta la boca del Manacacías, luego Manacacías aguas arriba [CONFIRMAR el reparto] |
| M03 | San Miguel → Puerto Gaitán | carretera | ≈ 38,9 | — (leído del perfil de elevación [CONFIRMAR]) |
| M04 | San Miguel → Puerto Gaitán | río | 41,65 | **todo aguas arriba** |

**Lo que muestran:**
- **Por río no se recorre mucho más que por tierra** (1,15 veces en Yucao y 1,07 en San Miguel). Lo que hace lento el río es la embarcación y la corriente, no la distancia.
- **San Miguel queda río abajo de Puerto Gaitán.** Llevar pescado de San Miguel a Puerto Gaitán por río son 41,65 km contra la corriente. Con los supuestos iniciales, a remo serían unas 21 h y el pescado sin hielo llegaría sin valor. Con hielo llegaría con calidad de 0,86.
- **San Miguel también se conecta por carretera con Puerto Gaitán** (≈ 38,9 km). Es candidato natural a **transbordo**: el pescado llega por río y sigue en camión con frío.

### 4.3 Dos cuencas [CONFIRMAR en un mapa]

- **Cuenca del Meta:** Meta, Manacacías y Yucao. Puerto Gaitán queda en la confluencia.
- **Cuenca del Vichada:** su cabecera occidental está mayormente en Puerto Gaitán. El Planas, el Muco y el Guarrojo parecen drenar hacia allá.
- **Puente Arimena** está sobre el carreteable Puerto Gaitán–Puente Arimena (hacia el km 68 según la ANI).

Por eso el modelo es multimodal desde el inicio: aristas `modo ∈ {rio, via}`, más un tiempo de transbordo.

Fuentes: Wikipedia, "Puerto Gaitán"; WWF/UMCES, *Vichada River Report Card*; ANI (2017).

### 4.4 Nodos

Archivo: `src/pesca/datos/nodos.csv`. Columnas: `id, nombre, tipo, cuenca, lat, lon, validado, fuente, notas`.

**Tipos de nodo:**
- `acopio` (A01–A03);
- `desembarque` (D01…);
- `comunidad` (pueblo Yucao);
- `zona_pesca`:
  - P01 Meta alto (arriba de Puerto Gaitán);
  - P02 Meta bajo (hacia San Miguel);
  - P03 Manacacías;
  - P04 Yucao;
  - P05–P07 Guarrojo, Muco y Planas (Vichada);
  - P08–P12 caños Canalete, Cañomorroco, Maiciana, Guiva y Chayva (cuenca [CONFIRMAR]);
- `punto_rio` cada ~5 km (se generan sobre la traza del río; son los candidatos de R4);
- `confluencia`: X01 (boca del Manacacías) y K08–K12 (bocas de los caños, posición de relleno);
- `punto_via` (carretera): V01 y V02, donde el Planas y el Guarrojo cruzan la vía a Puente Arimena [CONFIRMAR].

Las trazas de ríos y vías están en `src/pesca/datos/rios.csv` y `vias.csv` (aproximadas, `validado = no`, hasta que llegue el KML).

### 4.5 Aristas

- **Río**, en ambos sentidos. Atributos: `distancia_km`, `sentido`, `corriente_kmh`, `fuente`.
  - Los tramos que caen en una ruta medida se **calibran**: el grafo debe reproducir M02 y M04 (±1 %).
  - Los demás usan `haversine × sinuosidad`, con la sinuosidad calibrada a partir de M02 y M04.
- **Carretera.** Atributos: `distancia_km` (medida si existe: M01, M03), `fuente`.
- **Transbordo** (río ↔ carretera) en los acopios y desembarques. Atributo: `tiempo_transbordo_h`.
- **Acceso** por carretera de los desembarques que no están sobre una vía: línea recta × sinuosidad vial hasta el punto vial más cercano [SIMULADO].
- Cada lugar tiene un nodo por capa (`<id>@rio`, `<id>@via`). Puerto Gaitán por río es el malecón (`D_MALECON`), que tiene acceso vial a la plaza (A01).

### 4.6 Datos que conviene recoger (en orden de impacto)

1. **Dónde queda el desembarque de la señora.** Mientras no se sepa, se usan las candidatas de §3.4.
2. **Detalles de la espera** (lo que ya se sabe está en §3.1):
   - cuántos congeladores tiene la señora y de qué tamaño;
   - cada cuánto se va la luz;
   - cuántos kilos recibe por semana;
   - si el comprador trae hielo o neveras.
3. **Coordenadas o KML** de los puntos. El equipo los irá entregando durante el proyecto.
4. **Puerto Gaitán → Puente Arimena** por carretera.
5. **Tiempos reales de viaje** que reporten los pescadores. Con eso se calibran las velocidades.
6. **Precio en la plaza de Puerto Gaitán** según la calidad. Mientras tanto se usa el precio mayorista oficial de Villavicencio (§4.7).

### 4.7 Datos oficiales [OFICIAL]

**Desembarcos registrados por el SEPEC (AUNAP) en Puerto Gaitán, enero–octubre de 2022, en toneladas** (archivo `src/pesca/datos/sepec_desembarcos_2022.csv`):

| sitio | ene | feb | mar | abr | may | jun | jul | ago | sep | oct | total |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Malecón (Puerto Gaitán) | 5,4 | 2,2 | 2,9 | 4,1 | 0,1 | 1,0 | 1,9 | 2,7 | 2,4 | 1,5 | 24,2 |
| San Miguel (Puerto Gaitán) | — | — | — | — | — | — | — | — | — | — | 5,5 |

Para San Miguel, la fuente muestra solo 9 valores mensuales legibles (0,5 · 1,4 · 1,0 · 0,2 · 0,5 · 0,4 · 0,5 · 0,5 · 0,4) y no se pueden asignar a cada mes con certeza.

**Lo que se concluye de esta tabla:**
- **San Miguel es un sitio de desembarque monitoreado oficialmente.** Eso respalda el análisis de su cuarto frío.
- **Los volúmenes son modestos:** en promedio, unos 80 kg/día en el Malecón y unos 18 kg/día en San Miguel. Las capacidades de frío se dimensionan contra eso.
- La caída de mayo a julio coincide con la veda.
- **Es un registro mínimo:** los desembarques informales, como el de la señora, no aparecen. El modelo aplica un `factor_subregistro` [SIMULADO].

**Especies con más desembarcos en la Orinoquía (2022, toneladas):**
- *Pseudoplatystoma orinocoense*: 937,5
- *Prochilodus mariae*: 654,9
- *Pseudoplatystoma metaense*: 595,0
- *Brachyplatystoma vaillantii*: 556,0
- *Zungaro zungaro*: 339,0
- Total de la cuenca: 5 561 t.

**Precios mayoristas (SIPSA/DANE, Central de Abastos de Villavicencio, julio de 2026)** (archivo `src/pesca/datos/precios_referencia.csv`):
- cachama fresca: $11 833/kg;
- bagre rayado entero fresco: $14 000/kg.

En la plaza de Puerto Gaitán el pescador probablemente recibe menos, porque faltan el margen del intermediario y el transporte. Esa diferencia queda como parámetro.

**Fuentes:**
- AUNAP–Universidad del Magdalena, *Estadísticas de desembarco y esfuerzo de las pesquerías artesanales de Colombia* (datos de 2022, publicado en 2025), Tabla 12 y Anexo 12.
- SIPSA/DANE, publicado en agronegocios.co.
- Congelación: ESALQ/USP, *Visão Agrícola* n.º 11.

---

## 5. Modelo de transporte

**Embarcaciones** (9 m de eslora [DATO]). Velocidad en agua quieta [SIMULADO, calibrar con §4.6.5]:

| tipo | km/h |
|---|---|
| `madera_remo` | 4 (3–5) |
| `madera_motor` | 15 (12–18) |
| `aluminio_remo` | 5 (4–6) |
| `aluminio_motor` | 28 (22–35) |

- Aguas abajo: `v + corriente`. Aguas arriba: `v − corriente`.
- Si la velocidad efectiva es ≤ `v_minima`, el tramo es **infactible** para ese tipo, y se explica por qué.

**Vehículos de carretera** [SIMULADO]:

| tipo | km/h | temperatura del pescado |
|---|---|---|
| `comprador_carro` (situación actual; se asume carro [CONFIRMAR]) | 30 (20–40) | ambiente, o icopor con hielo si lo trae |
| `camion_refrigerado` (propuesta) | 35 (25–45) | 4 °C |

**Flota por zona:** cada zona tiene una mezcla de embarcaciones [SIMULADO]. Las inversiones pueden cambiarla.

---

## 6. Modelo de degradación

```
RRS(T) = (1 + 0,1·T)²  si T ≥ −10 °C;  0 si T < −10 °C   # tasa relativa de deterioro (Ratkowsky / Spencer–Baines); RRS(0 °C) = 1
Q = 1 − Σ_etapas (Δt · RRS(T)) / VU0        # calidad entre 0 y 1; VU0 = 360 h (15 días en hielo, cachama [DATO])
```

- **Etapas:** faena → río → desembarque (almacenado hasta que llega el comprador) → carretera → venta.
- **Estados de conservación:**

| estado | temperatura | cómo entra al modelo |
|---|---|---|
| `ambiente` | 32 °C (28–38) | RRS normal |
| `icopor_con_hielo` | 4 °C mientras dura el hielo | El hielo dura `horas_hielo` según el estado de la nevera (nueva ~48 h, deteriorada ~12 h) [SIMULADO]. Después el lote pasa a `ambiente` |
| `congelado` | ≤ −18 °C | El deterioro bacteriano se detiene (RRS = 0). A −18 °C la calidad se mantiene de 6 a 12 meses según la especie [DATO, ESALQ/USP]. Pero la congelación lenta de un congelador doméstico daña la textura, así que se aplica una sola vez un `factor_precio_congelado` [SIMULADO] |
| falla del congelador | sube hacia la ambiente | Con probabilidad diaria `p_corte_dia`, el congelador pasa `horas_corte` sin luz. Si el corte supera `horas_descongelacion`, el lote se descongela y acumula deterioro a temperatura ambiente [SIMULADO] |

- **Capacidad del congelador:** lo que no cabe (`n_congeladores × kg_por_congelador`) va a neveras de icopor. Con días de espera, esa es la parte que más se daña.
- La pérdida es aditiva por etapa: sirve como peso del grafo, y el diagnóstico la reporta por etapa.
- **El diagnóstico reporta la pérdida por etapa:** en qué parte de la cadena se va el valor.
- **Limitación para el informe:** el modelo se calibró sobre todo con pescado de aguas templadas. Se usa como aproximación y se cita.

**Precio según calidad** [SIMULADO; reemplazar con §4.6.6]:

| calidad | factor de precio |
|---|---|
| Q ≥ 0,75 | 1,00 |
| 0,50–0,75 | 0,70 |
| 0,25–0,50 | 0,40 |
| < 0,25 | 0 (rechazo) |

---

## 7. Algoritmos (lo que el curso espera ver)

| algoritmo | para qué se usa aquí | cómo se implementa | qué se muestra |
|---|---|---|---|
| **Dijkstra** | Ruta de mínima pérdida de calidad (o mínimo tiempo) entre un pescador y un acopio | **Implementación propia** (didáctica), validada contra `networkx` | Ruta, costo y nodos explorados |
| **A\*** | La misma búsqueda, guiada hacia el destino | Propia. Heurística **admisible**: distancia en línea recta / velocidad efectiva máxima × la menor tasa de deterioro posible | Mismo resultado que Dijkstra con menos nodos explorados |
| **BFS** | Ruta con menos tramos | Propia | **Por qué no sirve aquí:** ignora km, corriente y degradación, y su ruta "corta" puede ser peor |
| **Problema de transporte** (flujo de costo mínimo) | Repartir a todos los pescadores entre los acopios, respetando capacidades | `networkx.min_cost_flow` (con enteros) o PuLP | Flujos, uso de cada acopio, comparación con hoy |
| **p-mediana** | Dónde ubicar k acopios para minimizar la pérdida total ponderada por kg | PuLP/CBC | Ubicaciones, curva del codo, comparación con los acopios actuales |
| **Monte Carlo** | Incertidumbre de los datos simulados | Propio, con semilla fija | Medias e intervalos del 90 % |

Comparación obligatoria: **Dijkstra vs A\* vs BFS** en 5–10 pares origen-destino, con costo de la ruta, nodos explorados y tiempo de cómputo, en una tabla y en el mapa.

---

## 8. Requerimientos

### R1. Red multimodal y algoritmos de búsqueda
- **Motor:**
  - grafo río + carretera + transbordos, calibrado con M01–M04;
  - Dijkstra, A\* y BFS propios;
  - matriz origen × acopio × embarcación (km, h, % contra corriente, calidad, factible).
- **Pantallas:** "Mapa de la red" (aristas coloreadas por fuente del dato) y "Laboratorio de algoritmos" (eliges origen, destino y algoritmo; se ven la ruta y los nodos explorados).
- **Hecho cuando:**
  - el grafo reproduce los km de M01–M04 (±1 %);
  - aguas abajo es más rápido que aguas arriba;
  - el motor es más rápido que el remo;
  - no hay aristas de río entre las cuencas;
  - Dijkstra propio = `networkx` en todos los pares de prueba;
  - A\* da el mismo costo que Dijkstra y explora igual o menos nodos;
  - existe la tabla comparativa con BFS.

### R2. Diagnóstico: la situación de hoy
- **Motor:**
  - **volúmenes calibrados con el SEPEC** (§4.7): el total mensual simulado para el Malecón y San Miguel reproduce el registro de 2022, multiplicado por el `factor_subregistro`;
  - **población sintética de pescadores** (ubicación sobre el río real, embarcación, kg por faena, días de pesca, desembarque habitual y estado de su nevera de icopor), cuyo total suma esos volúmenes;
  - **simulación día a día del desembarque de la señora** durante un ciclo de recogida: entra pescado cada día, se llena el congelador, lo que no cabe va a icopor, hay cortes de luz y el comprador llega a los 7–15 días;
  - la cadena de §3.1 simulada pescador por pescador, con Monte Carlo sobre la espera, los cortes, los volúmenes y las velocidades;
  - **sensibilidad a la ubicación del desembarque** (§3.4).
- **Salidas por pescador y por zona:** km por río y por carretera, horas totales, % contra corriente, calidad al vender, precio recibido, COP perdidos y **pérdida por etapa**.
- **Pantalla "Diagnóstico: la situación hoy":**
  - mapa con los recorridos actuales;
  - indicadores clave (por ejemplo, "en promedio el pescado llega con calidad X y pierde Y % de su valor");
  - un gráfico de **pérdida por etapa** (en cascada o barras apiladas);
  - el **inventario del congelador día a día** durante un ciclo de recogida: capacidad, desborde a icopor y cortes de luz;
  - distribución por zona.
- **Hecho cuando:** cada cifra viene con su intervalo, la pérdida por etapa suma la pérdida total y la pantalla deja claro qué es medido y qué es simulado.

### R3. Recomendador ("Uber pesquero") y asignación óptima
- **Motor:**
  - `recomendar(origen, embarcacion, kg, escenario)`: compara **todas las formas de vender**:
    - ir directo a la plaza;
    - dejar el pescado en un desembarque y esperar al comprador;
    - llevarlo a un acopio activo, incluidas las rutas bimodales.
    
    El criterio es la **calidad al momento de la venta**, contando todo el tiempo hasta vender, esperas incluidas. Devuelve la ruta por tramos con su modo y sentido, el tiempo, la calidad, el precio, las alternativas y una explicación en lenguaje sencillo;
  - **problema de transporte** para toda la flota, con capacidades y un nodo `sin_destino`.
- **Pantallas:**
  - "¿A dónde llevo mi pescado?": clic en el mapa o lista; tarjeta de recomendación; ruta coloreada (verde a favor de la corriente, rojo en contra, gris por carretera); tabla de alternativas; se ve bien en celular;
  - "Toda la flota".
- **Hecho cuando:**
  - se conserva el flujo y no se excede ninguna capacidad;
  - hay un caso 2 × 2 resuelto a mano;
  - **prueba de sentido:** con San Miguel activo, un pescador del Meta bajo a remo y sin hielo nunca recibe "por río a Puerto Gaitán";
  - la explicación menciona la corriente y, si aplica, el transbordo.

### R4. Acopios: viabilidad de los actuales y reubicación
- **Motor:**
  - **Viabilidad:** escenarios con Puerto Gaitán solo, + San Miguel rehabilitado, + Puente Arimena rehabilitado y con los tres. Para cada uno: kg salvados, valor ganado, uso de capacidad, VPN a 5 años y Monte Carlo de 500 corridas. Regla: vale la pena si VPN > 0 en ≥ 70 % de las corridas [SIMULADO, ajustable].
  - **Reubicación:** p-mediana sobre los `punto_rio`, en dos modos: (a) mover los acopios (k = 3 libres), y (b) mantener los actuales y agregar k = 1…3. Curva del codo.
- **Pantalla "Centros de acopio":** veredicto para cada acopio actual, un mapa comparando acopios actuales con propuestos, botones "activar en el escenario" y tabla de coordenadas descargable.
- **Hecho cuando:** la regla de decisión es explícita, las ubicaciones caen sobre el río, la pérdida no aumenta con k y los acopios propuestos se pueden usar en el recomendador.

### R5. Rutas bimodales, cadena de frío e inversión
- **Motor, escenarios:**
  - **Bimodal:** el pescador desembarca en el acopio más cercano río abajo, hace transbordo y sigue en camión refrigerado a la plaza.
  - **Hielo a bordo:** cajas térmicas que bajan la temperatura en el río a ~4 °C.
  - **Desembarque mejorado:** refrigeración confiable donde la señora, y menos espera.
  - **Portafolio de inversión de la alcaldía** [SIMULADO]:
    - I1 cajas térmicas con hielo;
    - I2 punto o fábrica de hielo;
    - I3 rehabilitar San Miguel o Puente Arimena;
    - I4 acopio nuevo de R4;
    - I5 camión refrigerado con **ruta de recolección programada**: pasa por los desembarques cada N días, y N es una variable de decisión;
    - I6 subsidio de motor;
    - I7 mejorar el desembarque informal.
  - Se enumeran los portafolios y se construye la **frontera de Pareto** (costo vs valor salvado) para 3 presupuestos.
- **Pantalla "Bimodal y cadena de frío":** comparación unimodal vs bimodal para cada zona, control de presupuesto, portafolio recomendado y gráfico de Pareto.
- **Hecho cuando:** ningún portafolio excede su presupuesto, y el efecto de cada medida se ve por separado y combinado.

### R6. Hoy vs propuesta, y cartilla sin señal
- **Motor:**
  - la propuesta final (combinación de R3, R4 y R5 elegida por el equipo) comparada con hoy, pescador por pescador y en total: km, horas, calidad, COP recibidos y kg perdidos;
  - **cartilla de rutas**: una tabla por zona y embarcación con "lleva tu pescado a X por esta ruta (≈ N h)", descargable en PDF o CSV para imprimir, porque en el río no hay buena señal.
- **Pantalla "Hoy vs propuesta":** la diapositiva de cierre, con indicadores antes y después, el mapa doble y el botón de cartilla.
- **Hecho cuando:** todas las cifras salen de `resumen_resultados.md` y la cartilla se descarga.

---

## 9. La aplicación

### 9.1 Arquitectura

```
pesca-puerto-gaitan/
├── pyproject.toml · requirements.txt · LICENSE (MIT) · README.md · CLAUDE.md
├── src/pesca/
│   ├── datos/             # parametros.yaml, nodos.csv, distancias_medidas.csv, rutas_kml/, precalculado/
│   ├── config.py · escenario.py
│   ├── red.py             # grafo multimodal y calibración
│   ├── busqueda.py        # Dijkstra, A*, BFS propios + comparación
│   ├── transporte.py · degradacion.py
│   ├── poblacion.py       # pescadores sintéticos
│   ├── cadena_actual.py   # simulación de la situación de hoy (R2)
│   ├── asignacion.py      # recomendador + problema de transporte (R3)
│   ├── ubicacion.py       # viabilidad + p-mediana (R4)
│   ├── frio_bimodal.py    # escenarios bimodales, frío e inversión (R5)
│   ├── comparacion.py     # hoy vs propuesta + cartilla (R6)
│   ├── montecarlo.py · visualizacion.py · cli.py
│   └── app/               # Inicio.py + páginas
├── scripts/correr_todo.py # precalcula lo pesado → datos/precalculado/ y outputs/
├── outputs/ · tests/ · docs/
```

**Principios:**
- **Motor separado de la interfaz.** Las páginas no tienen lógica: llaman funciones del motor y dibujan.
- **Un objeto `Escenario`** compartido. La barra lateral define: acopios activos, desembarques activos, hielo a bordo, camión refrigerado, temporada e inversiones aplicadas. Cambiarlo actualiza todas las pantallas.
- **Lo pesado se precalcula** (Monte Carlo, p-mediana) en `datos/precalculado/` y se versiona. Lo liviano se calcula en vivo con `st.cache_data`.
- **Cada cifra en pantalla** lleva su unidad y su etiqueta si es simulada.

### 9.2 Pantallas (en el orden de la presentación)

1. **Inicio:** el problema en 3 líneas y cómo navegar.
2. **Diagnóstico: la situación hoy** (R2).
3. **Mapa de la red** (R1).
4. **Laboratorio de algoritmos** (R1).
5. **¿A dónde llevo mi pescado?** ★ (R3).
6. **Toda la flota** (R3).
7. **Centros de acopio** (R4).
8. **Bimodal y cadena de frío** (R5).
9. **Hoy vs propuesta** + cartilla (R6).
10. **Supuestos y datos:** parámetros con etiquetas, distancias medidas con sus capturas, limitaciones.

**La app está hecha cuando:**
- [ ] Abre sin errores en local (`pesca-gaitan`) y en el link público.
- [ ] Cada pantalla carga en menos de 5 s.
- [ ] Toda la interfaz está en español claro.
- [ ] Un cambio del escenario se ve en el recomendador.

---

## 10. Supuestos y parámetros iniciales

Van en `src/pesca/datos/parametros.yaml`. Son **[SIMULADO]** salvo que diga otra cosa.

| parámetro | valor inicial | rango MC | nota |
|---|---|---|---|
| `semilla` | 42 | — | |
| sinuosidad sin medir | río 1,18 (M02 + M04) · vía 1,34 (M01 + M03) | ±20 % | [CALIBRADO] en la Fase 1. Los tramos exclusivos de cada ruta medida se escalan para reproducirla: M02 ×1,86, M04 ×1,07, M01 ×1,57, M03 ×1,27 |
| corriente, aguas altas / bajas (km/h) | 4 / 2 | 3–6 / 1–3 | escenario base: aguas bajas [CONFIRMAR] |
| `v_minima` (km/h) | 1 | — | |
| velocidades de embarcación y de carretera | §5 | §5 | |
| transbordo (h) | 0,5 | 0,25–1,5 | |
| VU0 (h) | 360 | 288–432 | [DATO] |
| T ambiente en canoa / carretera sin frío (°C) | 32 | 28–38 | |
| T con hielo o refrigeración (°C) | 4 | 2–8 | |
| horas de faena | 4 | 2–8 | |
| ciclo de recogida del comprador (días) | uniforme(7, 15) | — | [DATO, estimado por el equipo] |
| congeladores de la señora | 2 × 150 kg útiles | 1–3 × 100–200 kg | [CONFIRMAR] |
| candidatas del desembarque de la señora | D01a (base), D01b, D01c, D01d | — | [SIMULADO] definitivo: la ubicación real no se conocerá (D10) |
| `p_corte_dia` (probabilidad diaria de corte de luz) | 0,10 | 0,02–0,25 | [CONFIRMAR] |
| `horas_corte` / `horas_descongelacion` | uniforme(2, 12) / 6 | | |
| `factor_precio_congelado` | 0,85 | 0,75–0,95 | penaliza la congelación lenta |
| horas que dura el hielo en icopor (nevera nueva / deteriorada) | 48 / 12 | 24–72 / 4–24 | |
| pescadores con nevera de icopor en buen estado hoy | 30 % | 10–50 % | las neveras se deterioran rápido [DATO] |
| precio de referencia (COP/kg) | 11 833 (cachama) · 14 000 (bagre rayado) | ±25 % | [OFICIAL] SIPSA, Villavicencio, jul 2026 |
| `mezcla_cachama` (fracción de cachama; el resto es bagre) | 0,5 | 0,3–0,7 | da el precio base ponderado |
| `factor_precio_local` (plaza de Puerto Gaitán vs Villavicencio) | 0,8 | 0,6–1,0 | |
| volumen desembarcado | calibrado al SEPEC 2022 (§4.7) | | [OFICIAL] |
| `factor_subregistro` | 2,0 | 1,3–3,0 | desembarques informales que no registra el SEPEC |
| destino del volumen (Fase 2) | registrado: Malecón (venta directa) y San Miguel; no registrado: 85 % la señora, 15 % Vichada (cruces con la vía) | Vichada 5–30 % | decisión del usuario, 14 nov |
| kg por faena / faenas por semana | 20 / 4 | 10–40 / 3–6 | el número de pescadores se deriva del volumen |
| hielo que se pone al pescado que espera en icopor (h) | 24 | 12–48 | desborde de la señora, San Miguel y Vichada |
| ciclo del comprador en San Miguel (días) | uniforme(7, 15) | — | [SIMULADO] definitivo: no habrá datos del comprador |
| el comprador trae hielo | no | — | [SIMULADO] definitivo: no habrá datos del comprador |
| bote que no puede remontar la corriente | vende río abajo, en el centro más cercano que alcanza (Malecón, San Miguel, la señora o un cruce del Vichada) | — | [SIMULADO], indicado por el usuario. En aguas altas ≈ 31 % del pescado se desvía |
| pescadores por zona y kg por faena | se derivan para reproducir el volumen calibrado | ±30 % | |
| mezcla de flota | 60 % madera_remo, 30 % madera_motor, 10 % aluminio_motor | ±15 pp | |
| capacidad de la plaza de Puerto Gaitán (kg/día) | 1 500 | 800–2 400 | ~8 negocios [DATO]; holgada frente a ~80 kg/día registrados |
| kg útiles por m³ de cuarto frío | 400 | 300–500 | |
| capacidad de San Miguel / Puente Arimena (kg) | 1 600 / 400 | | 4 m³ [DATO] / tamaño [CONFIRMAR] |
| horas en el cuarto frío de un acopio activo antes de salir a la plaza | 24 | 12–72 | Fase 3, recomendador |
| espera esperada en un desembarque (días) | (E[ciclo] + 1) / 2 ≈ 6 | — | Fase 3: el lote llega en cualquier día del ciclo del comprador |
| rehabilitación + operación anual de San Miguel (COP) | 40 M + 24 M | 25–70 M / 15–40 M | |
| tasa de descuento | 12 % | — | VPN a 5 años |
| días de pesca al año | 270 | — | veda 1 may – 31 jul [DATO] |
| separación entre candidatos (km) | 5 | — | |
| corridas de Monte Carlo | 500 (R2, R4), 100 (R5) | — | |
| costos de I1–I7 | se definen en la Fase 5 | | |

---

## 11. Fuera de alcance

- **Criaderos para la veda.** Quedan como trabajo futuro y se mencionan en las recomendaciones del informe.
- Detectar a los "falsos pescadores".
- Datos reales de calidad del agua, batimetría o caudales.
- **Datos personales** de pescadores o de la señora del desembarque en el repositorio público.

---

## 12. Decisiones

| id | decisión | estado |
|---|---|---|
| D1 | Entrega | **resuelta:** todo funcional el domingo 15; presentación el lunes 16 en la mañana. El formato del informe no está definido |
| D2 | Modelo multimodal (río + carretera) | **resuelta:** sí, es parte del diagnóstico y de la solución |
| D3 | "Embalses u ornamentación" en la inversión de la alcaldía | **resuelta:** se interpreta como infraestructura de cadena de frío (I1–I7) |
| D4 | Coordenadas exactas de los acopios y del desembarque | **abierta** (§4.6) |
| D5 | ¿A qué cuenca pertenece cada caño menor? | abierta. Por defecto: Meta o Manacacías [CONFIRMAR] |
| D6 | ¿Individual o en equipo? | **resuelta:** individual, en `main` |
| D7 | Acopios del proyecto | **resuelta:** Puerto Gaitán, San Miguel y Puente Arimena. Yucao es una comunidad pescadora |
| D8 | Alcance | **resuelta:** transporte + cadena de frío + inversión. Criaderos, trabajo futuro |
| D9 | Algoritmos | **resuelta:** Dijkstra, A\*, BFS (comparados), problema de transporte, p-mediana |
| D10 | Ubicación del desembarque de la señora | **resuelta:** la ubicación real no se conocerá. Se usan las 4 candidatas simuladas con análisis de sensibilidad (§3.4); en aguas bajas y altas la conclusión no cambia |
