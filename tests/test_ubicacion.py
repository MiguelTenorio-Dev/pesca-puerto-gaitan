import numpy as np
import pandas as pd
import pytest

from pesca import asignacion as asg, config, montecarlo, red, ubicacion as ub
from pesca.escenario import Escenario

G = red.construir_red()
BASE = Escenario.base()


# ---------------------------------------------------------------- viabilidad


def test_vpn_a_mano():
    # -100 + 30 × (1/1,1 + 1/1,1² + … + 1/1,1⁵) = -100 + 30 × 3,7908 = 13,72
    assert ub.factor_anualidad(0.10, 5) == pytest.approx(3.7908, abs=1e-4)
    assert ub.vpn(100, 30, 5, 0.10) == pytest.approx(13.72, abs=0.01)


def test_regla_del_70():
    assert ub.vale_la_pena(pd.Series([1, 1, 1, 1, 1, 1, 1, -1, -1, -1]))[0] is True  # 70 %
    assert ub.vale_la_pena(pd.Series([1, 1, 1, 1, 1, 1, -1, -1, -1, -1]))[0] is False  # 60 %


def test_costos_de_los_acopios():
    p = config.parametro
    inversion, operacion, kwh = ub.costos_acopios(frozenset({"A02", "A03"}))
    assert inversion == p("economia.rehabilitacion_san_miguel_cop") + p("economia.rehabilitacion_puente_arimena_cop")
    assert kwh == p("economia.kwh_dia_san_miguel") + p("economia.kwh_dia_puente_arimena")


@pytest.fixture(scope="module")
def viab():
    return ub.viabilidad(n=4)


def test_viabilidad_coherente(viab):
    assert set(viab["acopio"]) == {"A02", "A03", "todos"}
    assert viab.groupby("acopio").size().eq(4).all()
    # La energia resta: sin energia el VPN es mayor o igual
    assert (viab["vpn_sin_energia"] >= viab["vpn"] - 1e-6).all()
    assert (viab["energia_anual"] > 0).all()
    # Activar acopios no empeora el reparto optimo
    assert (viab["costo_evitado_dia"] >= -1).all()
    assert viab["uso_pct"].between(0, 100 + 1e-6).all()


def test_equilibrio_de_la_energia(viab):
    r = ub.resumen_viabilidad(viab).set_index("acopio")
    for acopio, sub in viab.groupby("acopio"):
        cop = r.at[acopio, "equilibrio_cop_kwh"]
        vpn_medio = (sub["vpn_sin_energia"] - cop * sub["vp_energia_por_cop_kwh"]).mean()
        assert vpn_medio == pytest.approx(0, abs=1)


def test_montecarlo_correr_reproducible():
    def f(i, rng):
        return (i, config.parametro("volumen.factor_subregistro"), rng.random())

    a = montecarlo.correr(f, 3, 7)
    assert a == montecarlo.correr(f, 3, 7)
    assert config.parametro("volumen.factor_subregistro") == config.hoja("volumen.factor_subregistro")["valor"]


# ---------------------------------------------------------------- p-mediana


def test_p_mediana_a_mano():
    # 3 demandas en una linea (posiciones 0, 1, 2), candidatos en las mismas posiciones; costo = distancia
    w = pd.Series({"a": 1.0, "b": 1.0, "c": 1.0})
    pos = {"a": 0, "b": 1, "c": 2}
    c = pd.DataFrame({j: {i: abs(pos[i] - pos[j]) for i in pos} for j in pos})
    r = ub.p_mediana(w, c, 1)
    assert r["abiertos"] == ["b"]
    assert r["costo_dia"] == pytest.approx(2)
    r2 = ub.p_mediana(w, c, 2, fijos=("a",))
    assert "a" in r2["abiertos"] and len(r2["abiertos"]) == 2
    with pytest.raises(ValueError):
        ub.p_mediana(w, c, 4)


@pytest.fixture(scope="module")
def reubicacion():
    return ub.reubicar()


def test_ubicaciones_sobre_el_rio(reubicacion):
    for r in reubicacion["resultados"]:
        for j in r["abiertos"]:
            assert G.nodes[j]["capa"] == red.CAPA_RIO


def test_la_perdida_no_aumenta_con_k(reubicacion):
    res = pd.DataFrame(reubicacion["resultados"])
    for modo in ("mover", "agregar"):
        costos = res[res["modo"] == modo].sort_values("p")["costo_dia"].to_list()
        assert all(b <= a + 1e-6 for a, b in zip(costos, costos[1:])), modo
    # Agregar a los 3 de hoy nunca es peor que los 3 de hoy
    assert res[res["modo"] == "agregar"]["costo_dia"].max() <= reubicacion["costo_actuales_dia"] + 1e-6


def test_modo_agregar_mantiene_los_actuales(reubicacion):
    for r in reubicacion["resultados"]:
        if r["modo"] == "agregar":
            # los acopios de hoy que estan sobre el rio (La Cristalina no tiene acceso por rio)
            actuales = ub.actuales_en_rio()
            assert set(actuales) <= set(r["abiertos"])
            assert len(r["abiertos"]) == len(actuales) + r["k"]


def test_propuesta_se_usa_en_el_recomendador(reubicacion):
    propuesta = next(r for r in reubicacion["resultados"] if r["modo"] == "agregar" and r["k"] == 1)
    esc = ub.escenario_con_propuesta(BASE, propuesta["acopios"])
    # La Cristalina (A03) no tiene acceso por rio: la p-mediana sobre el rio no la activa
    assert esc.acopios_nuevos and {"A01", "A02"} <= esc.acopios_activos
    nuevo = next(iter(esc.acopios_nuevos))
    origen = next(i for i, j in propuesta["asignacion"].items() if j == red.clave(nuevo, red.CAPA_RIO))
    rec = asg.recomendar(origen, "madera_motor", 20, esc, "buena")
    opcion = next(o for o in rec.alternativas if o.destino == nuevo)
    assert opcion.factible and opcion.tipo == "acopio" and opcion.bimodal
    assert opcion.ruta[-1] == asg.PLAZA
    r = asg.problema_transporte(esc)
    _, oferta = asg._poblacion_y_oferta(esc)
    assert r["flujos"]["kg_dia"].sum() == pytest.approx(sum(oferta.values()), abs=len(oferta) / asg.ESCALA_KG)


def test_escenario_rechaza_acopio_que_no_es_del_rio():
    with pytest.raises(ValueError):
        BASE.con(acopios_nuevos={"no_existe"})


def test_precalculado_completo():
    datos = ub.cargar_precalculado()
    assert datos is not None, "Corre python scripts/correr_todo.py --solo r4"
    v = datos["viabilidad"]
    assert v.groupby("acopio").size().eq(datos["meta"]["corridas"]).all()
    modos = {(r["modo"], r["p"]) for r in datos["pmediana"]["resultados"]}
    assert ("mover", 3) in modos
    assert {r["k"] for r in datos["pmediana"]["resultados"] if r["modo"] == "agregar"} == set(
        range(1, config.parametro("ubicacion.k_max_agregar") + 1))
