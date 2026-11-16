"""Cada cifra del informe debe estar en outputs/resumen_resultados.md o en la especificacion."""

import re

import pytest

from pesca import config

# Numeros con coma decimal (46,1) o con punto de miles (4.508, 1.332.437), con signo opcional
PATRON = re.compile(r"[−-]?\d{1,3}(?:\.\d{3})+(?:,\d+)?|[−-]?\d+,\d+")


def _valores(texto: str) -> set[float]:
    return {_normalizar(t) for t in PATRON.findall(texto)}


def _normalizar(token: str) -> float:
    signo = -1 if token[0] in "−-" else 1
    return signo * float(token.lstrip("−-").replace(".", "").replace(",", "."))


# El informe y la especificacion son documentos personales: estan en el PC del equipo, no en el repo publico
INFORME = config.DIR_REPO / "docs" / "informe" / "informe.md" if config.DIR_REPO else None
FUENTES = [config.DIR_REPO / "outputs" / "resumen_resultados.md", config.DIR_REPO / "docs" / "ESPECIFICACION.md"] if config.DIR_REPO else []


@pytest.mark.skipif(INFORME is None or not all(p.is_file() for p in [INFORME, *FUENTES]),
                    reason="el informe y la especificacion solo estan en el PC del equipo")
def test_cifras_del_informe_tienen_respaldo():
    informe = INFORME.read_text(encoding="utf-8")
    fuentes = FUENTES
    respaldo = set().union(*(_valores(f.read_text(encoding="utf-8")) for f in fuentes))
    # Un negativo del informe tambien vale si la fuente lo escribe en un intervalo ("a -129,3")
    respaldo |= {-v for v in respaldo}
    huerfanas = sorted({t for t in PATRON.findall(informe) if _normalizar(t) not in respaldo})
    assert not huerfanas, f"Cifras del informe sin respaldo: {huerfanas}"


def test_patron_reconoce_formatos():
    assert _valores("46,1 · 4.508 · $1.332.437 · −129,3 M · 0,63") == {46.1, 4508.0, 1332437.0, -129.3, 0.63}
