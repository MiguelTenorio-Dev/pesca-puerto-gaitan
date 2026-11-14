import pytest

from pesca.degradacion import rrs


def test_rrs_en_hielo_es_uno():
    assert rrs(0) == pytest.approx(1.0)


def test_rrs_congelado_es_cero():
    assert rrs(-18) == 0.0


def test_rrs_crece_con_la_temperatura():
    assert rrs(4) < rrs(32) < rrs(38)
