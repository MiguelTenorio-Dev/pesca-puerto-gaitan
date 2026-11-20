"""Mapas Folium de la red y de las busquedas. Las paginas solo los dibujan."""

from __future__ import annotations

import folium
import networkx as nx

from pesca import red
from pesca.busqueda import ResultadoBusqueda

# Color de las aristas segun la fuente del dato
COLOR_ETIQUETA = {"MEDIDO": "#1a9850", "CALIBRADO": "#d4a017", "SIMULADO": "#f46d43"}
COLOR_TRANSBORDO = "#7b3294"
TEXTO_GRUPO = {
    "MEDIDO": "🟢 Medido (trazas KML del equipo y rutas M01–M04)",
    "CALIBRADO": "🟡 Calibrado (sinuosidad de lo medido)",
    "SIMULADO": "🟠 Simulado (accesos estimados)",
}

# Color de la ruta segun el sentido
COLOR_SENTIDO = {"aguas_abajo": "#1a9850", "aguas_arriba": "#d73027", None: "#555555"}

COLOR_TIPO = {
    "acopio": "#d73027",
    "desembarque": "#fc8d59",
    "comunidad": "#7b3294",
    "zona_pesca": "#2166ac",
    "confluencia": "#878787",
    "punto_via": "#4d4d4d",
    "punto_rio": "#92c5de",
}

# Rampa de la exploracion: claro (primeros) a oscuro (ultimos)
RAMPA_EXPLORACION = ("#ffffb2", "#253494")
GUION_VIA = "8 6"


def _mapa_vacio(grafo: nx.DiGraph) -> folium.Map:
    lats = [a["lat"] for _, a in grafo.nodes(data=True)]
    lons = [a["lon"] for _, a in grafo.nodes(data=True)]
    mapa = folium.Map(tiles="OpenStreetMap", control_scale=True)
    mapa.fit_bounds([[min(lats), min(lons)], [max(lats), max(lons)]])
    return mapa


def _aristas_unicas(grafo: nx.DiGraph):
    """Una arista por par de nodos (en los rios, la que va aguas abajo)."""
    vistos = set()
    for u, v, d in grafo.edges(data=True):
        par = frozenset((u, v))
        if par in vistos or d["sentido"] == "aguas_arriba":
            continue
        vistos.add(par)
        yield u, v, d


