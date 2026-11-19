import pandas as pd
import pytest

from pesca import acopios, config, grafo, laboratorio, pesos, recomendador

G = grafo.construir_grafo()
CON_SAN_MIGUEL = pesos.Condiciones(nevera="sin_hielo", acopios=frozenset({"CP01", "CP03"}))


# ---------------------------------------------------------------- flujo con capacidades


def test_caso_2x2_resuelto_a_mano():
    # i1 prefiere A (0,1) pero A solo recibe 80 kg: 80 a A y 20 a B (0,3); i2 a B. Costo 8 + 6 + 5 = 19
    c = pd.DataFrame([[0.1, 0.3], [0.2, 0.1]], index=["i1", "i2"], columns=["A", "B"])
    w = pd.Series({"i1": 100.0, "i2": 50.0})
    flujo = recomendador.flujo_minimo(c, w, pd.Series({"A": 80.0, "B": float("nan")}), ["A", "B"])
    kg = flujo.set_index(["zona", "destino"])["kg_dia"]
    assert kg[("i1", "A")] == 80 and kg[("i1", "B")] == 20 and kg[("i2", "B")] == 50
    assert (flujo["kg_dia"] * flujo["c_ij"]).sum() == pytest.approx(19.0)


def test_flujo_se_conserva_y_respeta_capacidades():
    an = acopios.analizar(G)
    capacidad = acopios.capacidad(config.cargar_centros_poblados())
    w = an["w"] * 100  # carga grande para que la capacidad muerda
    flujo = recomendador.flujo_minimo(an["c"], w, capacidad, an["S"])
    enviado = flujo.groupby("zona")["kg_dia"].sum()
    assert (enviado == w.round().astype(int)).all()
    for j, kg in flujo.groupby("destino")["kg_dia"].sum().items():
        if j != acopios.SIN_DESTINO:
            assert kg <= capacidad[j]


def test_sin_capacidades_coincide_con_voronoi():
    an = acopios.analizar(G)
    sin_tope = pd.Series(dtype=float)
    tabla = recomendador.comparar_con_voronoi(an["c"], an["w"], sin_tope, an["S"])
    assert not tabla["difiere"].any()


def test_con_capacidad_llena_difiere_de_voronoi():
    c = pd.DataFrame([[0.1, 0.3], [0.2, 0.1]], index=["i1", "i2"], columns=["A", "B"])
    tabla = recomendador.comparar_con_voronoi(c, pd.Series({"i1": 100.0, "i2": 50.0}), pd.Series({"A": 80.0}), ["A", "B"])
    assert tabla.set_index("zona").at["i1", "difiere"]


# ---------------------------------------------------------------- recomendador


def test_prueba_de_sentido_meta_bajo_a_remo_sin_hielo():
    """Con San Miguel activo, un pescador del Meta bajo a remo y sin hielo nunca recibe 'por río a Puerto Gaitán'."""
    for temporada in config.TEMPORADAS:
        rec = recomendador.recomendar("P02", "madera_remo", 30, CON_SAN_MIGUEL.con(temporada=temporada), G)
        assert rec.mejor is not None
        assert rec.mejor.tipo != "plaza"
        assert rec.mejor.destino == "CP03"


def test_explicacion_menciona_corriente_y_transbordo():
    rec = recomendador.recomendar("P02", "madera_remo", 30, CON_SAN_MIGUEL, G)
    texto = recomendador.explicar(rec)
    assert "corriente" in texto and "transbordo" in texto
    assert rec.mejor.texto[0].startswith("Por río")
    assert any("Transbordo" in t for t in rec.mejor.texto)


def test_la_mejor_opcion_es_la_de_mas_plata_neta():
    rec = recomendador.recomendar("C01", "madera_motor", 20, CON_SAN_MIGUEL.con(nevera="buena"), G)
    factibles = [o for o in rec.opciones if o.factible]
    assert rec.mejor.neto == max(o.neto for o in factibles)
    assert any(not o.factible and o.motivo for o in rec.opciones)  # La Cristalina: sin acceso por río


def test_esperar_al_comprador_cuando_el_pueblo_no_tiene_frio():
    rec = recomendador.recomendar("P02", "madera_remo", 30, CON_SAN_MIGUEL.con(acopios=frozenset({"CP01"})), G)
    tipos = {o.destino: o.tipo for o in rec.opciones}
    assert tipos["CP03"] == "esperar"


def test_coincide_con_el_laboratorio():
    """La perdida de la opcion plaza (ida por agua y venta) es la misma que calcula el laboratorio sobre ese subgrafo."""
    rec = recomendador.recomendar("C01", "madera_remo", 20, CON_SAN_MIGUEL.con(nevera="deteriorada"), G)
    plaza = next(o for o in rec.opciones if o.tipo == "plaza")
    solo_agua = acopios.grafo_ida(G)
    lab = laboratorio.correr("dijkstra", solo_agua, "C01", "CP01:entra", CON_SAN_MIGUEL.con(nevera="deteriorada", acopios=frozenset()))
    assert plaza.dq == pytest.approx(lab.costo)
