import pandas as pd
import pytest

from pesca import busqueda, config, grafo, visualizacion
from pesca.red import haversine_km

NODOS, ARISTAS, CENTROS = config.cargar_nodos_grafo(), config.cargar_aristas(), config.cargar_centros_poblados()
TOLERANCIA = config.parametro("red.tolerancia_calibracion")


@pytest.fixture
def g():
    return grafo.construir_grafo()


def _distancia(u, v, a):
    return a["d_km"]


# ---------------------------------------------------------------- construccion


def test_cada_tramo_de_rio_tiene_su_inverso_con_sentido_opuesto(g):
    rios = [(u, v, a) for u, v, a in g.edges(data=True) if a["tipo"] == "rio"]
    assert len(rios) == 2 * (ARISTAS["tipo"] == "rio").sum()
    for u, v, a in rios:
        inverso = g.edges[v, u]
        assert inverso["tipo"] == "rio"
        assert inverso["sentido"] == -a["sentido"] != 0
        assert inverso["d_km"] == a["d_km"]


def test_accesos_vias_y_transbordos_en_los_dos_sentidos(g):
    for u, v, a in g.edges(data=True):
        if a["tipo"] in grafo.TIPOS_DOBLES:
            assert g.has_edge(v.replace(":entra", ":sale"), u.replace(":sale", ":entra")), a["id"]


def test_nodo_dividido_de_cada_centro_poblado(g):
    centros = set(NODOS.loc[NODOS["tipo"] == "centro_poblado", "id"])
    assert centros and not centros & set(g.nodes)
    for c in centros:
        entra, sale = c + grafo.ENTRA, c + grafo.SALE
        assert g.edges[entra, sale]["tipo"] == "espera"
        assert list(g.successors(entra)) == [sale]
        assert list(g.predecessors(sale)) == [entra]


def test_venta_solo_hacia_el_mercado(g):
    for m in grafo.mercados(g):
        assert g.out_degree(m) == 0
        assert {g.edges[u, m]["tipo"] for u in g.predecessors(m)} == {"venta"}


def test_arcos_sin_pesos_y_con_su_fuente(g):
    for _, _, a in g.edges(data=True):
        assert {"d_km", "tipo", "modo", "sentido", "clase_via", "fuente", "validado"} <= set(a)
        assert not {"peso", "tiempo_h", "perdida"} & set(a)
        assert a["etiqueta"] in config.ETIQUETAS


def test_ids_unicos(g):
    ids = [a["id"] for *_, a in g.edges(data=True)]
    assert len(ids) == len(set(ids))
    assert NODOS["id"].is_unique


def test_dos_arcos_entre_el_mismo_par_es_un_error():
    repetida = pd.concat([ARISTAS, ARISTAS.iloc[[0]].assign(id="T999")], ignore_index=True)
    with pytest.raises(ValueError, match="Dos arcos"):
        grafo.construir_grafo(NODOS, repetida, CENTROS)


# ---------------------------------------------------------------- validacion (§7 pruebas 12 y 13)


def test_d_km_no_menor_que_la_linea_recta(g):
    for _, _, a in g.edges(data=True):
        if a["modo"] != "interno":
            assert a["d_km"] >= haversine_km(*a["geometria"][0], *a["geometria"][1]) - 1e-4, a["id"]


def test_validar_grafo_real(g):
    val = grafo.validar_grafo(g)
    assert val.ok, val.errores
    alc = val.alcanzabilidad
    for zona, sub in alc.groupby("zona"):
        assert sub.loc[sub["destino"].isin(grafo.candidatos(g)), "alcanzable"].any(), zona
        assert sub.loc[sub["destino"].isin(grafo.mercados(g)), "alcanzable"].all(), zona
    assert set(alc["zona"]) == set(NODOS.loc[NODOS["tipo"] == "zona_pesca", "id"])


def test_zona_aislada_es_un_error():
    nodos = pd.concat(
        [NODOS, pd.DataFrame([{**NODOS.iloc[0].to_dict(), "id": "P99", "nombre": "zona suelta", "tipo": "zona_pesca"}])],
        ignore_index=True,
    )
    val = grafo.validar_grafo(grafo.construir_grafo(nodos, ARISTAS, CENTROS))
    assert any("P99" in e for e in val.errores)


def test_el_agua_no_une_las_cuencas(g):
    val = grafo.validar_grafo(g)
    for comp in val.componentes_agua:
        assert len({g.nodes[n]["cuenca"] for n in comp} & {"meta", "vichada"}) <= 1
    # un rio de juguete que une un punto del Vichada con el Meta hace fallar la validacion
    vichada = {**NODOS.iloc[0].to_dict(), "id": "R900", "cuenca": "vichada", "lat": 4.2, "lon": -71.9}
    puente = {**ARISTAS.iloc[0].to_dict(), "id": "T900", "origen": "R900", "destino": NODOS.iloc[0]["id"], "distancia_km": 30.0}
    malo = grafo.construir_grafo(
        pd.concat([NODOS, pd.DataFrame([vichada])], ignore_index=True),
        pd.concat([ARISTAS, pd.DataFrame([puente])], ignore_index=True),
        CENTROS,
    )
    assert any("cuencas" in e for e in grafo.validar_grafo(malo).errores)


def test_componentes_dfs_igual_a_networkx(g):
    propios = sorted(map(sorted, busqueda.componentes_dfs(g)))
    import networkx as nx

    assert propios == sorted(map(sorted, nx.weakly_connected_components(g)))


