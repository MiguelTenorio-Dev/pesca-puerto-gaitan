"""Genera docs/informe/informe.pdf a partir de docs/informe/informe.md.

Uso: python scripts/informe_pdf.py
Necesita la libreria `markdown` (extra dev) y Google Chrome o Chromium para imprimir a PDF.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import markdown

from pesca import config

ORIGEN = config.DIR_REPO / "docs" / "informe" / "informe.md"
DESTINO = ORIGEN.with_suffix(".pdf")

CSS = """
@page { size: A4; margin: 18mm 16mm 18mm 16mm; }
body { font-family: "DejaVu Serif", Georgia, serif; font-size: 10.5pt; line-height: 1.45; color: #1f1f1f; }
h1 { font-size: 18pt; line-height: 1.25; margin: 0 0 6pt; }
h2 { font-size: 14pt; margin: 18pt 0 6pt; border-bottom: 1px solid #bbb; padding-bottom: 2pt; }
h3 { font-size: 12pt; margin: 12pt 0 4pt; }
p, li { text-align: justify; }
blockquote { margin: 8pt 0; padding: 4pt 10pt; border-left: 3px solid #2a78d6; background: #f3f6fb; font-size: 9.5pt; }
table { border-collapse: collapse; margin: 8pt auto; font-size: 9pt; page-break-inside: avoid; }
th, td { border: 1px solid #999; padding: 3pt 6pt; vertical-align: top; }
th { background: #e8eef8; }
code { font-family: "DejaVu Sans Mono", monospace; font-size: 9pt; }
pre { background: #f5f5f5; padding: 6pt; font-size: 8.5pt; white-space: pre-wrap; page-break-inside: avoid; }
img { display: block; max-width: 100%; margin: 8pt auto 2pt; page-break-inside: avoid; }
hr { border: none; border-top: 1px solid #ccc; margin: 12pt 0; }
"""


ITEM = re.compile(r"^\s*(?:[-*]|\d+\.)\s")


def separar_listas(texto: str) -> str:
    """python-markdown exige una linea en blanco antes de una lista (GitHub no): se agrega donde falta."""
    salida = []
    for linea in texto.splitlines():
        previa = salida[-1] if salida else ""
        if ITEM.match(linea) and previa.strip() and not ITEM.match(previa) and not previa.startswith(("  ", ">")):
            salida.append("")
        salida.append(linea)
    return "\n".join(salida)


def main() -> None:
    if not ORIGEN.is_file():
        raise SystemExit(f"No está {ORIGEN}: el informe es un documento personal y no viene en el repositorio")
    chrome = shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chromium-browser")
    if chrome is None:
        raise SystemExit("Hace falta Google Chrome o Chromium para imprimir el PDF")
    cuerpo = markdown.markdown(separar_listas(ORIGEN.read_text(encoding="utf-8")), extensions=["tables", "fenced_code"])
    html = f'<!doctype html><html lang="es"><head><meta charset="utf-8"><style>{CSS}</style></head><body>{cuerpo}</body></html>'
    # El HTML va junto al .md para que las rutas relativas de las figuras funcionen
    with tempfile.NamedTemporaryFile("w", suffix=".html", dir=ORIGEN.parent, delete=False, encoding="utf-8") as f:
        f.write(html)
        temporal = Path(f.name)
    try:
        subprocess.run([chrome, "--headless", "--disable-gpu", "--no-pdf-header-footer", "--allow-file-access-from-files",
                        f"--print-to-pdf={DESTINO}", temporal.as_uri()], check=True, capture_output=True)
    finally:
        temporal.unlink()
    print(f"PDF: {DESTINO}")


if __name__ == "__main__":
    main()
