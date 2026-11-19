"""Pruebas 8, 9 y 11 de la adenda (§7): acopios sobre el grafo v4."""

import numpy as np
import pandas as pd
import pytest

from pesca import acopios, config, grafo

G = grafo.construir_grafo()
CENTROS = config.cargar_centros_poblados()
AN = acopios.analizar(G, CENTROS)


# ---------------------------------------------------------------- prueba 8: candidatos


def test_todo_acopio_elegido_es_un_centro_poblado_candidato():
    assert set(AN["S"]) <= set(AN["candidatos"])
    assert set(AN["candidatos"]) <= set(CENTROS["id"])
    for j in AN["S"]:
        assert G.nodes[f"{j}:entra"]["tipo"] == "centro_poblado"
    assert not any(G.nodes.get(j, {}).get("tipo") == "punto_rio" for j in AN["S"])


def test_cada_excluido_tiene_su_motivo():
    tabla = AN["tabla_candidatos"]
    assert (tabla.loc[~tabla["candidato"], "motivo"].str.len() > 0).all()
    assert (tabla.loc[tabla["candidato"], "motivo"] == "").all()
    motivo = tabla.set_index("nombre")["motivo"]
    assert "sin coordenadas" in motivo["Domo Planas"]
    assert "P_min" in motivo["Murujuy"]


def test_regla_de_candidatos_responde_a_p_min_y_al_acceso():
    todos, _ = acopios.candidatos(CENTROS, G, p_min=0, criterio_acceso="permisivo")
    pocos, tabla = acopios.candidatos(CENTROS, G, p_min=1000)
    assert pocos == ["CP01"]
    assert set(pocos) <= set(todos)
    assert "habitantes < P_min" in tabla.set_index("id").at["CP03", "motivo"]


def test_datos_por_confirmar_quedan_marcados():
    tabla = AN["tabla_candidatos"].set_index("id")
    assert (tabla.loc[AN["candidatos"], "marca"] == "[CONFIRMAR]").all()


# ---------------------------------------------------------------- c_ij y p-mediana (prueba 9)


def test_costos_entre_0_y_1():
    c = AN["c"]
    assert ((c >= 0) & (c <= 1 + 1e-12)).all().all()
    # La Cristalina no tiene acceso por rio: ningun pescador llega con su bote (promedio ponderado de unos)
    assert list(c["CP02"]) == pytest.approx([config.parametro("acopios_grafo.costo_sin_destino")] * len(c))


def test_enumeracion_igual_a_ilp():
    for p in range(1, len(AN["candidatos"]) + 1):
        enum = acopios.p_mediana_enumeracion(AN["c"], AN["w"], p)
        ilp = acopios.p_mediana_ilp(AN["c"], AN["w"], p)
        assert ilp["f"] == pytest.approx(enum["f"], abs=1e-9)


def test_tres_metodos_y_gap():
    tabla = AN["metodos"].set_index("metodo")
    assert tabla.at["ilp", "f"] == pytest.approx(tabla.at["enumeracion", "f"])
    assert tabla.at["busqueda_local", "gap_pct"] >= -1e-9


def test_f_no_crece_con_p():
    f = AN["curva"]["f"].to_numpy()
    assert (np.diff(f) <= 1e-12).all()


@pytest.mark.parametrize("semilla", range(20))
def test_metodos_en_instancias_al_azar(semilla):
    rng = np.random.default_rng(semilla)
    c = pd.DataFrame(rng.random((8, 9)), index=[f"i{k}" for k in range(8)], columns=[f"j{k}" for k in range(9)])
    w = pd.Series(rng.uniform(1, 10, 8), index=c.index)
    enum = acopios.p_mediana_enumeracion(c, w, 3)
    assert acopios.p_mediana_ilp(c, w, 3)["f"] == pytest.approx(enum["f"])
    local = acopios.p_mediana_busqueda_local(c, w, 3)
    assert local["f"] >= enum["f"] - 1e-12  # heuristica: nunca mejor que el optimo
    fijos = acopios.p_mediana_enumeracion(c, w, 4, ("j0",))
    assert "j0" in fijos["S"] and fijos["f"] >= acopios.p_mediana_enumeracion(c, w, 4)["f"] - 1e-12


def test_ilp_con_capacidad():
    c = pd.DataFrame([[0.1, 0.3], [0.2, 0.1]], index=["i1", "i2"], columns=["A", "B"])
    w = pd.Series({"i1": 100.0, "i2": 50.0})
    sin = acopios.p_mediana_ilp(c, w, 2)
    con = acopios.p_mediana_ilp(c, w, 2, capacidad=pd.Series({"A": 80.0, "B": 1000.0}))
    assert sin["f"] == pytest.approx(100 * 0.1 + 50 * 0.1)
    assert con["f"] == pytest.approx(80 * 0.1 + 20 * 0.3 + 50 * 0.1)


# ---------------------------------------------------------------- prueba 11: Voronoi


def test_cada_zona_va_a_su_argmin():
    asig = acopios.voronoi(AN["c"], AN["S"])
    for i, j in asig.items():
        assert AN["c"].at[i, j] == AN["c"].loc[i, list(AN["S"])].min()


# ---------------------------------------------------------------- referencias, viabilidad y sensibilidad


def test_referencias():
    assert AN["libre"]["f"] <= acopios.f(AN["c"], AN["w"], AN["S"]) + 1e-12  # la p-mediana libre es cota inferior
    assert AN["costo_exigir_pueblos"] >= -1e-12
    assert AN["f_centroide_p1"] >= AN["f_p1"] - 1e-12  # el punto medio no le gana a la p-mediana
    assert AN["centroide"] in G or f"{AN['centroide']}:entra" in G


def test_viabilidad():
    via = acopios.viabilidad(AN, AN["S"]).set_index("acopio")
    assert via["kg_dia"].sum() == pytest.approx(AN["w"].sum())
    assert (via["perdida_evitada_kg_dia"] >= -1e-12).all()
    assert via.at["CP01", "veredicto"].startswith("ya funciona")


def test_montecarlo_y_regla_de_decision():
    mc = acopios.montecarlo_viabilidad(AN["S"], n=8)
    assert set(mc["acopio"]) == set(AN["S"]) - {acopios.PLAZA}
    via = acopios.viabilidad(AN, AN["S"], mc).set_index("acopio")
    for j in set(AN["S"]) - {acopios.PLAZA}:
        assert via.at[j, "veredicto"] in ("vale la pena", "no vale la pena")
        assert 0 <= via.at[j, "pct_vpn_positivo"] <= 100


def test_sensibilidad():
    sens = acopios.sensibilidad(AN)
    assert set(sens["variable"]) == {"P_min", "criterio_acceso", "temporada", "embarcacion"}
    base = sens[(sens["variable"] == "P_min") & (sens["valor"] == str(config.parametro("acopios_grafo.p_min_habitantes")))]
    assert not base["cambia"].any()
    assert sens.apply(lambda r: set(r["S"]) <= set(CENTROS["id"]), axis=1).all()