def _mezclar(c1: str, c2: str, t: float) -> str:
    a = [int(c1[i : i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i : i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


def _texto_arista(d: dict) -> str:
    if d["modo"] == "transbordo":
        return "Transbordo río ↔ carretera"
    modo = "Río" if d["modo"] == red.CAPA_RIO else "Carretera"
    return f"{modo} · {d['distancia_km']:.1f} km · {d['fuente']}"


def _lugares(grafo: nx.DiGraph):
    """Un nodo por lugar (las dos capas se dibujan una sola vez)."""
    vistos = set()
    for n, a in grafo.nodes(data=True):
        if a["lugar"] not in vistos:
            vistos.add(a["lugar"])
            yield n, a


def mapa_red(grafo: nx.DiGraph) -> folium.Map:
    """Toda la red, con las aristas coloreadas por la fuente del dato."""
    mapa = _mapa_vacio(grafo)
    grupos = {e: folium.FeatureGroup(name=t) for e, t in TEXTO_GRUPO.items()}
    transbordos = folium.FeatureGroup(name="🟣 Transbordos")
    lugares = folium.FeatureGroup(name="Lugares")
    puntos = folium.FeatureGroup(name="Puntos del río y de la vía", show=False)

    for _, _, d in _aristas_unicas(grafo):
        if d["modo"] == "transbordo":
            folium.CircleMarker(
                d["geometria"][0], radius=11, color=COLOR_TRANSBORDO, weight=2, fill=False, tooltip=_texto_arista(d)
            ).add_to(transbordos)
            continue
        folium.PolyLine(
            d["geometria"],
            color=COLOR_ETIQUETA[d["etiqueta"]],
            weight=4 if d["modo"] == red.CAPA_RIO else 3,
            dash_array=None if d["modo"] == red.CAPA_RIO else GUION_VIA,
            tooltip=_texto_arista(d),
        ).add_to(grupos[d["etiqueta"]])

    for n, a in _lugares(grafo):
        generado = a["tipo"] in ("punto_rio", "punto_via")
        folium.CircleMarker(
            [a["lat"], a["lon"]],
            radius=3 if generado else 7,
            color=COLOR_TIPO.get(a["tipo"], "black"),
            fill=True,
            fill_opacity=0.9,
            tooltip=f"{a['lugar']} · {a['nombre']} ({a['tipo']}) · validado: {a['validado']}",
        ).add_to(puntos if generado else lugares)

    for capa in [*grupos.values(), transbordos, puntos, lugares]:
        capa.add_to(mapa)
    folium.LayerControl(collapsed=False).add_to(mapa)
    return mapa


def _red_de_fondo(mapa: folium.Map, grafo: nx.DiGraph) -> None:
    for _, _, d in _aristas_unicas(grafo):
        if d["modo"] != "transbordo":
            folium.PolyLine(
                d["geometria"], color="#bdbdbd", weight=2,
                dash_array=None if d["modo"] == red.CAPA_RIO else GUION_VIA,
            ).add_to(mapa)


def _dibujar_ruta(mapa: folium.Map, grafo: nx.DiGraph, ruta: tuple[str, ...]) -> None:
    """Ruta gruesa: verde a favor de la corriente, roja en contra, gris punteada por carretera, transbordo morado."""
    for u, v in zip(ruta, ruta[1:]):
        if not grafo.has_edge(u, v):  # acceso estimado de un acopio nuevo hasta la via
            puntos = [[grafo.nodes[n]["lat"], grafo.nodes[n]["lon"]] for n in (u, v)]
            folium.PolyLine(puntos, color=COLOR_SENTIDO[None], weight=5, dash_array=GUION_VIA, tooltip="Acceso estimado").add_to(mapa)
            folium.CircleMarker(puntos[0], radius=10, color=COLOR_TRANSBORDO, weight=3, tooltip="Transbordo").add_to(mapa)
            continue
        d = grafo.edges[u, v]
        if d["modo"] == "transbordo":
            folium.CircleMarker(d["geometria"][0], radius=10, color=COLOR_TRANSBORDO, weight=3, tooltip="Transbordo").add_to(mapa)
            continue
        folium.PolyLine(
            d["geometria"], color=COLOR_SENTIDO[d["sentido"]], weight=7, opacity=0.85,
            dash_array=None if d["modo"] == red.CAPA_RIO else GUION_VIA, tooltip=_texto_arista(d),
        ).add_to(mapa)


def mapa_recomendacion(grafo: nx.DiGraph, origen: str, ruta: tuple[str, ...]) -> folium.Map:
    """La red en gris, la ruta recomendada y el punto donde esta el pescador."""
    mapa = _mapa_vacio(grafo)
    _red_de_fondo(mapa, grafo)
    if ruta:
        _dibujar_ruta(mapa, grafo, ruta)
        fin = grafo.nodes[ruta[-1]]
        folium.Marker([fin["lat"], fin["lon"]], tooltip=f"Destino: {fin['nombre']}", icon=folium.Icon(color="red")).add_to(mapa)
    a = grafo.nodes[origen]
    folium.Marker([a["lat"], a["lon"]], tooltip=f"Estás aquí: {a['nombre']}", icon=folium.Icon(color="green", icon="user")).add_to(mapa)
    return mapa


def mapa_busqueda(grafo: nx.DiGraph, resultado: ResultadoBusqueda, paso: int | None = None) -> folium.Map:
    """La red en gris, los primeros `paso` nodos explorados y la ruta coloreada por sentido."""
    mapa = _mapa_vacio(grafo)
    _red_de_fondo(mapa, grafo)
    if resultado.alcanzable:
        _dibujar_ruta(mapa, grafo, resultado.ruta)

    explorados = resultado.explorados[: paso if paso is not None else len(resultado.explorados)]
    total = max(1, len(resultado.explorados) - 1)
    for k, n in enumerate(explorados):
        a = grafo.nodes[n]
        folium.CircleMarker(
            [a["lat"], a["lon"]],
            radius=6,
            color="#333333",
            weight=1,
            fill=True,
            fill_color=_mezclar(*RAMPA_EXPLORACION, k / total),
            fill_opacity=0.95,
            tooltip=f"#{k + 1}: {a['nombre']}",
        ).add_to(mapa)

    for nodo, color, texto in ((resultado.origen, "green", "Origen"), (resultado.destino, "red", "Destino")):
        a = grafo.nodes[nodo]
        folium.Marker([a["lat"], a["lon"]], tooltip=f"{texto}: {a['nombre']}", icon=folium.Icon(color=color)).add_to(mapa)
    return mapa


# ---------------------------------------------------------------- diagnostico (Fase 2)

# Paleta de referencia (skill dataviz): slot 1 azul y slot 2 naranja, validados como par
COLOR_VALOR = "#2a78d6"
COLOR_PERDIDA = "#eb6834"
COLOR_TEXTO_SECUNDARIO = "#52514e"
COLOR_SITIO = {"malecon": "#2a78d6", "san_miguel": "#eb6834", "senora": "#1baf7a", "vichada": "#eda100", "acopio": "#8f5bd6"}


ICONO_INSTALACION = {
    "acopio": ("blue", "home", "Acopio"),
    "acopio_nuevo": ("purple", "star", "Acopio nuevo"),
    "sin_uso": ("gray", "remove", "Cuarto frío sin uso"),
    "punto_frio": ("lightblue", "asterisk", "Punto frío (hielo)"),
    "desembarque": ("orange", "inbox", "Desembarque informal"),
}


def marcar_instalaciones(mapa: folium.Map, instalaciones) -> None:
    """Un marcador por instalacion (acopio, punto frio, cuarto frio sin uso, desembarque), siempre visible."""
    for f in instalaciones.itertuples():
        color, icono, texto = ICONO_INSTALACION[f.rol]
        folium.Marker([f.lat, f.lon], tooltip=f"{texto}: {f.descripcion}",
                      icon=folium.Icon(color=color, icon=icono)).add_to(mapa)


def mapa_recorridos(grafo: nx.DiGraph, flujos: dict[tuple[str, str], float], desembarques: dict[str, str],
                    instalaciones=None) -> folium.Map:
    """Recorridos de hoy: grosor proporcional a los kg; rio por sentido y carretera en gris.

    `desembarques` es {lugar: sitio} para marcar cada desembarque con el color de su sitio.
    """
    mapa = _mapa_vacio(grafo)
    for _, _, d in _aristas_unicas(grafo):
        if d["modo"] != "transbordo":
            folium.PolyLine(d["geometria"], color="#d9d9d9", weight=1.5,
                            dash_array=None if d["modo"] == red.CAPA_RIO else GUION_VIA).add_to(mapa)
    maximo = max(flujos.values(), default=1.0)
    for (u, v), kg in sorted(flujos.items(), key=lambda x: x[1]):
        if not grafo.has_edge(u, v):  # acceso estimado de un acopio nuevo
            puntos = [[grafo.nodes[n]["lat"], grafo.nodes[n]["lon"]] for n in (u, v)]
            folium.PolyLine(puntos, color=COLOR_SENTIDO[None], weight=2 + 10 * kg / maximo, opacity=0.8,
                            dash_array=GUION_VIA, tooltip=f"{kg:.0f} kg · acceso estimado").add_to(mapa)
            continue
        d = grafo.edges[u, v]
        if d["modo"] == "transbordo" or kg <= 0:
            continue
        folium.PolyLine(
            d["geometria"],
            color=COLOR_SENTIDO[d["sentido"]],
            weight=2 + 10 * kg / maximo,
            opacity=0.8,
            dash_array=None if d["modo"] == red.CAPA_RIO else GUION_VIA,
            tooltip=f"{kg:.0f} kg en el ciclo · {_texto_arista(d)}",
        ).add_to(mapa)
    for lugar, sitio in desembarques.items():
        n = red.clave(lugar, red.CAPA_RIO)
        a = grafo.nodes[n]
        folium.CircleMarker([a["lat"], a["lon"]], radius=9, color="#333333", weight=2, fill=True,
                            fill_color=COLOR_SITIO[sitio], fill_opacity=1, tooltip=f"{a['nombre']} ({sitio})").add_to(mapa)
    plaza = grafo.nodes["A01@via"]
    folium.Marker([plaza["lat"], plaza["lon"]], tooltip=plaza["nombre"], icon=folium.Icon(color="red")).add_to(mapa)
    if instalaciones is not None:
        marcar_instalaciones(mapa, instalaciones)
    return mapa


def grafico_cascada(pasos: list[dict]):
    """Cascada COP/kg. Cada paso: {etapa, valor (media), p5, p95, tipo: 'total'|'perdida'}."""
    import altair as alt
    import pandas as pd

    filas, nivel = [], 0.0
    for orden, p in enumerate(pasos):
        if p["tipo"] == "total":
            inicio, fin = 0.0, p["valor"]
            nivel = p["valor"]
            bajo, alto = p["p5"], p["p95"]
        else:
            inicio, fin = nivel, nivel - p["valor"]
            bajo, alto = nivel - p["p95"], nivel - p["p5"]
            nivel = fin
        filas.append({"orden": orden, "etapa": p["etapa"], "inicio": inicio, "fin": fin, "valor": p["valor"],
                      "p5": p["p5"], "p95": p["p95"], "bajo": bajo, "alto": alto, "tipo": p["tipo"]})
    datos = pd.DataFrame(filas)
    x = alt.X("etapa:N", sort=list(datos["etapa"]), title=None, axis=alt.Axis(labelAngle=0, labelLimit=140))
    color = alt.Color("tipo:N", scale=alt.Scale(domain=["total", "perdida"], range=[COLOR_VALOR, COLOR_PERDIDA]),
                      legend=alt.Legend(title=None, labelExpr="datum.value == 'total' ? 'valor' : 'pérdida'", orient="top"))
    tooltip = [alt.Tooltip("etapa:N"), alt.Tooltip("valor:Q", title="COP/kg (media)", format=",.0f"),
               alt.Tooltip("p5:Q", title="p5", format=",.0f"), alt.Tooltip("p95:Q", title="p95", format=",.0f")]
    barras = alt.Chart(datos).mark_bar(size=38, cornerRadius=4).encode(
        x=x, y=alt.Y("inicio:Q", title="COP por kg"), y2="fin:Q", color=color, tooltip=tooltip)
    intervalo = alt.Chart(datos).mark_rule(color=COLOR_TEXTO_SECUNDARIO, strokeWidth=2).encode(x=x, y="bajo:Q", y2="alto:Q")
    etiquetas = alt.Chart(datos).transform_calculate(arriba="max(datum.inicio, datum.fin)").mark_text(
        dy=-8, color=COLOR_TEXTO_SECUNDARIO).encode(x=x, y="arriba:Q", text=alt.Text("valor:Q", format=",.0f"))
    return (barras + intervalo + etiquetas).properties(height=340)


def grafico_inventario(inventario):
    """Un ciclo de la señora: kg congelados y kg en icopor por dia, la capacidad y los cortes de luz."""
    import altair as alt

    largo = inventario.melt(id_vars=["dia", "capacidad_kg", "corte_h"], value_vars=["kg_congelado", "kg_icopor"],
                            var_name="donde", value_name="kg")
    largo["donde"] = largo["donde"].map({"kg_congelado": "en el congelador", "kg_icopor": "desborde a icopor"})
    barras = alt.Chart(largo).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, stroke="white", strokeWidth=2).encode(
        x=alt.X("dia:O", title="día del ciclo (el comprador llega al final)", axis=alt.Axis(labelAngle=0)),
        y=alt.Y("kg:Q", stack=True, title="kg guardados"),
        color=alt.Color("donde:N", scale=alt.Scale(domain=["en el congelador", "desborde a icopor"],
                                                   range=[COLOR_VALOR, COLOR_PERDIDA]),
                        legend=alt.Legend(title=None, orient="top")),
        order=alt.Order("donde:N", sort="descending"),
        tooltip=["dia:O", "donde:N", alt.Tooltip("kg:Q", format=",.0f")],
    )
    capacidad = alt.Chart(inventario).mark_rule(color=COLOR_TEXTO_SECUNDARIO, strokeDash=[6, 4], strokeWidth=2).encode(
        y="mean(capacidad_kg):Q", tooltip=[alt.Tooltip("mean(capacidad_kg):Q", title="capacidad (kg)")])
    cortes = alt.Chart(inventario[inventario["corte_h"] > 0]).mark_text(text="⚡ corte", dy=-10, fontSize=12,
                                                                          color=COLOR_TEXTO_SECUNDARIO).encode(
        x="dia:O", y=alt.value(0), tooltip=[alt.Tooltip("corte_h:Q", title="horas sin luz", format=".1f")])
    return (barras + capacidad + cortes).properties(height=320)


def grafico_zonas(zonas):
    """% del valor perdido por zona, con el intervalo del 90 %."""
    import altair as alt

    orden = list(zonas.sort_values("pct_valor_perdido", ascending=False)["nombre"])
    y = alt.Y("nombre:N", sort=orden, title=None)
    tooltip = ["nombre:N", alt.Tooltip("pct_valor_perdido:Q", title="% perdido (media)", format=".1f"),
               alt.Tooltip("pct_valor_perdido_p5:Q", title="p5", format=".1f"),
               alt.Tooltip("pct_valor_perdido_p95:Q", title="p95", format=".1f"),
               alt.Tooltip("kg_mes:Q", title="kg al mes", format=",.0f")]
    barras = alt.Chart(zonas).mark_bar(color=COLOR_PERDIDA, cornerRadiusTopRight=4, cornerRadiusBottomRight=4, height=16).encode(
        x=alt.X("pct_valor_perdido:Q", title="% del valor perdido", scale=alt.Scale(domain=[0, 100])), y=y, tooltip=tooltip)
    intervalo = alt.Chart(zonas).mark_rule(color=COLOR_TEXTO_SECUNDARIO, strokeWidth=2).encode(
        x="pct_valor_perdido_p5:Q", x2="pct_valor_perdido_p95:Q", y=y)
    return (barras + intervalo).properties(height=28 * len(zonas))


def grafico_uso_destinos(uso):
    """kg/dia que recibe cada destino en el reparto optimo, con su capacidad (si tiene)."""
    import altair as alt

    y = alt.Y("destino_nombre:N", sort="-x", title=None, axis=alt.Axis(labelLimit=240))
    tooltip = [alt.Tooltip("destino_nombre:N", title="destino"), alt.Tooltip("kg_dia:Q", title="kg al día", format=",.0f"),
               alt.Tooltip("capacidad_kg_dia:Q", title="capacidad (kg/día)", format=",.0f"),
               alt.Tooltip("pct_uso:Q", title="% de la capacidad", format=".0f")]
    barras = alt.Chart(uso).mark_bar(color=COLOR_VALOR, cornerRadiusTopRight=4, cornerRadiusBottomRight=4, height=16).encode(
        x=alt.X("kg_dia:Q", title="kg al día"), y=y, tooltip=tooltip)
    con_capacidad = uso.dropna(subset=["capacidad_kg_dia"])
    tope = alt.Chart(con_capacidad).mark_tick(color=COLOR_TEXTO_SECUNDARIO, thickness=3, size=22).encode(
        x="capacidad_kg_dia:Q", y=y, tooltip=tooltip)
    return (barras + tope).properties(height=34 * len(uso) + 20)


# ---------------------------------------------------------------- centros de acopio (Fase 4)


def mapa_acopios(grafo: nx.DiGraph, actuales: list[str], propuestos: list[dict], asignacion: dict[str, str]) -> folium.Map:
    """Acopios de hoy (rojo) vs propuestos (azul), con lineas finas de cada zona a su acopio."""
    mapa = _mapa_vacio(grafo)
    _red_de_fondo(mapa, grafo)
    for i, j in asignacion.items():
        puntos = [[grafo.nodes[n]["lat"], grafo.nodes[n]["lon"]] for n in (i, j)]
        folium.PolyLine(puntos, color=COLOR_VALOR, weight=1.5, opacity=0.6).add_to(mapa)
        folium.CircleMarker(puntos[0], radius=3, color=COLOR_VALOR, fill=True, fill_opacity=0.8,
                            tooltip=grafo.nodes[i]["nombre"]).add_to(mapa)
    for n in actuales:
        a = grafo.nodes[n]
        folium.Marker([a["lat"], a["lon"]], tooltip=f"Hoy: {a['nombre']}", icon=folium.Icon(color="red", icon="home")).add_to(mapa)
    for p in propuestos:
        folium.Marker([p["lat"], p["lon"]], tooltip=f"Propuesto: {p['nombre']} ({p['lat']:.4f}, {p['lon']:.4f})",
                      icon=folium.Icon(color="blue", icon="star")).add_to(mapa)
    return mapa


def grafico_vpn(resumen):
    """VPN a 5 años por acopio: media e IC 90 %, con la linea del cero."""
    import altair as alt
    import pandas as pd

    datos = resumen.assign(media=resumen["vpn_media"] / 1e6, p5=resumen["vpn_p5"] / 1e6, p95=resumen["vpn_p95"] / 1e6)
    y = alt.Y("nombre:N", title=None, axis=alt.Axis(labelLimit=260))
    tooltip = [alt.Tooltip("nombre:N", title="acopio"), alt.Tooltip("media:Q", title="VPN medio (millones)", format=",.1f"),
               alt.Tooltip("p5:Q", title="p5", format=",.1f"), alt.Tooltip("p95:Q", title="p95", format=",.1f"),
               alt.Tooltip("pct_vpn_positivo:Q", title="% corridas con VPN > 0", format=".0f")]
    intervalo = alt.Chart(datos).mark_rule(color=COLOR_TEXTO_SECUNDARIO, strokeWidth=3).encode(
        x=alt.X("p5:Q", title="VPN a 5 años (millones de COP)"), x2="p95:Q", y=y, tooltip=tooltip)
    punto = alt.Chart(datos).mark_point(filled=True, size=140, color=COLOR_VALOR).encode(x="media:Q", y=y, tooltip=tooltip)
    cero = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(color=COLOR_PERDIDA, strokeDash=[6, 4], strokeWidth=2).encode(x="x:Q")
    return (intervalo + punto + cero).properties(height=60 * len(datos) + 30)


def grafico_codo(codo, costo_actuales: float, p_marcado: int):
    """Costo por dia vs numero de acopios (p-mediana), con el costo de los acopios de hoy."""
    import altair as alt
    import pandas as pd

    datos = codo.assign(millones=codo["costo_dia"] / 1e6, elegido=codo["p"] == p_marcado)
    x = alt.X("p:O", title="número de acopios", axis=alt.Axis(labelAngle=0))
    y = alt.Y("millones:Q", title="pérdida + viaje (millones COP/día)")
    linea = alt.Chart(datos).mark_line(color=COLOR_VALOR, strokeWidth=2).encode(x=x, y=y)
    puntos = alt.Chart(datos).mark_point(filled=True, size=90).encode(
        x=x, y=y, color=alt.condition("datum.elegido", alt.value(COLOR_PERDIDA), alt.value(COLOR_VALOR)),
        tooltip=[alt.Tooltip("p:O", title="acopios"), alt.Tooltip("millones:Q", title="millones COP/día", format=".2f")])
    hoy = alt.Chart(pd.DataFrame({"y": [costo_actuales / 1e6], "t": ["los 3 acopios de hoy"]})).mark_rule(
        color=COLOR_TEXTO_SECUNDARIO, strokeDash=[6, 4], strokeWidth=2).encode(y="y:Q", tooltip=alt.Tooltip("t:N", title=""))
    return (linea + puntos + hoy).properties(height=300)


def grafico_medidas(resumen):
    """Valor salvado al año de cada medida sola: media e IC 90 %, con la inversion en el tooltip."""
    import altair as alt

    datos = resumen.assign(media=resumen["beneficio_anual_media"] / 1e6, p5=resumen["beneficio_anual_p5"] / 1e6,
                           p95=resumen["beneficio_anual_p95"] / 1e6, inversion=resumen["inversion_media"] / 1e6)
    y = alt.Y("medida:N", title=None, sort="-x", axis=alt.Axis(labelLimit=300))
    tooltip = [alt.Tooltip("medida:N"), alt.Tooltip("media:Q", title="valor salvado (millones/año)", format=",.1f"),
               alt.Tooltip("p5:Q", title="p5", format=",.1f"), alt.Tooltip("p95:Q", title="p95", format=",.1f"),
               alt.Tooltip("inversion:Q", title="inversión (millones)", format=",.0f"),
               alt.Tooltip("pct_vpn_positivo:Q", title="% corridas con VPN > 0", format=".0f")]
    barras = alt.Chart(datos).mark_bar(color=COLOR_VALOR, cornerRadius=3, height=18).encode(
        x=alt.X("media:Q", title="valor que se salva al año (millones de COP)"), y=y, tooltip=tooltip)
    intervalo = alt.Chart(datos).mark_rule(color=COLOR_TEXTO_SECUNDARIO, strokeWidth=2).encode(x="p5:Q", x2="p95:Q", y=y)
    return (barras + intervalo).properties(height=34 * len(datos) + 30)


def grafico_pareto(tabla, presupuestos: list[float], recomendados: list[str]):
    """Inversion vs valor salvado al año de todos los portafolios; frontera de Pareto y presupuestos."""
    import altair as alt
    import pandas as pd

    datos = tabla.assign(inversion_m=tabla["inversion"] / 1e6, valor_m=tabla["beneficio_anual"] / 1e6,
                         vpn_m=tabla["vpn"] / 1e6,
                         grupo=tabla.apply(lambda f: "recomendado" if f["portafolio"] in recomendados
                                           else ("frontera de Pareto" if f["pareto"] else "otros"), axis=1))
    x = alt.X("inversion_m:Q", title="inversión inicial (millones de COP)")
    y = alt.Y("valor_m:Q", title="valor que se salva al año (millones de COP)")
    tooltip = [alt.Tooltip("portafolio:N"), alt.Tooltip("inversion_m:Q", title="inversión (millones)", format=",.0f"),
               alt.Tooltip("valor_m:Q", title="valor salvado (millones/año)", format=",.1f"),
               alt.Tooltip("vpn_m:Q", title="VPN (millones)", format=",.0f")]
    color = alt.Color("grupo:N", scale=alt.Scale(domain=["otros", "frontera de Pareto", "recomendado"],
                                                 range=["#c8c8c8", COLOR_VALOR, COLOR_PERDIDA]),
                      legend=alt.Legend(title=None, orient="top"))
    puntos = alt.Chart(datos).mark_point(filled=True, size=55, opacity=0.85).encode(x=x, y=y, color=color, tooltip=tooltip)
    frontera = alt.Chart(datos[datos["pareto"]].sort_values("inversion_m")).mark_line(
        color=COLOR_VALOR, strokeWidth=2, interpolate="step-after").encode(x=x, y=y)
    limites = pd.DataFrame({"x": [b / 1e6 for b in presupuestos],
                            "t": [f"presupuesto {b / 1e6:,.0f} M".replace(",", ".") for b in presupuestos]})
    reglas = alt.Chart(limites).mark_rule(color=COLOR_TEXTO_SECUNDARIO, strokeDash=[6, 4]).encode(
        x="x:Q", tooltip=alt.Tooltip("t:N", title=""))
    return (reglas + frontera + puntos).properties(height=380)


def grafico_combinado(pasos: list[dict]):
    """Valor salvado al año acumulado al ir sumando las medidas de un portafolio."""
    import altair as alt
    import pandas as pd

    filas, previo = [], 0.0
    for p in pasos:
        filas.append({"medida": f"+ {p['medida']}", "inicio": previo / 1e6, "fin": p["beneficio_anual"] / 1e6,
                      "aporte": (p["beneficio_anual"] - previo) / 1e6})
        previo = p["beneficio_anual"]
    datos = pd.DataFrame(filas)
    x = alt.X("medida:N", sort=list(datos["medida"]), title=None, axis=alt.Axis(labelAngle=0, labelLimit=160))
    barras = alt.Chart(datos).mark_bar(size=40, cornerRadius=3).encode(
        x=x, y=alt.Y("inicio:Q", title="valor salvado acumulado (millones/año)"), y2="fin:Q",
        color=alt.condition("datum.aporte >= 0", alt.value(COLOR_VALOR), alt.value(COLOR_PERDIDA)),
        tooltip=[alt.Tooltip("medida:N"), alt.Tooltip("aporte:Q", title="aporta (millones/año)", format=",.1f"),
                 alt.Tooltip("fin:Q", title="acumulado (millones/año)", format=",.1f")])
    return barras.properties(height=280)


# ---------------------------------------------------------------- grafo v4 (adenda §2, fase G2)

# Color de cada etiqueta de fuente (las 6 de config.ETIQUETAS)
COLOR_FUENTE = {
    "MEDIDO": "#1a9850",
    "DATO": "#4575b4",
    "OFICIAL": "#4575b4",
    "CALIBRADO": "#d4a017",
    "SIMULADO": "#f46d43",
    "CONFIRMAR": "#d73027",
}
COLOR_VIA = "#7f7f7f"
COLOR_NODO_V4 = {
    "zona_pesca": "#2166ac",
    "punto_rio": "#92c5de",
    "embarcadero": "#35978f",
    "centro_poblado": "#d73027",
    "punto_via": "#4d4d4d",
    "desembarque": "#fc8d59",
    "comunidad": "#7b3294",
    "mercado": "#1b7837",
}
TEXTO_NODO_V4 = {
    "zona_pesca": "Zonas de pesca",
    "punto_rio": "Puntos del río",
    "embarcadero": "Embarcaderos",
    "centro_poblado": "Centros poblados",
    "punto_via": "Puntos de la vía",
    "desembarque": "Desembarques",
    "comunidad": "Comunidades",
    "mercado": "Mercado",
}


def mapa_grafo(grafo: nx.DiGraph) -> folium.Map:
    """Grafo v4: nodos por tipo; rio con flecha de corriente y color por fuente; vias en gris."""
    from folium.plugins import PolyLineTextPath

    mapa = _mapa_vacio(grafo)
    rios = folium.FeatureGroup(name="Río (flecha = corriente; color = fuente)")
    accesos = folium.FeatureGroup(name="Accesos")
    vias = folium.FeatureGroup(name="Carreteras")
    for _, _, a in grafo.edges(data=True):
        # cada tramo una vez: el rio en su sentido aguas abajo; lo demas en el sentido del CSV
        if "~" in a["id"] or a["modo"] == "interno":
            continue
        texto = f"{a['id']} · {a['tipo']} · {a['d_km']:.2f} km · {a['fuente']}"
        if a["tipo"] == "rio":
            linea = folium.PolyLine(a["geometria"], color=COLOR_FUENTE[a["etiqueta"]], weight=5, tooltip=texto).add_to(rios)
            PolyLineTextPath(linea, "  ►  ", repeat=True, offset=6, attributes={"fill": "#08306b", "font-size": "14"}).add_to(rios)
        elif a["tipo"] == "via":
            folium.PolyLine(a["geometria"], color=COLOR_VIA, weight=3, dash_array=GUION_VIA, tooltip=texto).add_to(vias)
        else:
            folium.PolyLine(a["geometria"], color=COLOR_FUENTE[a["etiqueta"]], weight=1.5, tooltip=texto).add_to(accesos)

    grupos = {t: folium.FeatureGroup(name=texto) for t, texto in TEXTO_NODO_V4.items()}
    for n, a in grafo.nodes(data=True):
        if a.get("parte") == "sale":
            continue  # el nodo dividido se dibuja una vez
        menor = a["tipo"] in ("punto_rio", "punto_via", "embarcadero")
        folium.CircleMarker(
            [a["lat"], a["lon"]],
            radius=4 if menor else 8,
            color=COLOR_NODO_V4.get(a["tipo"], "black"),
            fill=True,
            fill_opacity=0.9,
            tooltip=f"{n.split(':')[0]} · {a['nombre']} ({a['tipo']}) · {a['fuente']} · validado: {a['validado']}",
        ).add_to(grupos[a["tipo"]])

    for capa in [rios, vias, accesos, *grupos.values()]:
        capa.add_to(mapa)
    folium.LayerControl(collapsed=True).add_to(mapa)
    return mapa


COLOR_A_FAVOR, COLOR_EN_CONTRA, COLOR_SIN_CORRIENTE = "#1a9850", "#d73027", "#4575b4"


def _fondo_grafo(mapa: folium.Map, grafo: nx.DiGraph) -> None:
    """La red v4 en gris claro, cada tramo una vez."""
    for _, _, a in grafo.edges(data=True):
        if "~" in a["id"] or a["modo"] == "interno":
            continue
        folium.PolyLine(a["geometria"], color="#bdbdbd", weight=2 if a["modo"] == "rio" else 1.5,
                        dash_array=None if a["modo"] == "rio" else GUION_VIA).add_to(mapa)


def _punto(grafo: nx.DiGraph, nodo) -> list[float]:
    a = grafo.nodes[nodo[0] if isinstance(nodo, tuple) else nodo]
    return [a["lat"], a["lon"]]


def color_tramo(modo: str, sentido: int) -> str:
    if modo == "via":
        return COLOR_VIA
    return {1: COLOR_A_FAVOR, -1: COLOR_EN_CONTRA}.get(sentido, COLOR_SIN_CORRIENTE)


def mapa_ruta_grafo(grafo: nx.DiGraph, tramos: list, origen: str | None = None) -> folium.Map:
    """Ruta sobre el grafo v4: verde a favor de la corriente, rojo en contra, gris por carretera."""
    mapa = _mapa_vacio(grafo)
    _fondo_grafo(mapa, grafo)
    for u, v, modo, sentido in tramos:
        if modo == "interno":
            continue
        folium.PolyLine([_punto(grafo, u), _punto(grafo, v)], color=color_tramo(modo, sentido), weight=6, opacity=0.9,
                        dash_array=GUION_VIA if modo == "via" else None).add_to(mapa)
    for n, a in grafo.nodes(data=True):
        if a["tipo"] in ("centro_poblado", "mercado", "comunidad") and a.get("parte") != "sale":
            folium.CircleMarker([a["lat"], a["lon"]], radius=6, color=COLOR_NODO_V4[a["tipo"]], fill=True, fill_opacity=0.9,
                                tooltip=a["nombre"]).add_to(mapa)
    if origen is not None:
        folium.Marker(_punto(grafo, origen), tooltip="Estás aquí", icon=folium.Icon(color="blue", icon="user")).add_to(mapa)
    return mapa


def mapa_busqueda_capas(grafo: nx.DiGraph, resultado, paso: int | None = None) -> folium.Map:
    """Estados explorados (de claro a oscuro, en orden) y la ruta encontrada."""
    mapa = _mapa_vacio(grafo)
    _fondo_grafo(mapa, grafo)
    explorados = resultado.explorados if paso is None else resultado.explorados[:paso]
    n = max(len(explorados) - 1, 1)
    for k, estado in enumerate(explorados):
        folium.CircleMarker(_punto(grafo, estado), radius=8, color=_mezclar(*RAMPA_EXPLORACION, k / n), fill=True,
                            fill_opacity=0.8, tooltip=f"{k + 1}. {estado[0]} ({estado[1]})").add_to(mapa)
    if paso is None and resultado.alcanzable:
        for u, v in zip(resultado.camino, resultado.camino[1:]):
            folium.PolyLine([_punto(grafo, u), _punto(grafo, v)], color="#000000", weight=4).add_to(mapa)
    return mapa


def mapa_acopios_grafo(grafo: nx.DiGraph, actuales: list[str], propuestos: list[str], asignacion: dict,
                       puntos_frios: list[str] = (), nombres: dict | None = None) -> folium.Map:
    """Acopios de hoy (rojo), propuestos (azul), puntos frios (celeste) y el area de influencia de cada acopio."""
    mapa = _mapa_vacio(grafo)
    _fondo_grafo(mapa, grafo)
    nombres = nombres or {}

    def lugar(j: str) -> list[float]:
        return _punto(grafo, f"{j}:entra" if f"{j}:entra" in grafo else j)

    for i, j in asignacion.items():
        folium.PolyLine([_punto(grafo, i), lugar(j)], color=COLOR_VALOR, weight=1.5, opacity=0.7).add_to(mapa)
        folium.CircleMarker(_punto(grafo, i), radius=4, color=COLOR_NODO_V4["zona_pesca"], fill=True,
                            tooltip=f"{grafo.nodes[i]['nombre']} → {nombres.get(j, j)}").add_to(mapa)
    for j in actuales:
        folium.Marker(lugar(j), tooltip=f"Hoy: {nombres.get(j, j)}", icon=folium.Icon(color="red", icon="home")).add_to(mapa)
    for j in propuestos:
        folium.Marker(lugar(j), tooltip=f"Propuesto: {nombres.get(j, j)}", icon=folium.Icon(color="blue", icon="star")).add_to(mapa)
    for j in puntos_frios:
        folium.Marker(lugar(j), tooltip=f"Punto frío (hielo): {nombres.get(j, j)}",
                      icon=folium.Icon(color="lightblue", icon="asterisk")).add_to(mapa)
    return mapa
