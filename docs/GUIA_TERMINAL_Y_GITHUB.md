# Guía: terminal, GitHub y publicación en Nobara 44

Nobara 44 está basada en Fedora y usa `dnf` para instalar paquetes. Hay dos particularidades:
- **El sistema se actualiza con `nobara-sync`, no con `dnf update`.** El actualizador de Nobara también sincroniza sus repositorios y aplica ajustes propios.
- **El `python3` del sistema es Python 3.14.** Para el proyecto usamos **Python 3.12**, que Fedora ofrece como paquete aparte. Así quedamos con la misma versión que en Streamlit Community Cloud y con máxima compatibilidad de librerías. El `python3` del sistema no se toca nunca.

---

## 1. Qué vas a tener en la terminal

| herramienta | para qué sirve | comprobar |
|---|---|---|
| **Claude Code** | Escribe el código, corre los tests y hace los commits | `claude --version` |
| **Python 3.12** | Lenguaje del motor y de la app | `python3.12 --version` |
| **Git** | Guarda el historial de versiones | `git --version` |
| **GitHub CLI (`gh`)** | Crea el repo y sube todo desde la terminal | `gh --version` |
| `.venv` (en el proyecto) | Entorno aislado con las librerías del proyecto | se crea en la Fase 0 |
| Streamlit (dentro de `.venv`) | Servidor de la app web | `streamlit --version` |

**Cómo se trabaja:** dos pestañas de terminal abiertas en la carpeta del proyecto. En Konsole, `Ctrl+Shift+T` abre una pestaña nueva.
- **Pestaña 1:** `claude`. Ahí le pides cosas y apruebas lo que propone.
- **Pestaña 2:** la app corriendo (`pesca-gaitan`), visible en el navegador en `http://localhost:8501`. Cuando Claude cambia el código, recargas la página.

---

## 2. Instalar lo que falte (una sola vez)

```bash
# 1. Actualizar el sistema a la manera de Nobara
nobara-sync cli

# 2. Instalar Git, GitHub CLI y Python 3.12
sudo dnf install git gh python3.12

# 3. Comprobar
git --version
gh --version
python3.12 --version
claude --version
```

**Reglas para no dañar el sistema:**
- Nunca uses `sudo pip install`. Todo lo de Python se instala **dentro** del `.venv` del proyecto.
- No cambies a qué apunta `python3` (ni con `alternatives` ni con enlaces). Nobara y Fedora dependen de él.
- Si `nobara-sync` falla por conflictos: `nobara-sync repair`.

**Configurar Git y conectar GitHub:**
```bash
git config --global user.name "Tu Nombre"
git config --global user.email "el-correo-de-tu-cuenta-de-github"
gh auth login
```
`gh auth login` hace unas preguntas: elige GitHub.com → HTTPS → "Login with a web browser". Copia el código que te muestra y autoriza en el navegador.

---

## 3. Crear el repo público y subir el proyecto (una sola vez)

Descomprime el proyecto y entra a la carpeta:
```bash
cd ~/ruta/donde/lo/pusiste/pesca-puerto-gaitan
git init -b main
git add -A
git commit -m "fase 0: documentos del proyecto y distancias medidas"
gh repo create pesca-puerto-gaitan --public --source=. --remote=origin --push --description "Transporte y cadena de frío para pescadores de Puerto Gaitán (Meta): diagnóstico y optimización con grafos"
```
Con eso queda en `https://github.com/<tu-usuario>/pesca-puerto-gaitan`.

**Después de cada fase:**
```bash
git add -A
git commit -m "fase N: lo que se hizo"
git push
```
O le dices a Claude Code "haz commit y push de la fase N", y apruebas los comandos.

---

## 4. Entorno virtual y app en local (desde la Fase 0)

```bash
python3.12 -m venv .venv
source .venv/bin/activate          # el prompt muestra (.venv)
pip install --upgrade pip
pip install -e ".[dev]"
pesca-gaitan                       # o: streamlit run src/pesca/app/Inicio.py
```
- Cada vez que abras una pestaña nueva: `source .venv/bin/activate`.
- Si alguna librería intenta compilar y falla (raro, casi todas traen binarios listos): `sudo dnf install python3.12-devel gcc`.

---

## 5. Publicar la app con un link (desde la Fase 2)

Streamlit Community Cloud es gratis para apps públicas y se actualiza con cada `git push`.

1. Abre **share.streamlit.io** e inicia sesión con tu cuenta de GitHub. Autoriza a Streamlit.
2. **Create app** → desplegar desde GitHub.
3. Repository: `<tu-usuario>/pesca-puerto-gaitan` · Branch: `main` · Main file path: `src/pesca/app/Inicio.py`.
4. En *Advanced settings* elige **Python 3.12**, la misma versión que en local. Si quieres, ponle un subdominio como `pesca-gaitan`.
5. **Deploy.** Si falla, copia el log y pégaselo a Claude Code.

La app se "duerme" si nadie la usa por varias horas. Ábrela unos minutos antes de presentar.

---

## 6. Que cualquiera pueda instalarlo desde GitHub (Fase 7)

```bash
pip install git+https://github.com/<tu-usuario>/pesca-puerto-gaitan
pesca-gaitan
```
Claude Code lo deja listo en la Fase 0: un `pyproject.toml` con el comando `pesca-gaitan`, y los datos y la app dentro del paquete.

**Versión estable para la entrega:**
```bash
git tag v1.0
git push --tags
gh release create v1.0 --title "v1.0 – Entrega" --notes "Versión entregada el 15 de noviembre de 2026"
```

---

## 7. Checklist de repo público

- [ ] `LICENSE` (MIT).
- [ ] README con link a la app, captura, instalación, qué datos son medidos y cuáles simulados, limitaciones y créditos.
- [ ] Nada de `.venv/`, contraseñas ni claves (el `.gitignore` lo cubre).
- [ ] Sin datos personales de pescadores: ni nombres, ni teléfonos, ni ubicación de viviendas.
- [ ] Las capturas de Google Earth en `docs/evidencias/` conservan visible la atribución de Google.
