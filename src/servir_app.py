"""
Lanzador de la aplicación web (Actividad 3).

Levanta un servidor HTTP local sobre la carpeta app/ y abre el navegador.
Es necesario servirlo por HTTP porque la aplicación carga el GeoJSON con
`fetch`, operación bloqueada en el protocolo file://.

Uso:
    python -m src.servir_app            # puerto 8000
    python -m src.servir_app 8080       # puerto personalizado
    python -m src.servir_app --sin-navegador
"""

from __future__ import annotations

import functools
import http.server
import socketserver
import sys
import threading
import webbrowser
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import APP  # noqa: E402


class Manejador(http.server.SimpleHTTPRequestHandler):
    """Sirve archivos sin registrar cada petición en consola."""

    def log_message(self, *args):
        pass

    def end_headers(self):
        # Evita el almacenamiento en caché al desarrollar.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def main() -> None:
    argumentos = [a for a in sys.argv[1:] if not a.startswith("--")]
    puerto = int(argumentos[0]) if argumentos else 8000
    abrir_navegador = "--sin-navegador" not in sys.argv

    if not (APP / "index.html").exists():
        print("No se encontró app/index.html. Verifica la estructura del proyecto.")
        return

    if not (APP / "datos" / "paises.geojson").exists():
        print(
            "Falta app/datos/paises.geojson.\n"
            "Genera primero la capa temática con:\n"
            "    python -m src.capa_tematica"
        )
        return

    manejador = functools.partial(Manejador, directory=str(APP))
    with socketserver.TCPServer(("127.0.0.1", puerto), manejador) as servidor:
        url = f"http://127.0.0.1:{puerto}/index.html"
        print(f"Atlas Global de Desastres → {url}")
        print("Pulsa Ctrl+C para detener el servidor.")

        if abrir_navegador:
            threading.Timer(0.8, lambda: webbrowser.open(url)).start()

        try:
            servidor.serve_forever()
        except KeyboardInterrupt:
            print("\nServidor detenido.")


if __name__ == "__main__":
    main()
