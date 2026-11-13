# Pesca en Puerto Gaitán: transporte y cadena de frío

Proyecto universitario de ingeniería. Diagnostica cuánto valor pierde el pescado entre la captura y la venta en Puerto Gaitán (Meta) y propone rutas, acopios, rutas bimodales río + carretera y cadena de frío con grafos y optimización. Incluye una app web en Streamlit con un recomendador para pescadores.

## Instalar y abrir (Python 3.12)

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pesca-gaitan            # abre la app
pytest -q               # corre las pruebas
```

Para instalarlo directamente desde GitHub: `pip install git+https://github.com/<usuario>/pesca-puerto-gaitan`

## Documentos

- [Especificación](docs/ESPECIFICACION.md): la fuente de verdad.
- [Plan de trabajo](docs/PLAN_DE_TRABAJO.md): fases y registro de decisiones.

Los datos marcados **[SIMULADO]** son supuestos del proyecto y la app los muestra con esa etiqueta. Las coordenadas con `validado = no` son aproximadas.

Licencia MIT.
