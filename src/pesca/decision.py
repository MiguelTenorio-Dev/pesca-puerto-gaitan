"""Recorrido "Del dato a la decisión" (fase G7): los cinco pasos con un ejemplo numérico del escenario activo."""

from __future__ import annotations

from pesca import acopios, config, grafo, grafo_datos, laboratorio, pesos

PAGINAS = {
    1: ("pages/11_Datos_del_grafo.py", "Datos del grafo"),
    2: ("pages/12_Como_se_construye_el_grafo.py", "Cómo se construye el grafo"),
    3: ("pages/13_Como_se_calculan_los_pesos.py", "Cómo se calculan los pesos"),
    4: ("pages/04_Laboratorio_de_algoritmos.py", "Laboratorio de algoritmos"),
    5: ("pages/07_Centros_de_acopio.py", "Centros de acopio"),
}


def _n(x: float, d: int = 3) -> str:
    return f"{x:.{d}f}".replace(".", ",")


def recorrido(escenario, bote: str = "madera_remo", nevera: str = "deteriorada") -> list[dict]:
    g = grafo.construir_grafo()
    centros = config.cargar_centros_poblados()
    nodos, aristas = config.cargar_nodos_grafo(), config.cargar_aristas()
    resumen = grafo_datos.resumen_fuentes({"centros": centros, "nodos": nodos, "aristas": aristas}).sum(axis=1)
    cal = grafo.calibrar(g).set_index("id")
    cond = pesos.condiciones(escenario, bote, nevera)
    m04 = pesos.arco_ejemplo_m04()
    peso = pesos.costo_arco(m04, "hielo", 0.0, cond)
    origen, destino = laboratorio.pares()[1]
    ruta = laboratorio.correr("dijkstra", g, origen, destino, cond)
    an = acopios.analizar(g, centros, escenario.temporada)
    nombres = centros.set_index("id")["nombre"]
    etiquetas = ", ".join(f"{int(v)} {k}" for k, v in resumen.items() if v)

    pasos = [
        (
            "Datos y fuentes",
            "Todo sale de archivos: centros poblados del DANE, nodos y arcos del grafo, y las rutas medidas M01–M04. "
            "Cada fila dice de dónde viene (MEDIDO, DATO, OFICIAL, CALIBRADO, SIMULADO o CONFIRMAR).",
            f"filas por fuente: {etiquetas}. San Miguel tiene {centros.set_index('id').at['CP03', 'habitantes_2018']} habitantes (OFICIAL) "
            "y su coordenada es el punto de desembarque medido en el KML.",
        ),
        (
            "Cómo se construye el grafo",
            "Un vértice en cada confluencia, frente a cada pueblo y cada ~5 km; cada tramo de río tiene su arco de ida "
            "y de vuelta (con la corriente al revés), y cada pueblo se parte en entra → sale.",
            f"{g.number_of_nodes()} nodos y {g.number_of_edges()} arcos. El grafo reproduce M04 = "
            f"{_n(cal.at['M04', 'km_grafo'], 2)} km (medido {_n(cal.at['M04', 'km_medido'], 2)} km).",
        ),
        (
            "Cómo se calcula el peso de una arista",
            "ΔQ = horas × RRS(temperatura) / 360. La velocidad es la del bote ± la corriente, y la temperatura depende de "
            "si todavía hay hielo, si va en frío o si está congelado.",
            (f"San Miguel → Puerto Gaitán por río a remo, {escenario.temporada.replace('_', ' ')}, icopor deteriorado: "
             f"τ = {_n(peso[1])} h, ΔQ = {_n(peso[0], 4)} → calidad {_n(max(0.0, 1 - peso[0]))}.")
            if peso else f"San Miguel → Puerto Gaitán por río a remo en {escenario.temporada.replace('_', ' ')}: infactible, la corriente no deja subir.",
        ),
        (
            "Qué algoritmo encuentra la ruta",
            "Dijkstra sobre el grafo por capas (estado = lugar y cómo viaja el pescado). Es válido porque ΔQ ≥ 0 y llegar "
            "más tarde nunca abarata lo que sigue. A* llega a lo mismo explorando menos; BFS solo cuenta tramos.",
            (f"{g.nodes[origen]['nombre']} → {g.nodes[destino]['nombre']}: calidad al llegar {_n(max(0.0, 1 - ruta.costo))}, "
             f"{_n(ruta.km, 1)} km, {ruta.nodos_expandidos} estados expandidos. " + " · ".join(laboratorio.ruta_texto(g, ruta)))
            if ruta.alcanzable else "Sin ruta factible con este bote.",
        ),
        (
            "Qué algoritmo elige los acopios",
            "La p-mediana sobre los vértices del grafo (Hakimi): basta mirar los vértices, y aquí solo los centros poblados. "
            "Se resuelve por enumeración exacta, ILP y búsqueda local, y se compara con el centroide y con los de hoy.",
            f"Candidatos: {', '.join(nombres[j] for j in an['candidatos'])}. Con p = {an['p_codo']} (el codo) se eligen "
            f"{', '.join(nombres[j] for j in an['S'])}: se pierden {_n(acopios.f(an['c'], an['w'], an['S']), 2)} kg/día, contra "
            f"{_n(an['f_p1'], 2)} con un solo acopio y {_n(an['f_centroide_p1'], 2)} con el centroide.",
        ),
    ]
    return [
        {"n": n, "titulo": titulo, "respuesta": respuesta, "ejemplo": ejemplo, "pagina": PAGINAS[n][0], "enlace": PAGINAS[n][1]}
        for n, (titulo, respuesta, ejemplo) in enumerate(pasos, 1)
    ]


