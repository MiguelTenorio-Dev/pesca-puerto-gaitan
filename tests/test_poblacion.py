import numpy as np
import pytest

from pesca import config, poblacion, red

G = red.construir_red()


def _poblacion(semilla=42, desembarque="D01a"):
    return poblacion.generar_poblacion(np.random.default_rng(semilla), desembarque, G)


@pytest.mark.parametrize("factor", [1.3, 2.0, 3.0])
def test_metas_reproducen_sepec_por_factor(factor):
    with config.sobrescribir({"volumen.factor_subregistro": factor}):
        metas = poblacion.metas_volumen()
        m = poblacion.meses()
    total_sitios = metas[list(poblacion.SITIOS)].sum(axis=1)
    registrado = m["malecon_t"] * (1 + 5.5 / 24.2)
    assert np.allclose(total_sitios, registrado * factor)
    assert total_sitios.sum() == pytest.approx((24.2 + 5.5) * factor)


def test_volumen_de_la_poblacion_igual_a_la_meta():
    for factor in (1.5, 2.0, 2.8):
        with config.sobrescribir({"volumen.factor_subregistro": factor}):
            vol = poblacion.volumen_mensual(_poblacion())
            metas = poblacion.metas_volumen()
        for sitio in poblacion.SITIOS:
            assert np.allclose(vol[sitio], metas[sitio], rtol=1e-9), sitio


def test_un_anio_simulado_cerca_de_la_meta():
    rng = np.random.default_rng(7)
    pob = _poblacion()
    act, dias = poblacion.actividad(), poblacion.meses()["dias"]
    total = 0.0
    for mes in act.index:
        for _ in range(dias[mes]):
            salen = rng.random(len(pob)) < pob["p_faena_pico"] * act[mes]
            total += pob.loc[salen, "kg_por_faena"].sum()
    assert total / 1000 == pytest.approx(poblacion.metas_volumen()[list(poblacion.SITIOS)].to_numpy().sum(), rel=0.10)


def test_sin_subregistro_nadie_va_donde_la_senora():
    with config.sobrescribir({"volumen.factor_subregistro": 1.0}):
        pob = _poblacion()
    assert set(pob["sitio"]) == {"malecon", "san_miguel"}


def test_pescadores_sobre_el_rio_de_su_cuenca():
    nodos = config.cargar_nodos().set_index("id")
    for p in _poblacion().itertuples():
        a = G.nodes[p.ubicacion]
        assert a["capa"] == red.CAPA_RIO
        assert a["cuenca"] == nodos.at[p.zona, "cuenca"]


def test_desembarques_segun_el_sitio():
    pob = _poblacion(desembarque="D01c")
    assert set(pob.loc[pob["sitio"] == "senora", "desembarque"]) == {"D01c"}
    assert set(pob.loc[pob["sitio"] == "malecon", "desembarque"]) == {"D_MALECON"}
    assert set(pob.loc[pob["sitio"] == "vichada", "desembarque"]) <= {"V01", "V02", "A03"}


def test_mezcla_de_embarcaciones():
    with config.sobrescribir({"volumen.factor_subregistro": 3.0, "poblacion.kg_por_faena": 5.0}):
        pob = _poblacion()
    assert len(pob) > 200
    frac = pob["embarcacion"].value_counts(normalize=True)
    for tipo, esperado in config.parametro("flota.mezcla").items():
        assert frac.get(tipo, 0) == pytest.approx(esperado, abs=0.08), tipo


def test_misma_semilla_misma_poblacion():
    assert _poblacion(5).equals(_poblacion(5))
    assert not _poblacion(5).equals(_poblacion(6))
