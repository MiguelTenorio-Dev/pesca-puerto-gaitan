import pytest

from pesca import config
from pesca.escenario import Escenario


def test_base_valido():
    e = Escenario.base()
    assert e.acopios_activos == frozenset({"A01"})
    assert e.desembarque_senora == "D01a"
    assert e.semilla == config.parametro("general.semilla")


def test_hashable():
    e = Escenario.base()
    assert hash(e) == hash(Escenario.base())
    assert len({e, Escenario.base()}) == 1


def test_con_no_muta_el_original():
    e = Escenario.base()
    e2 = e.con(acopios_activos={"A01", "A02"})
    assert e.acopios_activos == frozenset({"A01"})
    assert e2.acopios_activos == frozenset({"A01", "A02"})
    assert isinstance(e2.acopios_activos, frozenset)


@pytest.mark.parametrize(
    "cambios",
    [
        {"acopios_activos": {"A99"}},
        {"acopios_activos": set()},
        {"desembarque_senora": "A01"},
        {"temporada": "verano"},
    ],
)
def test_valores_invalidos(cambios):
    with pytest.raises(ValueError):
        Escenario.base().con(**cambios)


def test_corriente_segun_temporada():
    e = Escenario.base()
    bajas = e.con(temporada="aguas_bajas").corriente_kmh()
    altas = e.con(temporada="aguas_altas").corriente_kmh()
    assert altas > bajas > 0
