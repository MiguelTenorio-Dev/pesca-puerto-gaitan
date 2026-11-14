import pytest

from pesca import busqueda, red, transporte
from pesca.escenario import Escenario

G = red.construir_red()
BASE = Escenario.base()
ARISTA_RIO = next(d for _, _, d in G.edges(data=True) if d["modo"] == red.CAPA_RIO and d["sentido"] == "aguas_abajo")


def _perfil(embarcacion="madera_motor", **cambios):
    return transporte.Perfil.desde_escenario(BASE.con(**cambios), embarcacion)


def _inversa():
    return {**ARISTA_RIO, "sentido": "aguas_arriba"}


@pytest.mark.parametrize("embarcacion", transporte.embarcaciones())
def test_aguas_abajo_mas_rapido_que_aguas_arriba(embarcacion):
    p = _perfil(embarcacion)
    abajo, arriba = transporte.tiempo_h(ARISTA_RIO, p), transporte.tiempo_h(_inversa(), p)
    assert abajo < arriba


def test_motor_mas_rapido_que_remo():
    for d in (ARISTA_RIO, _inversa()):
        assert transporte.tiempo_h(d, _perfil("madera_motor")) < transporte.tiempo_h(d, _perfil("madera_remo"))
        assert transporte.tiempo_h(d, _perfil("aluminio_motor")) < transporte.tiempo_h(d, _perfil("aluminio_remo"))


def test_remo_en_aguas_altas_no_remonta():
    p = _perfil("madera_remo", temporada="aguas_altas")
    v, motivo = transporte.velocidad_efectiva(_inversa(), p)
    assert v is None
    assert "corriente" in motivo
    assert transporte.tiempo_h(_inversa(), p) is None
    assert transporte.peso(p)("a", "b", _inversa()) is None


def test_aguas_altas_mas_lento_rio_arriba():
    bajas = transporte.tiempo_h(_inversa(), _perfil(temporada="aguas_bajas"))
    altas = transporte.tiempo_h(_inversa(), _perfil(temporada="aguas_altas"))
    assert altas > bajas


def test_hielo_reduce_la_perdida():
    sin = transporte.perdida(ARISTA_RIO, _perfil(hielo_a_bordo=False))
    con = transporte.perdida(ARISTA_RIO, _perfil(hielo_a_bordo=True))
    assert 0 < con < sin


def test_san_miguel_a_puerto_gaitan_por_rio_infactible_a_remo_en_aguas_altas():
    rio = G.edge_subgraph([(u, v) for u, v, d in G.edges(data=True) if d["modo"] == red.CAPA_RIO])
    p = _perfil("madera_remo", temporada="aguas_altas")
    r = busqueda.dijkstra(rio, "A02@rio", "D_MALECON@rio", transporte.peso(p))
    assert not r.alcanzable
    assert "corriente" in transporte.motivo_infactible(rio, "A02@rio", "D_MALECON@rio", p)
    # Con la red completa si llega: por carretera
    completo = busqueda.dijkstra(G, "A02@rio", "D_MALECON@rio", transporte.peso(p))
    assert completo.alcanzable
    assert any(G.edges[u, v]["modo"] == red.CAPA_VIA for u, v in zip(completo.ruta, completo.ruta[1:]))


def test_matriz_origen_acopio():
    m = transporte.matriz_origen_acopio(BASE)
    esperadas = {"origen", "acopio", "embarcacion", "factible", "km", "km_rio", "km_via", "horas", "pct_contra_corriente", "calidad_viaje"}
    assert esperadas <= set(m.columns)
    assert len(m) == m[["origen", "acopio", "embarcacion"]].drop_duplicates().shape[0]
    factibles = m[m["factible"]]
    assert factibles["pct_contra_corriente"].between(0, 100).all()
    assert factibles["calidad_viaje"].between(0, 1).all()
    assert (factibles["km"] >= factibles["km_rio"]).all()


def test_ruta_san_miguel_puerto_gaitan_todo_contra_corriente():
    rio = G.edge_subgraph([(u, v) for u, v, d in G.edges(data=True) if d["modo"] == red.CAPA_RIO])
    p = _perfil("aluminio_motor")
    r = busqueda.dijkstra(rio, "A02@rio", "D_MALECON@rio", transporte.peso(p))
    assert transporte.resumen_ruta(G, r.ruta, p)["pct_contra_corriente"] == pytest.approx(100)


def test_perfil_valida_embarcacion():
    with pytest.raises(ValueError):
        transporte.Perfil("canoa_magica", "comprador_carro", 2.0, 32.0, 32.0)
