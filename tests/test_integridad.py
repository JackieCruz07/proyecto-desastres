# -*- coding: utf-8 -*-
"""Pruebas de integridad del proyecto.

Se ejecutan con la biblioteca estándar (unittest) y solo necesitan
beautifulsoup4 para la auditoría de interfaz.

Uso:
    python -m unittest discover -s tests -v
"""

import csv
import json
import subprocess
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DATOS = RAIZ / "app" / "datos"
NOTEBOOKS = RAIZ / "notebooks"


def cargar(nombre):
    return json.loads((DATOS / nombre).read_text(encoding="utf-8"))


class TestDatos(unittest.TestCase):
    """Coherencia entre los archivos que consume la aplicación."""

    def test_json_validos(self):
        for ruta in sorted(DATOS.glob("*.json")):
            with self.subTest(ruta.name):
                json.loads(ruta.read_text(encoding="utf-8"))

    def test_totales_mundiales(self):
        meta = cargar("metadatos.json")
        self.assertEqual(meta["n_eventos"], 10907)
        self.assertEqual(meta["n_territorios"], 175)

    def test_geojson(self):
        geojson = cargar("paises.geojson")
        self.assertEqual(len(geojson["features"]), 175)

    def test_filtros_suman_el_total(self):
        filtros = cargar("filtros.json")
        total = sum(fila[2] for filas in filtros["datos"].values() for fila in filas)
        self.assertEqual(total, 10907)

    def test_mexico_estados(self):
        mexico = cargar("mexico_estados.json")
        self.assertEqual(len(mexico["estados"]), 32)
        self.assertEqual(len(mexico["destacados"]), 4)

    def test_app_completa(self):
        self.assertTrue((RAIZ / "app" / "index.html").exists())
        modulos = sorted((RAIZ / "app" / "js").glob("*.js"))
        self.assertEqual(len(modulos), 9)

    def test_reporte_de_validacion(self):
        ruta = RAIZ / "resultados" / "tablas" / "validacion_resultados.csv"
        self.assertTrue(ruta.exists(), "falta el reporte de la Actividad 7")
        with ruta.open(encoding="utf-8", newline="") as archivo:
            filas = list(csv.DictReader(archivo))
        self.assertGreaterEqual(len(filas), 30)
        pendientes = [f for f in filas if f["resultado"] != "OK"]
        self.assertEqual(pendientes, [], f"comprobaciones por revisar: {pendientes}")


class TestNotebooks(unittest.TestCase):
    """Los notebooks son la evidencia: deben estar ejecutados y sin errores."""

    def test_sin_errores_y_ejecutados(self):
        for ruta in sorted(NOTEBOOKS.glob("*.ipynb")):
            nb = json.loads(ruta.read_text(encoding="utf-8"))
            for celda in nb["cells"]:
                if celda["cell_type"] != "code":
                    continue
                with self.subTest(notebook=ruta.name, celda=celda.get("execution_count")):
                    self.assertIsNotNone(celda.get("execution_count"))
                    for salida in celda.get("outputs", []):
                        self.assertNotEqual(salida.get("output_type"), "error")

    def test_sin_celdas_vacias_al_final(self):
        for ruta in sorted(NOTEBOOKS.glob("*.ipynb")):
            nb = json.loads(ruta.read_text(encoding="utf-8"))
            ultima = nb["cells"][-1]
            with self.subTest(ruta.name):
                self.assertTrue(
                    ultima["cell_type"] != "code" or "".join(ultima["source"]).strip(),
                    "el notebook termina en una celda de código vacía",
                )


class TestInterfaz(unittest.TestCase):
    """La auditoría de la Actividad 6 debe pasar sin errores."""

    def test_mexico_con_relieve(self):
        html = (RAIZ / "app" / "index.html").read_text(encoding="utf-8")
        js = (RAIZ / "app" / "js" / "mexico_estados.js").read_text(encoding="utf-8")
        for control in (
            "mexico-variable-altura",
            "mexico-intensidad",
            "mexico-escala-altura",
            "mexico-escala",
        ):
            self.assertIn(f'id="{control}"', html)
        self.assertIn('id: "estados-relieve"', js)
        self.assertIn('on("style.load"', js)
        self.assertIn("function limpiarIslas", js)
        self.assertIn("estado.geo = limpiarIslas(geo)", js)
        self.assertNotIn("colorDe(", js)

    def test_validar_ui(self):
        resultado = subprocess.run(
            [sys.executable, "-m", "src.validar_ui"],
            cwd=RAIZ,
            capture_output=True,
            text=True,
        )
        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)


if __name__ == "__main__":
    unittest.main()
