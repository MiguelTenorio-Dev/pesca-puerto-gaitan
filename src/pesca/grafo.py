"""Grafo dirigido y multimodal de la adenda v4 (§2), construido solo desde los CSV del grafo.

- Un tramo de rio viene una vez en aristas.csv (sentido +1, aguas abajo); aqui se crea el inverso
  (sentido -1, id "<id>~inv"). Accesos, vias y transbordos van en los dos sentidos (id "<id>~vuelta").
- Cada centro poblado es un nodo dividido "<id>:entra" -> "<id>:sale" unido por un arco de espera
  (adenda §2.2): lo que llega entra por ":entra" y lo que sale parte de ":sale". Asi el costo de esperar
  o almacenar en el pueblo es el costo de un arco y las busquedas no necesitan casos especiales.
- Todavia no hay pesos: cada arco guarda d_km, tipo, modo, sentido, clase_via, fuente y validado.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx
import pandas as pd

from pesca import busqueda, config, grafo_datos
from pesca.red import haversine_km

ENTRA, SALE = ":entra", ":sale"
INVERSO, VUELTA = "~inv", "~vuelta"
TIPOS_DOBLES = {"acceso", "via", "transbordo"}
TIPOS_AGUA = {"rio", "acceso"}

TEXTO_SENTIDO = {1: "a favor de la corriente", -1: "contra la corriente", 0: "sin corriente"}


# ---------------------------------------------------------------- construccion


def _dividido(nodos: pd.DataFrame) -> set[str]:
    return set(nodos.loc[nodos["tipo"] == "centro_poblado", "id"])


def construir_grafo(
    nodos: pd.DataFrame | None = None, aristas: pd.DataFrame | None = None, centros: pd.DataFrame | None = None
) -> nx.DiGraph:
    """DiGraph desde nodos.csv, aristas.csv y centros_poblados.csv (por defecto, los del paquete)."""
    nodos = nodos if nodos is not None else config.cargar_nodos_grafo()
    aristas = aristas if aristas is not None else config.cargar_aristas()
    centros = centros if centros is not None else config.cargar_centros_poblados()
    divididos = _dividido(nodos)

    g = nx.DiGraph()
    g.graph.update(
        ajustes=[],
        ids_repetidos=sorted(set(nodos["id"][nodos["id"].duplicated()]) | set(aristas["id"][aristas["id"].duplicated()])),
        n_centros=len(centros),
        sin_coordenadas=list(centros.loc[centros["lat"].isna(), "nombre"]),
    )
    for fila in nodos.to_dict("records"):
        atributos = {**fila, "etiqueta": grafo_datos.etiqueta(fila["fuente"])}
        if fila["id"] in divididos:
            for parte in (ENTRA, SALE):
                g.add_node(fila["id"] + parte, **atributos, parte=parte[1:])
        else:
            g.add_node(fila["id"], **atributos, parte=None)

    def salida(n: str) -> str:
        return n + SALE if n in divididos else n

    def entrada(n: str) -> str:
        return n + ENTRA if n in divididos else n

    def agregar(u: str, v: str, id_arco: str, fila: dict, sentido: int) -> None:
        if g.has_edge(u, v):
            raise ValueError(f"Dos arcos entre {u} y {v} ({g.edges[u, v]['id']} y {id_arco})")
        a, b = g.nodes[u], g.nodes[v]
        g.add_edge(
            u, v, id=id_arco, d_km=float(fila["distancia_km"]), tipo=fila["tipo"], modo=fila["modo"], sentido=sentido,
            clase_via=fila["clase_via"], fuente=fila["fuente"], etiqueta=grafo_datos.etiqueta(fila["fuente"]),
            validado=fila["validado"], notas=fila["notas"], geometria=[(a["lat"], a["lon"]), (b["lat"], b["lon"])],
        )

    for fila in aristas.to_dict("records"):
        o, d, tipo = fila["origen"], fila["destino"], fila["tipo"]
        agregar(salida(o), entrada(d), fila["id"], fila, int(fila["sentido"]))
        if tipo == "rio":
            agregar(salida(d), entrada(o), fila["id"] + INVERSO, fila, -int(fila["sentido"]))
        elif tipo in TIPOS_DOBLES:
            agregar(salida(d), entrada(o), fila["id"] + VUELTA, fila, 0)
        if tipo == "transbordo":
            # el pueblo del transbordo: si es punto frio, ahi se recoge hielo nuevo (pesos.capa_nueva)
            pueblo = d if g.nodes[entrada(d)]["tipo"] in ("centro_poblado", "comunidad") else o
            for u, v in ((salida(o), entrada(d)), (salida(d), entrada(o))):
                g.edges[u, v]["pueblo"] = pueblo

    for c in sorted(divididos):
        fila = {
            "distancia_km": 0.0, "tipo": "espera", "modo": "interno", "clase_via": None, "validado": "no",
            "fuente": "SIMULADO: nodo dividido entra → sale; el tiempo espera_h lo pone el escenario", "notas": None,
        }
        agregar(c + ENTRA, c + SALE, f"ESP_{c}", fila, 0)
        g.edges[c + ENTRA, c + SALE]["centro"] = c
    return g


# ---------------------------------------------------------------- tablas y texto


def tabla_nodos(g: nx.DiGraph) -> pd.DataFrame:
    filas = [{"nodo": n, **a} for n, a in g.nodes(data=True)]
    columnas = ["nodo", "nombre", "tipo", "parte", "cuenca", "lat", "lon", "etiqueta", "fuente", "validado", "notas"]
    return pd.DataFrame(filas)[columnas]


def tabla_arcos(g: nx.DiGraph) -> pd.DataFrame:
    filas = [{"origen": u, "destino": v, **{k: x for k, x in a.items() if k != "geometria"}} for u, v, a in g.edges(data=True)]
    columnas = ["id", "origen", "destino", "tipo", "modo", "sentido", "d_km", "clase_via", "etiqueta", "fuente", "validado", "notas"]
    return pd.DataFrame(filas)[columnas]


def _minuscula(texto: str) -> str:
    return texto[:1].lower() + texto[1:]


def _km(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")


def ruta_a_texto(g: nx.DiGraph, camino: list[str] | tuple[str, ...]) -> list[str]:
    """La ruta tramo a tramo en español. Junta los tramos seguidos del mismo modo y sentido."""
    lineas: list[str] = []
    grupo: dict | None = None

    def cerrar() -> None:
        if grupo is None:
            return
        desde, hasta = g.nodes[grupo["desde"]]["nombre"], g.nodes[grupo["hasta"]]["nombre"]
        if grupo["modo"] == "rio":
            lineas.append(f"Por río {_km(grupo['km'])} km {TEXTO_SENTIDO[grupo['sentido']]}, de {desde} a {hasta}")
        else:
            lineas.append(f"Por carretera {_km(grupo['km'])} km, de {desde} a {hasta}")

    for u, v in zip(camino, camino[1:]):
        a = g.edges[u, v]
        if a["modo"] in ("rio", "via"):
            if a["d_km"] == 0:
                continue  # acceso o enlace sobre el mismo punto
            clave = (a["modo"], a["sentido"])
            if grupo is not None and (grupo["modo"], grupo["sentido"]) == clave:
                grupo.update(km=grupo["km"] + a["d_km"], hasta=v)
            else:
                cerrar()
                grupo = {"modo": a["modo"], "sentido": a["sentido"], "km": a["d_km"], "desde": u, "hasta": v}
            continue
        cerrar()
        grupo = None
        if a["tipo"] == "transbordo":
            embarcadero = u if g.nodes[u]["tipo"] == "embarcadero" else v
            lineas.append(f"Transbordo en el {_minuscula(g.nodes[embarcadero]['nombre'])}")
        elif a["tipo"] == "espera":
            lineas.append(f"Pasa por el centro de {g.nodes[u]['nombre']} (aquí se entrega o se espera)")
        elif a["tipo"] == "venta":
            lineas.append(f"Venta en la {_minuscula(g.nodes[v]['nombre'])}")
    cerrar()
    return lineas


# ---------------------------------------------------------------- validacion


@dataclass
class Validacion:
    errores: list[str] = field(default_factory=list)
    alcanzabilidad: pd.DataFrame = field(default_factory=pd.DataFrame)
    componentes_agua: list[set[str]] = field(default_factory=list)
    n_componentes: int = 0

    @property
    def ok(self) -> bool:
        return not self.errores


def candidatos(g: nx.DiGraph) -> list[str]:
    """Nodos de llegada de los centros poblados del grafo (la regla completa de §4.1 es de G5)."""
    return sorted(n for n, a in g.nodes(data=True) if a["tipo"] == "centro_poblado" and a["parte"] == "entra")


def mercados(g: nx.DiGraph) -> list[str]:
    return sorted(n for n, a in g.nodes(data=True) if a["tipo"] == "mercado")


def validar_grafo(g: nx.DiGraph) -> Validacion:
    """Adenda §2.3 paso 7 y §7 pruebas 12–13: alcanzabilidad, ids, d >= linea recta y cuencas."""
    val = Validacion()
    if g.graph.get("ids_repetidos"):
        val.errores.append(f"ids repetidos: {g.graph['ids_repetidos']}")
    ids_arcos = pd.Series([a["id"] for *_, a in g.edges(data=True)])
    if ids_arcos.duplicated().any():
        val.errores.append(f"ids de arco repetidos: {sorted(set(ids_arcos[ids_arcos.duplicated()]))}")

    for u, v, a in g.edges(data=True):
        if a["modo"] == "interno":
            continue
        recta = haversine_km(*a["geometria"][0], *a["geometria"][1])
        if a["d_km"] < recta - 1e-4:
            val.errores.append(f"{a['id']}: d_km = {a['d_km']:.3f} < línea recta {recta:.3f}")

    destinos = candidatos(g) + mercados(g)
    filas = []
    for zona in sorted(n for n, a in g.nodes(data=True) if a["tipo"] == "zona_pesca"):
        for destino in destinos:
            r = busqueda.bfs(g, zona, destino)
            filas.append({"zona": zona, "destino": destino, "alcanzable": r.alcanzable, "tramos": r.tramos if r.alcanzable else None})
    val.alcanzabilidad = pd.DataFrame(filas, columns=["zona", "destino", "alcanzable", "tramos"])
    for zona, sub in val.alcanzabilidad.groupby("zona"):
        if not sub.loc[sub["destino"].isin(candidatos(g)), "alcanzable"].any():
            val.errores.append(f"{zona} no llega a ningún centro poblado")
        if not sub.loc[sub["destino"].isin(mercados(g)), "alcanzable"].any():
            val.errores.append(f"{zona} no llega al mercado")

    agua = g.edge_subgraph([(u, v) for u, v, a in g.edges(data=True) if a["tipo"] in TIPOS_AGUA])
    val.componentes_agua = busqueda.componentes_dfs(agua)
    for comp in val.componentes_agua:
        cuencas = {g.nodes[n]["cuenca"] for n in comp} & {"meta", "vichada"}
        if len(cuencas) > 1:
            val.errores.append(f"El agua une las cuencas del Meta y del Vichada: {sorted(comp)[:5]}…")
    val.n_componentes = len(busqueda.componentes_dfs(g))
    return val


# ---------------------------------------------------------------- calibracion


def _extremos(g: nx.DiGraph, origen: str, destino: str, modo: str) -> tuple[str, str]:
    """Nodos donde empieza y termina una ruta medida: embarcaderos por río, centros por vía."""
    a, b = grafo_datos.LUGARES_MEDIDOS[origen], grafo_datos.LUGARES_MEDIDOS[destino]
    if modo == "rio":
        return f"E_{a}", f"E_{b}"
    return (a + SALE if a + SALE in g else a), (b + ENTRA if b + ENTRA in g else b)


def _por_distancia(g: nx.DiGraph, modo: str, origen: str, destino: str) -> busqueda.ResultadoBusqueda:
    tipos = TIPOS_AGUA if modo == "rio" else {"via"}
    sub = g.edge_subgraph([(u, v) for u, v, a in g.edges(data=True) if a["tipo"] in tipos])
    if origen not in sub or destino not in sub:
        return busqueda.ResultadoBusqueda("dijkstra", origen, destino, (), float("inf"), (), 0.0)
    return busqueda.dijkstra(sub, origen, destino, lambda u, v, a: a["d_km"])


def calibrar(g: nx.DiGraph) -> pd.DataFrame:
    """Compara el grafo con M01–M04 (Dijkstra propio por distancia, dentro del modo de la ruta).

    Si una ruta de rio se sale de la tolerancia, escala solo sus arcos de acceso con d > 0 (factor >= 1)
    y lo anota en g.graph["ajustes"]. Nunca toca las distancias medidas ni los tramos de rio o via.
    """
    tolerancia = config.parametro("red.tolerancia_calibracion")
    filas = []
    for m in config.cargar_distancias_medidas().itertuples():
        o, d = _extremos(g, m.origen, m.destino, m.modo)
        r = _por_distancia(g, m.modo, o, d)
        km, ajuste = r.costo, ""
        trazas = [g.edges[u, v] for u, v in zip(r.ruta, r.ruta[1:])
                  if g.edges[u, v]["d_km"] > 0 and not grafo_datos.es_enlace(g.edges[u, v]["fuente"])]
        manda = "KML" if trazas and all(a["etiqueta"] == "MEDIDO" for a in trazas) else "medición"
        if manda == "KML":
            ajuste = "manda la traza KML; la diferencia con la medición a mano solo se reporta"
        elif r.alcanzable and abs(km / m.distancia_km - 1) > tolerancia:
            accesos = [(u, v) for u, v in zip(r.ruta, r.ruta[1:]) if g.edges[u, v]["tipo"] == "acceso" and g.edges[u, v]["d_km"] > 0]
            km_acceso = sum(g.edges[e]["d_km"] for e in accesos)
            factor = (m.distancia_km - (km - km_acceso)) / km_acceso if km_acceso > 0 else 0.0
            if factor >= 1:
                for u, v in accesos:
                    for arco in ((u, v), (v, u)):
                        if g.has_edge(*arco):
                            g.edges[arco]["d_km"] *= factor
                ids = sorted(g.edges[e]["id"] for e in accesos)
                ajuste = f"accesos {ids} × {factor:.3f}"
                g.graph["ajustes"].append(f"{m.id}: {ajuste}")
                km = _por_distancia(g, m.modo, o, d).costo
            else:
                ajuste = "no calibra: escalar los accesos no alcanza; revisar las trazas"
        filas.append(
            {
                "id": m.id, "modo": m.modo, "km_medido": float(m.distancia_km), "km_grafo": km,
                "error_pct": 100 * (km / m.distancia_km - 1), "manda": manda, "ajuste": ajuste,
            }
        )
    tabla = pd.DataFrame(filas)
    tabla["dentro"] = (tabla["error_pct"].abs() <= 100 * tolerancia) | (tabla["manda"] == "KML")
    return tabla


# ---------------------------------------------------------------- pasos de §2.3


def estado_pasos(g: nx.DiGraph, val: Validacion, cal: pd.DataFrame) -> pd.DataFrame:
    """Los 7 pasos de la construccion (adenda §2.3) con su estado: hecho, simulado, pendiente o error."""
    nodos, arcos = tabla_nodos(g), tabla_arcos(g)

    def por_traza(tipo: str, archivo: str) -> tuple[str, str]:
        etiquetas = sorted(set(arcos.loc[arcos["tipo"] == tipo, "etiqueta"]))
        if etiquetas == ["MEDIDO"]:
            return "hecho", f"{(arcos['tipo'] == tipo).sum() // 2} tramos medidos en KML"
        return "simulado", f"tramos {', '.join(etiquetas)}; falta {archivo}"

    sin_validar = (nodos.drop_duplicates("nombre")["validado"] == "no").sum()
    centros = nodos[(nodos["tipo"] == "centro_poblado") & (nodos["parte"] == "entra")]
    zonas = nodos[nodos["tipo"] == "zona_pesca"]
    pasos = [
        ("Reunir coordenadas", "simulado" if sin_validar else "hecho", f"{sin_validar} lugares con validado = no"),
        ("Esqueleto del río", *por_traza("rio", "rio.kml")),
        ("Esqueleto vial", *por_traza("via", "vias.kml")),
        (
            "Colgar los pueblos",
            "simulado" if g.graph["sin_coordenadas"] else "hecho",
            f"{len(centros)} de {g.graph['n_centros']} centros en el grafo; sin coordenadas: {', '.join(g.graph['sin_coordenadas']) or 'ninguno'}",
        ),
        (
            "Colgar las zonas de pesca",
            "simulado" if (zonas["etiqueta"] != "DATO").any() else "hecho",
            f"{len(zonas)} zonas ({', '.join(sorted(set(zonas['etiqueta'])))}); falta pesca.kml",
        ),
        ("Atributos por escenario (v, τ, ΔQ)", "hecho", "pesos.py: velocidad con la corriente, tiempo y pérdida de calidad por capas, según bote, temporada y nevera"),
        (
            "Validar",
            "hecho" if val.ok and cal["dentro"].all() else "error",
            f"alcanzabilidad, d ≥ línea recta y cuencas: {'bien' if val.ok else '; '.join(val.errores)}; "
            f"M01–M04: {'dentro de la tolerancia' if cal['dentro'].all() else 'fuera'}",
        ),
    ]
    return pd.DataFrame([{"paso": i, "nombre": n, "estado": e, "detalle": d} for i, (n, e, d) in enumerate(pasos, 1)])
