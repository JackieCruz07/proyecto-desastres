"""
Capturas de evidencia de la integración de la interfaz (Actividad 6).

Levanta un servidor estático sobre app/ y usa Playwright para documentar
la interfaz integrada en escritorio y móvil:

    resultados/graficas/integracion_ui/
        01_escritorio_resumen.png
        02_escritorio_filtros.png
        03_escritorio_buscador.png
        04_modal_pais.png
        05_ayuda_atajos.png
        06_movil_mapa.png
        07_movil_panel.png
        08_mexico_estados.png

Uso:
    pip install playwright
    playwright install chromium
    python -m src.capturas_ui
"""

from __future__ import annotations

import asyncio
import functools
import http.server
import socketserver
import sys
import threading
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import APP  # noqa: E402

SALIDA = Path(__file__).resolve().parents[1] / "resultados" / "graficas" / "integracion_ui"
PUERTO = 8014


class ManejadorSilencioso(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):  # noqa: D102
        pass


def iniciar_servidor() -> socketserver.TCPServer:
    manejador = functools.partial(ManejadorSilencioso, directory=str(APP))
    servidor = http.server.ThreadingHTTPServer(("127.0.0.1", PUERTO), manejador)
    servidor.daemon_threads = True
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    return servidor


async def lanzar_navegador(playwright):
    return await playwright.chromium.launch(
        args=[
            "--use-gl=swiftshader",
            "--enable-webgl",
            "--no-sandbox",
            "--disable-setuid-sandbox",
        ]
    )


async def esperar_listo(pagina) -> None:
    await pagina.wait_for_function(
        "window.AtlasUI && window.AtlasUI.estado.listo", timeout=90000
    )
    await pagina.wait_for_timeout(1400)


async def main() -> None:
    from playwright.async_api import async_playwright

    SALIDA.mkdir(parents=True, exist_ok=True)
    servidor = iniciar_servidor()
    url = f"http://127.0.0.1:{PUERTO}/"

    try:
        async with async_playwright() as playwright:
            navegador = await lanzar_navegador(playwright)

            # ------------------------- Escritorio -------------------------
            contexto = await navegador.new_context(
                viewport={"width": 1600, "height": 900}, device_scale_factor=1
            )
            pagina = await contexto.new_page()
            await pagina.goto(url, wait_until="networkidle", timeout=90000)
            await esperar_listo(pagina)

            await pagina.evaluate("window.AtlasUI.seleccionar('MEX')")
            await pagina.wait_for_timeout(1300)
            await pagina.screenshot(path=str(SALIDA / "01_escritorio_resumen.png"))

            await pagina.evaluate("window.AtlasUI.irAPestana('filtros')")
            await pagina.evaluate(
                """() => {
                    const el = document.getElementById('filtro-anio-min');
                    el.value = 2010;
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    const tipo = document.getElementById('selector-tipo');
                    const preferido =
                        Array.from(tipo.options).find((opcion) => opcion.value === 'Flood') ||
                        tipo.options[1];
                    if (preferido) {
                        tipo.value = preferido.value;
                        tipo.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                }"""
            )
            await pagina.wait_for_timeout(1200)
            await pagina.screenshot(path=str(SALIDA / "02_escritorio_filtros.png"))

            await pagina.evaluate("document.getElementById('btn-reset-filtros').click()")
            await pagina.wait_for_timeout(900)
            await pagina.evaluate("window.AtlasUI.irAPestana('resumen')")
            await pagina.fill("#buscador-pais", "jap")
            await pagina.wait_for_timeout(600)
            await pagina.screenshot(path=str(SALIDA / "03_escritorio_buscador.png"))

            await pagina.fill("#buscador-pais", "")
            await pagina.evaluate("window.AtlasApp.abrirPais('MEX')")
            await pagina.wait_for_timeout(1800)
            await pagina.screenshot(path=str(SALIDA / "04_modal_pais.png"))
            await pagina.evaluate("window.AtlasApp.cerrarPais()")
            await pagina.wait_for_timeout(400)

            await pagina.click("#btn-ayuda")
            await pagina.wait_for_timeout(500)
            await pagina.screenshot(path=str(SALIDA / "05_ayuda_atajos.png"))
            await pagina.keyboard.press("Escape")
            await pagina.wait_for_timeout(400)

            await pagina.wait_for_function(
                "document.querySelectorAll('#mexico-mini .mexico-mini__dato').length >= 4",
                timeout=60000,
            )
            await pagina.evaluate("window.AtlasUI.abrirMexico(false)")
            await pagina.wait_for_timeout(2600)
            await pagina.screenshot(path=str(SALIDA / "08_mexico_estados.png"))

            await contexto.close()
            await navegador.close()

            # ---------------------------- Móvil ---------------------------
            # Un navegador nuevo evita reutilizar el contexto WebGL del mapa.
            navegador_movil = await lanzar_navegador(playwright)
            contexto_movil = await navegador_movil.new_context(
                viewport={"width": 390, "height": 844},
                device_scale_factor=1,
                is_mobile=True,
            )
            pagina_movil = await contexto_movil.new_page()
            await pagina_movil.goto(url, wait_until="networkidle", timeout=90000)
            await esperar_listo(pagina_movil)
            await pagina_movil.evaluate("window.AtlasUI.seleccionar('MEX')")
            await pagina_movil.wait_for_timeout(1200)
            await pagina_movil.screenshot(path=str(SALIDA / "06_movil_mapa.png"))

            await pagina_movil.click("#btn-panel-movil")
            await pagina_movil.wait_for_timeout(700)
            await pagina_movil.screenshot(path=str(SALIDA / "07_movil_panel.png"))

            await contexto_movil.close()
            await navegador_movil.close()
    finally:
        servidor.shutdown()
        servidor.server_close()

    print(f"Capturas guardadas en {SALIDA}")
    for ruta in sorted(SALIDA.glob("*.png")):
        print(f"  - {ruta.name}")


if __name__ == "__main__":
    asyncio.run(main())