# ---------------------------------------------------------------- resumen de resultados


def _celda(v) -> str:
    """Formato del resumen: coma decimal (como el resto del archivo) y sí/no."""
    if isinstance(v, bool) or type(v).__name__ == "bool_":
        return "sí" if v else "no"
    if isinstance(v, float):
        return _n(0.0 if abs(v) < 5e-4 else v, 3)
    return str(v)


def _tabla_md(df) -> list[str]:
    columnas = list(df.columns)
    filas = ["| " + " | ".join(columnas) + " |", "|" + "---|" * len(columnas)]
    filas += ["| " + " | ".join(_celda(v) for v in fila) + " |" for fila in df.itertuples(index=False)]
    return filas


def texto_resumen_grafo() -> str:
    """Seccion "Grafo y acopios" de outputs/resumen_resultados.md (adenda v4)."""
    g = grafo.construir_grafo()
    nodos, aristas = config.cargar_nodos_grafo(), config.cargar_aristas()
    cal = grafo.calibrar(g)
    an = acopios.analizar(g)
    nombres = config.cargar_centros_poblados().set_index("id")["nombre"].to_dict()

    def conj(s) -> str:
        return ", ".join(nombres.get(j, j) for j in s)

    tipos_n = nodos["tipo"].value_counts().rename_axis("tipo de nodo").reset_index(name="n")
    tipos_a = aristas["tipo"].value_counts().rename_axis("tipo de arco").reset_index(name="n")
    etiquetas = sorted(set(nodos["fuente"].map(grafo_datos.etiqueta)) | set(aristas["fuente"].map(grafo_datos.etiqueta)))
    lineas = ["## Grafo y acopios", "",
              f"Grafo construido desde `datos/grafo/` (fuentes: {', '.join(etiquetas)}): {len(nodos)} nodos y {len(aristas)} arcos en el CSV; "
              f"{g.number_of_nodes()} nodos y {g.number_of_edges()} arcos dirigidos en el grafo (con inversos y nodos divididos).", ""]
    lineas += _tabla_md(tipos_n) + [""] + _tabla_md(tipos_a) + ["", "**Calibración (Dijkstra por distancia):**", ""]
    lineas += _tabla_md(cal[["id", "modo", "km_medido", "km_grafo", "error_pct", "manda"]]) + [""]
    # Ejemplo del peso de una arista: San Miguel -> Puerto Gaitan por rio (M04), todo contra la corriente
    m04 = pesos.arco_ejemplo_m04()
    remo = pesos.Condiciones(bote="madera_remo", temporada="aguas_bajas")
    partes = []
    for nevera in ("buena", "deteriorada", "sin_hielo"):
        dq, tau, _ = pesos.costo_arco(m04, "hielo", 0.0, remo.con(nevera=nevera))
        partes.append(f"{pesos.TEXTO_NEVERA[nevera]}: ΔQ = {_n(dq, 4)} (Q = {_n(max(0.0, 1 - dq))})")
    tau = pesos.tiempo_arco(m04, remo)
    camion = pesos.costo_arco(pesos.arco_ejemplo_m03(), "frio", 0.0, remo)
    lineas += [f"**Peso de una arista** (San Miguel → Puerto Gaitán por río, {_n(m04['d_km'], 2)} km contra la corriente, madera a remo, "
               f"aguas bajas): v_e = {_n(pesos.velocidad_efectiva(m04, remo)[0], 0)} km/h, τ = {_n(tau)} h; " + "; ".join(partes)
               + f". En aguas altas el tramo es infactible a remo. El mismo trayecto en camión refrigerado por carretera "
               f"({_n(camion[1])} h): ΔQ = {_n(camion[0], 4)}.", ""]
    # Busqueda sobre el grafo por capas (remo, icopor deteriorado, San Miguel y la plaza con frio)
    cond = pesos.Condiciones(acopios=frozenset({"CP01", "CP03"}))
    comp = laboratorio.comparar(g, cond)
    tot = comp.groupby("algoritmo").agg(estados=("nodos_expandidos", "sum"), peor=("pct_peor_que_dijkstra", "max"))
    menos = 100 * (1 - tot.at["a_estrella", "estados"] / tot.at["dijkstra", "estados"])
    sin_hielo = cond.con(nevera="sin_hielo")
    bfs = laboratorio.correr("bfs", g, "P02", "MER_CP01", sin_hielo)
    dij = laboratorio.correr("dijkstra", g, "P02", "MER_CP01", sin_hielo)
    lineas += [f"**Búsqueda sobre el grafo por capas** ({len(comp) // 3} pares, madera a remo, icopor deteriorado): "
               f"Dijkstra expande {tot.at['dijkstra', 'estados']} estados y A* {tot.at['a_estrella', 'estados']} "
               f"({_n(menos, 0)} % menos) con el mismo costo; BFS expande {tot.at['bfs', 'estados']}. "
               f"Caso documentado (Meta bajo → plaza, sin hielo): BFS usa {bfs.tramos} tramos y pierde {_n(bfs.costo, 2)} de calidad; "
               f"Dijkstra usa {dij.tramos} tramos (por San Miguel y camión refrigerado) y pierde {_n(dij.costo, 2)}.", ""]
    # Reacomodo: cuanto se pierde con 1, 2, ... acopios y que hace cada acopio de hoy
    curva = an["curva"].assign(S=lambda d: d["S"].map(conj))
    lineas += ["**Reacomodo de los acopios (p-mediana sobre centros poblados, curva del codo):**", ""] + _tabla_md(curva) + [""]
    via = acopios.viabilidad(an, an["actuales"])
    via = via.assign(nombre=via["acopio"].map(lambda j: nombres.get(j, j)))
    lineas += ["**Qué hace cada acopio de hoy** (kg/día de las zonas que atiende y pérdida que evita, en kg equivalentes/día):", ""]
    lineas += _tabla_md(via[["nombre", "kg_dia", "perdida_evitada_kg_dia"]]) + [""]
    pre_mc = acopios.cargar_precalculado()
    if pre_mc is not None:
        mc = pre_mc["mc"]
        for j, sub in mc.groupby("acopio"):
            positivo = 100 * (sub["vpn"] > 0).mean()
            lineas.append(f"- {nombres.get(j, j)} en el grafo (comparado con ir directo a la plaza): VPN medio {_n(sub['vpn'].mean() / 1e6, 1)} M COP, "
                          f"positivo en el {_n(positivo, 0)} % de {len(sub)} corridas [SIMULADO].")
        lineas.append("")
    metodos = an["metodos"].assign(S=lambda d: d["S"].map(conj))
    lineas += [f"**Candidatos (centros poblados):** {conj(an['candidatos'])}. Excluidos: "
               + "; ".join(f"{r.nombre} ({r.motivo})" for r in an["tabla_candidatos"].itertuples() if not r.candidato) + ".", "",
               f"**Acopios elegidos (`S*`, p = {an['p_codo']} en el codo):** {conj(an['S'])}, con "
               f"{_n(acopios.f(an['c'], an['w'], an['S']))} kg equivalentes perdidos por día [SIMULADO].", ""]
    lineas += _tabla_md(metodos) + [""]
    lineas += [f"- Costo de exigir pueblos (`S*` − p-mediana libre): {_n(max(0.0, an['costo_exigir_pueblos']))} kg/día.",
               f"- Centroide de las zonas ({g.nodes[an['centroide']]['nombre'] if an['centroide'] in g else an['centroide']}): {_n(an['f_centroide_p1'])} kg/día, contra {_n(an['f_p1'])} de la p-mediana con 1 acopio.",
               f"- Acopios de hoy ({conj(an['actuales'])}): {_n(an['f_actuales'])} kg/día.", ""]
    pre = acopios.cargar_precalculado()
    if pre is not None:
        sens = pre["sensibilidad"].assign(S=lambda d: d["S"].map(conj))
        lineas += ["**Sensibilidad:**", ""] + _tabla_md(sens) + [""]
        cambia = sens.loc[sens["cambia"], "variable"].unique()
        lineas += [f"`S*` cambia con: {', '.join(cambia)}." if len(cambia) else "`S*` no cambia en ningún caso: la conclusión es robusta.", ""]
    return "\n".join(lineas)