# ---------------------------------------------------------------- calibracion (§7 prueba 1)


def test_calibracion_reproduce_lo_medido(g):
    cal = grafo.calibrar(g)
    assert {"M01", "M02", "M03", "M04"} <= set(cal["id"])
    assert cal["dentro"].all(), cal
    # lo que va por trazas simuladas reproduce la medicion; donde hay traza KML manda la traza (M04 se reporta)
    medicion = cal[cal["manda"] == "medición"]
    assert (medicion["error_pct"].abs() <= 100 * TOLERANCIA).all()
    assert set(medicion["id"]) >= {"M01", "M02", "M03"}
    assert cal.set_index("id").at["M04", "manda"] == "KML"
    assert g.graph["ajustes"] == []


def _simulado_de_m02() -> str:
    """El tramo de rio SIMULADO mas largo de M02 (Yucao → Puerto Gaitan); M04 va toda por la traza KML."""
    g = grafo.construir_grafo()
    r = grafo._por_distancia(g, "rio", "E_C01", "E_CP01")
    ids = {g.edges[u, v]["id"].split("~")[0] for u, v in zip(r.ruta, r.ruta[1:])
           if g.edges[u, v]["tipo"] == "rio" and g.edges[u, v]["etiqueta"] == "SIMULADO"}
    return ARISTAS[ARISTAS["id"].isin(ids)].sort_values("distancia_km")["id"].iloc[-1]


def test_calibrar_escala_solo_los_accesos():
    # M02 queda 1 km corta en un tramo simulado y el acceso de Yucao mide 0,2 km: para cerrar M02 el acceso debe pasar a 1,0 km
    corto = _simulado_de_m02()
    acceso = ARISTAS.loc[(ARISTAS["tipo"] == "acceso") & (ARISTAS["destino"] == "E_C01"), "id"].item()
    aristas = ARISTAS.copy()
    aristas.loc[aristas["id"] == corto, "distancia_km"] -= 1.0
    aristas.loc[aristas["id"] == acceso, "distancia_km"] = 0.2
    g = grafo.construir_grafo(NODOS, aristas, CENTROS)
    rio_antes = {a["id"]: a["d_km"] for *_, a in g.edges(data=True) if a["tipo"] in ("rio", "via")}

    cal = grafo.calibrar(g).set_index("id")
    assert cal["dentro"].all(), cal
    assert acceso in cal.at["M02", "ajuste"]
    assert len(g.graph["ajustes"]) == 1
    escalado = [a["d_km"] for *_, a in g.edges(data=True) if a["id"].startswith(acceso)]
    assert escalado == pytest.approx([1.0, 1.0], abs=1e-3)  # el CSV guarda los km con 4 decimales
    assert rio_antes == {a["id"]: a["d_km"] for *_, a in g.edges(data=True) if a["tipo"] in ("rio", "via")}
    assert (config.cargar_distancias_medidas()["distancia_km"].head(4) == [15.14, 17.38, 38.9, 41.65]).all()


def test_calibrar_reporta_cuando_no_alcanza():
    aristas = ARISTAS.copy()
    aristas.loc[aristas["id"] == _simulado_de_m02(), "distancia_km"] -= 5.0
    cal = grafo.calibrar(grafo.construir_grafo(NODOS, aristas, CENTROS)).set_index("id")
    assert not cal.at["M02", "dentro"]
    assert cal.at["M02", "ajuste"].startswith("no calibra")


# ---------------------------------------------------------------- texto, pasos y mapa


def test_ruta_a_texto_san_miguel_a_puerto_gaitan_por_rio(g):
    # solo por agua: por carretera es mas corto (38,9 km)
    r = grafo._por_distancia(g, "rio", "E_CP03", "E_CP01")
    rio = [(u, v) for u, v in zip(r.ruta, r.ruta[1:]) if g.edges[u, v]["tipo"] == "rio"]
    km_m04 = grafo.calibrar(g).set_index("id").at["M04", "km_grafo"]  # por la traza KML del Meta
    assert sum(g.edges[e]["d_km"] for e in rio) == pytest.approx(km_m04)
    texto = grafo.ruta_a_texto(g, r.ruta)
    assert len(texto) == 1
    assert "contra la corriente" in texto[0] and texto[0].startswith("Por río")


def test_ruta_a_texto_bimodal(g):
    r = busqueda.dijkstra(g, "E_CP03", "MER_CP01", _distancia)
    texto = grafo.ruta_a_texto(g, r.ruta)
    assert texto[0] == "Transbordo en el embarcadero de San Miguel"
    assert any(t.startswith("Por carretera 38,9 km") for t in texto)
    assert texto[-1] == "Venta en la plaza de mercado de Puerto Gaitán"


def test_estado_de_los_siete_pasos(g):
    pasos = grafo.estado_pasos(g, grafo.validar_grafo(g), grafo.calibrar(g))
    assert list(pasos["paso"]) == list(range(1, 8))
    assert set(pasos["estado"]) <= {"hecho", "simulado", "pendiente", "error"}
    assert pasos.set_index("paso").at[7, "estado"] == "hecho"
    assert pasos.set_index("paso").at[6, "estado"] == "hecho"  # G3: pesos.py


def test_mapa_con_flechas_de_corriente(g):
    html = visualizacion.mapa_grafo(g).get_root().render()
    assert "►" in html or "\\u25ba" in html
    assert "Carreteras" in html
