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
        self.assertEqual(len(modulos), 10)
        self.assertTrue((RAIZ / "app" / "modelos" / "modelo_prediccion.json").exists())

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

    def test_actividades_8_a_13(self):
        esperados = [
            "09_actividad8_preparacion_ml.ipynb",
            "10_actividad9_red_neuronal.ipynb",
            "11_actividad10_xgboost.ipynb",
            "12_actividad11_regresion.ipynb",
            "13_actividad12_interpretabilidad.ipynb",
            "14_actividad13_integracion_prediccion.ipynb",
        ]
        for nombre in esperados:
            with self.subTest(nombre):
                self.assertTrue((NOTEBOOKS / nombre).exists(), f"falta {nombre}")

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


class TestModelos(unittest.TestCase):
    """Los modelos de las Actividades 8–13 deben ser consistentes y exportables."""

    MODELO = RAIZ / "app" / "modelos" / "modelo_prediccion.json"
    METRICAS = RAIZ / "modelos" / "metricas.json"

    def test_paquete_exportado(self):
        self.assertTrue(self.MODELO.exists(), "falta app/modelos/modelo_prediccion.json")
        self.assertLess(self.MODELO.stat().st_size, 6 * 1024 * 1024, "el paquete es demasiado grande")
        paquete = json.loads(self.MODELO.read_text(encoding="utf-8"))
        for clave in ("version", "esquema", "catalogo", "clasificacion", "regresion", "metricas", "ejemplos"):
            self.assertIn(clave, paquete)
        self.assertEqual(len(paquete["esquema"]["columnas_xgb"]), 268)
        self.assertGreaterEqual(len(paquete["catalogo"]["paises"]), 150)

    def test_sin_fuga_de_informacion(self):
        paquete = json.loads(self.MODELO.read_text(encoding="utf-8"))
        entradas = paquete["esquema"]["cat_cols"] + paquete["esquema"]["num_cols_modelo"]
        prohibidas = ("death", "affected", "damage", "injured", "aid", "appeal", "declaration")
        fugas = [columna for columna in entradas if any(p in columna.lower() for p in prohibidas)]
        self.assertEqual(fugas, [])

    def test_metricas_coherentes(self):
        metricas = json.loads(self.METRICAS.read_text(encoding="utf-8"))
        clasificacion = metricas["clasificacion"]
        for modelo in ("red_neuronal", "xgboost"):
            prueba = clasificacion[modelo]["prueba"]
            with self.subTest(modelo):
                self.assertGreaterEqual(prueba["roc_auc"], 0.75)
                self.assertGreaterEqual(prueba["pr_auc"], 0.70)
                self.assertGreater(prueba["n"], 500)
                self.assertGreater(prueba["f1"], 0.65)
        for nombre in ("regresion_afectados", "regresion_dano"):
            cobertura = metricas[nombre]["xgboost"]["intervalos"]["prueba"]["cobertura"]
            with self.subTest(nombre):
                self.assertGreaterEqual(cobertura, 0.70)
                self.assertLessEqual(cobertura, 0.90)

    def test_ejemplos_en_rango(self):
        paquete = json.loads(self.MODELO.read_text(encoding="utf-8"))
        clasificacion = paquete["ejemplos"]["clasificacion"]
        self.assertIn(clasificacion["y"], (0, 1))
        for clave in ("prob_nn", "prob_xgb"):
            self.assertGreaterEqual(clasificacion[clave], 0.0)
            self.assertLessEqual(clasificacion[clave], 1.0)
        for nombre in ("afectados", "dano"):
            ejemplo = paquete["ejemplos"][nombre]
            self.assertGreaterEqual(ejemplo["pred_nn"], 0.0)
            self.assertGreaterEqual(ejemplo["pred_xgb"], 0.0)

    def test_inferencia_sin_internet(self):
        js = (RAIZ / "app" / "js" / "prediccion.js").read_text(encoding="utf-8")
        self.assertNotIn("https://", js)
        self.assertNotIn("http://", js)
        self.assertIn("margenArboles", js)
        self.assertIn("salidaRed", js)

    def test_tablas_de_interpretabilidad(self):
        for nombre in ("ablacion_xgb.csv", "equidad_modelos.csv", "estabilidad_temporal.csv"):
            self.assertTrue((RAIZ / "resultados" / "ml" / nombre).exists(), f"falta {nombre}")


class TestInterfaz(unittest.TestCase):
    """La auditoría de la Actividad 6 debe pasar sin errores."""

    def test_recursos_locales(self):
        html = (RAIZ / "app" / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("unpkg.com", html)
        self.assertNotIn("fonts.googleapis.com", html)
        for recurso in (
            "app/vendor/maplibre/maplibre-gl.js",
            "app/vendor/maplibre/maplibre-gl.css",
            "app/vendor/chartjs/chart.umd.js",
            "app/vendor/fuentes/fuentes.css",
        ):
            self.assertTrue((RAIZ / recurso).exists(), f"falta {recurso}")

    def test_entrega_docker(self):
        for archivo in ("Dockerfile", "docker-compose.yml", "docker/nginx.conf", ".dockerignore"):
            self.assertTrue((RAIZ / archivo).exists(), f"falta {archivo}")
        dockerfile = (RAIZ / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("COPY app/", dockerfile)
        self.assertIn("nginx", dockerfile)

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

    def test_pestana_prediccion(self):
        html = (RAIZ / "app" / "index.html").read_text(encoding="utf-8")
        shell = (RAIZ / "app" / "js" / "ui_shell.js").read_text(encoding="utf-8")
        self.assertIn('data-pestana="prediccion"', html)
        self.assertIn('id="vista-prediccion"', html)
        self.assertIn('src="js/prediccion.js"', html)
        self.assertIn('"1", "2", "3", "4", "5"', shell)
        self.assertIn('"prediccion"', shell)

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
