"""Comando `pesca-gaitan`: abre la app de Streamlit."""

from __future__ import annotations

import sys

from pesca.config import DIR_APP

RUTA_INICIO = DIR_APP / "Inicio.py"


def main() -> None:
    from streamlit.web import cli as stcli

    sys.argv = ["streamlit", "run", str(RUTA_INICIO), *sys.argv[1:]]
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
