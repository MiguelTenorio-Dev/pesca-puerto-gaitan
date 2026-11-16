import pytest

from pesca import asignacion as asg
from pesca import cadena_actual, comparacion, config
from pesca import degradacion as dg
from pesca.escenario import Escenario

BASE = Escenario.base()
POB = cadena_actual.corrida_ejemplo(BASE).poblacion


@pytest.fixture(scope="module")
def resultado():
    return comparacion.comparar(BASE, POB)


def test_una_fila_por_pescador(resultado):
    tabla = resultado["tabla"]
    assert tabla["pescador"].is_unique
    assert set(tabla["pescador"]) == set(POB["id"])


def test_hoy_coincide_con_el_costo_de_hoy_de_r3(resultado):
    tabla = resultado["tabla"]
    costo = (tabla["kg_dia"] * dg.precio_base() - tabla["neto_dia_hoy"]).sum()
    assert costo == pytest.approx(asg.costo_hoy(BASE, POB), rel=1e-9)


def test_propuesta_coincide_con_el_reparto_optimo(resultado):
    tabla = resultado["tabla"]
    costo = (tabla["kg_dia"] * dg.precio_base() - tabla["neto_dia_propuesta"]).sum()
    optimo = asg.problema_transporte(comparacion.escenario_propuesta(BASE), POB, con_hoy=False)["costo_optimo_dia"]
    assert costo == pytest.approx(optimo, rel=1e-3)  # el reparto va en decimas de kg


def test_totales_son_la_suma_de_las_filas(resultado):
    tabla = resultado["tabla"]
    tot = comparacion.totales(tabla)
    for lado in comparacion.LADOS:
        assert tot.at["neto_dia", lado] == pytest.approx(tabla[f"neto_dia_{lado}"].sum())
        assert tot.at["kg_perdidos_dia", lado] == pytest.approx(tabla[f"kg_perdidos_dia_{lado}"].sum())
    assert (tot["diferencia"] == tot["propuesta"] - tot["hoy"]).all()


def test_la_flota_no_pierde_plata_con_la_propuesta(resultado):
    # El reparto optimo minimiza perdida + viaje de toda la flota: en total nunca queda peor que hoy
    tot = comparacion.totales(resultado["tabla"])
    assert tot.at["neto_dia", "diferencia"] >= 0
    assert tot.at["kg_perdidos_dia", "diferencia"] <= 0


def test_partes_de_la_mejora_suman():
    p = comparacion.partes_de_la_mejora(100.0, 30.0)
    assert p["recomendador"] + p["inversion"] == p["total"] == 100.0
    d = comparacion.descomponer_mejora(500.0, 300.0, 50.0)
    assert d == {"recomendador": 200.0, "inversion": 50.0, "total": 250.0}


def test_propuesta_viene_del_yaml():
    assert comparacion.portafolio_propuesta() == frozenset(config.parametro("propuesta.portafolio"))
    esc = comparacion.escenario_propuesta(BASE)
    assert "A02" in esc.acopios_activos and esc.acopios_nuevos


@pytest.fixture(scope="module")
def cart():
    return comparacion.cartilla(BASE)


def test_cartilla_completa(cart):
    nodos = config.cargar_nodos()
    zonas = nodos["tipo"].isin(["zona_pesca", "comunidad"]).sum()
    assert len(cart) == zonas * len(comparacion.TEXTO_BOTE) * len(comparacion.TEMPORADAS)
    assert not cart.duplicated(["zona", "temporada", "bote"]).any()


def test_cartilla_dice_lo_mismo_que_el_recomendador(cart):
    esc = comparacion.escenario_propuesta(BASE)
    fila = cart[(cart["zona"] == "P02") & (cart["bote"] == comparacion.TEXTO_BOTE["madera_remo"])
                & (cart["temporada"] == comparacion.TEXTO_TEMPORADA[BASE.temporada])].iloc[0]
    rec = asg.recomendar("P02@rio", "madera_remo", config.parametro("poblacion.kg_por_faena"), esc,
                         config.parametro("propuesta.nevera_cartilla"))
    assert fila["lleva_a"] == rec.mejor.nombre
    assert fila["te_quedan_cop"] == pytest.approx(rec.mejor.cop_neto)


def test_pdf_una_pagina_por_zona(cart):
    pdf = comparacion.cartilla_pdf(cart)
    assert pdf.startswith(b"%PDF")
    assert pdf.count(b"/Type /Page\n") + pdf.count(b"/Type /Page ") >= 1
    assert pdf.count(b"/Type /Page") - pdf.count(b"/Type /Pages") == cart["zona"].nunique()


def test_resumen_completo_y_sin_nan():
    if comparacion.cargar_precalculado() is None:
        pytest.skip("Falta el precalculado de R6")
    texto = comparacion.texto_resumen()
    for seccion in ("## R1", "## R2", "## R3", "## R4", "## R5", "## R6"):
        assert seccion in texto
    assert "nan" not in texto.lower()
