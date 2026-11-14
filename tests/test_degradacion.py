import pytest

from pesca import config
from pesca import degradacion as dg
from pesca.degradacion import rrs


def test_rrs_en_hielo_es_uno():
    assert rrs(0) == pytest.approx(1.0)


def test_rrs_congelado_es_cero():
    assert rrs(-18) == 0.0


def test_rrs_crece_con_la_temperatura():
    assert rrs(4) < rrs(32) < rrs(38)


def test_calidad_decrece_con_las_horas():
    calidades = []
    for horas in (0, 2, 6, 12):
        lote = dg.Lote(kg=10)
        dg.avanzar(lote, horas, "rio", dg.AMBIENTE)
        calidades.append(dg.calidad(lote))
    assert calidades == sorted(calidades, reverse=True)
    assert calidades[0] == 1.0


def test_el_hielo_se_gasta_antes_de_pasar_a_ambiente():
    vu0 = config.parametro("degradacion.vu0_h")
    lote = dg.Lote(kg=10, hielo_restante_h=5)
    dg.avanzar(lote, 8, "rio", dg.ICOPOR_HIELO)
    assert lote.hielo_restante_h == 0
    assert lote.perdida["rio"] == pytest.approx((5 * rrs(4) + 3 * rrs(32)) / vu0)


def test_congelado_no_pierde_y_la_falla_si():
    lote = dg.Lote(kg=10)
    dg.congelar(lote)
    dg.avanzar(lote, 200, "espera", dg.CONGELADO)
    assert lote.perdida["espera"] == 0
    dg.avanzar(lote, 3, "espera", dg.FALLA)
    assert lote.perdida["espera"] > 0


def test_factor_de_precio_escalonado():
    assert [dg.factor_precio(q) for q in (1.0, 0.75, 0.6, 0.3, 0.1)] == [1.0, 1.0, 0.7, 0.4, 0.0]


def test_castigo_por_congelacion_una_sola_vez():
    lote = dg.Lote(kg=10)
    dg.congelar(lote)
    dg.congelar(lote)
    v = dg.valor_lote(lote, precio=1000)
    assert v["cop_recibido"] == pytest.approx(10 * 1000 * config.parametro("degradacion.factor_precio_congelado"))


@pytest.mark.parametrize("congelado", [False, True])
def test_perdida_por_etapa_suma_el_total(congelado):
    lote = dg.Lote(kg=15, hielo_restante_h=6)
    dg.avanzar(lote, 4, "faena", dg.ICOPOR_HIELO)
    dg.avanzar(lote, 5, "rio", dg.ICOPOR_HIELO)
    if congelado:
        dg.congelar(lote)
        dg.avanzar(lote, 2, "espera", dg.FALLA)
    dg.avanzar(lote, 1, "carretera", dg.AMBIENTE)
    v = dg.valor_lote(lote)
    assert sum(v[f"cop_{e}"] for e in dg.ETAPAS_COP) == pytest.approx(v["cop_perdido"])
    assert sum(v[f"perdida_{e}"] for e in dg.ETAPAS) == pytest.approx(dg.perdida_total(lote))
    assert v["cop_recibido"] + v["cop_perdido"] == pytest.approx(v["cop_posible"])


def test_lote_que_no_llega_se_pierde_en_el_rio():
    lote = dg.Lote(kg=10, no_llego=True)
    v = dg.valor_lote(lote, precio=1000)
    assert v["cop_recibido"] == 0
    assert v["cop_rio"] == pytest.approx(10_000)


def test_precio_base():
    assert dg.precio_base() == pytest.approx((0.5 * 11833 + 0.5 * 14000) * 0.8)


def test_ejemplo_pescador_meta_bajo():
    # Plan de la Fase 2, §7: madera a remo, nevera deteriorada, 20 kg, señora en la boca del Manacacias
    lote = dg.Lote(kg=20, hielo_restante_h=12)
    dg.avanzar(lote, 4, "faena", dg.ICOPOR_HIELO)
    dg.avanzar(lote, 11.4, "rio", dg.ICOPOR_HIELO)
    dg.congelar(lote)
    dg.avanzar(lote, 3, "espera", dg.FALLA)  # corte de 9 h, el congelador aguanta 6
    dg.avanzar(lote, 0.91, "carretera", dg.AMBIENTE)
    assert dg.perdida_total(lote) == pytest.approx(0.424, rel=1e-2)
    v = dg.valor_lote(lote)
    assert v["calidad"] == pytest.approx(0.576, rel=1e-2)
    assert v["cop_perdido"] == pytest.approx(83_700, rel=1e-2)
    assert v["cop_espera"] + v["cop_congelacion_lenta"] > v["cop_rio"]
