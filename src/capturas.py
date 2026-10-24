"""
Capturas de pantalla de la aplicación web (Actividad 3).

Levanta un servidor estático sobre la carpeta app/ y controla un navegador
(Playwright) para generar las imágenes que documentan la capa temática:

    resultados/graficas/capa_tematica/*.png

Escenas capturadas
------------------
1. globo_eventos          Mapa de calor global (variable: eventos).
2. globo_elevacion        Elevación por fallecidos.
3. globo_deformacion      Deformación de la superficie por afectados.
4. globo_dano             Coloración por daño económico ajustado.
5. plano_mexico           Vista plana con México seleccionado.
6. combinado              Color = eventos, elevación = fallecidos.

Uso:
    pip install playwright
    playwright install chromium
    python -m src.capturas
"""

from __future__ import annotations

import functools
import http.server
import socketserver
import sys
import threading
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import APP, RESULTADOS_GRAFICAS  # noqa: E402

CARPETA_SALIDA = RESULTADOS_GRAFICAS / "capa_tematica"
ANCHO, ALTO = 1600, 950
PUERTO = 8765


# ---------------------------------------------------------------------------
# Servidor estático
# ---------------------------------------------------------------------------

class ServidorSilencioso(http.server.SimpleHTTPRequestHandler):
    """Servidor HTTP que no imprime cada petición en consola."""

    def log_message(self, *args):  # noqa: D401
        pass


def iniciar_servidor(carpeta: Path) -> socketserver.TCPServer:
    manejador = functools.partial(ServidorSilencioso, directory=str(carpeta))
    servidor = socketserver.TCPServer(("127.0.0.1", PUERTO), manejador)
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    return servidor


# ---------------------------------------------------------------------------
# Escenas
# ---------------------------------------------------------------------------

# Cada escena define los controles a fijar y el encuadre de la cámara.
ESCENAS = [
    {
        "nombre": "01_globo_eventos",
        "descripcion": "Mapa de calor global por número de desastres.",
        "color": "eventos",
        "altura": "eventos",
        "recurso": "ninguno",
        "escala": "auto",
        "camara": {"center": [-30, 20], "zoom": 1.3, "pitch": 30, "bearing": 0},
    },
    {
        "nombre": "02_globo_elevacion",
        "descripcion": "Elevación de los territorios según los fallecidos.",
        "color": "eventos",
        "altura": "fallecidos",
        "recurso": "elevacion",
        "escala": "log",
        "camara": {"center": [10, 25], "zoom": 1.6, "pitch": 50, "bearing": -10},
    },
    {
        "nombre": "03_globo_deformacion",
        "descripcion": "Deformación de la superficie según personas afectadas.",
        "color": "afectados",
        "altura": "afectados",
        "recurso": "deformacion",
        "escala": "log",
        "camara": {"center": [20, 20], "zoom": 1.7, "pitch": 45, "bearing": 5},
    },
    {
        "nombre": "04_globo_dano_economico",
        "descripcion": "Coloración por daño económico ajustado.",
        "color": "dano_ajustado",
        "altura": "dano_ajustado",
        "recurso": "elevacion",
        "escala": "log",
        "camara": {"center": [-60, 25], "zoom": 1.5, "pitch": 40, "bearing": 0},
    },
    {
        "nombre": "05_combinado_eventos_fallecidos",
        "descripcion": "Color = eventos, elevación = fallecidos.",
        "color": "eventos",
        "altura": "fallecidos",
        "recurso": "elevacion",
        "escala": "log",
        "camara": {"center": [15, 30], "zoom": 1.8, "pitch": 55, "bearing": -15},
    },
    {
        "nombre": "06_plano_mexico",
        "descripcion": "Vista plana con México seleccionado.",
        "color": "eventos",
        "altura": "afectados",
        "recurso": "deformacion",
        "escala": "log",
        "proyeccion": "plano",
        "seleccion": "MEX",
        "camara": {"center": [-102, 23], "zoom": 3.4, "pitch": 55, "bearing": 0},
    },
]


def aplicar_escena(pagina, escena: dict) -> None:
    """Fija los controles de la interfaz y encuadra la cámara."""
    pagina.evaluate(
        """
        (escena) => {
          const col = document.getElementById('selector-color');
          const alt = document.getElementById('selector-elevacion');
          const esc = document.getElementById('selector-escala');

          col.value = escena.color;
          col.dispatchEvent(new Event('change'));
          alt.value = escena.altura;
          alt.dispatchEvent(new Event('change'));
          esc.value = escena.escala;
          esc.dispatchEvent(new Event('change'));

          const boton = document.querySelector(
            '.segmento[data-recurso="' + escena.recurso + '"]'
          );
          if (boton) boton.click();

          if (escena.proyeccion === 'plano') {
            document.getElementById('btn-plano').click();
          } else {
            document.getElementById('btn-globo').click();
          }
        }
        """,
        escena,
    )

    if escena.get("seleccion"):
        pagina.evaluate("(codigo) => window.CapaTematica.setSeleccionado(codigo)",
                        escena["seleccion"])

    camara = escena["camara"]
    pagina.evaluate(
        """
        (camara) => {
          const mapa = window.__mapa && window.__mapa();
          if (mapa) mapa.jumpTo(camara);
        }
        """,
        camara,
    )


def main() -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "Playwright no está instalado.\n"
            "Instálalo con:  pip install playwright\n"
            "                 playwright install chromium"
        )
        return

    CARPETA_SALIDA.mkdir(parents=True, exist_ok=True)
    servidor = iniciar_servidor(APP)
    print(f"Servidor en http://127.0.0.1:{PUERTO}")

    try:
        with sync_playwright() as p:
            navegador = p.chromium.launch()
            pagina = navegador.new_page(viewport={"width": ANCHO, "height": ALTO})

            pagina.goto(f"http://127.0.0.1:{PUERTO}/index.html")
            pagina.wait_for_function(
                "() => document.getElementById('estado-texto')"
                ".textContent.includes('lista')",
                timeout=60000,
            )
            pagina.wait_for_timeout(3000)

            for escena in ESCENAS:
                print(f"  · {escena['nombre']}: {escena['descripcion']}")
                aplicar_escena(pagina, escena)
                pagina.wait_for_timeout(2500)
                destino = CARPETA_SALIDA / f"{escena['nombre']}.png"
                pagina.screenshot(path=str(destino))
                print(f"    guardado → {destino}")

            navegador.close()
    finally:
        servidor.shutdown()

    print("\nCapturas completadas.")


if __name__ == "__main__":
    main()
