"""
Configuración central del proyecto.

Centraliza las rutas de carpetas para que todos los módulos y notebooks
del proyecto referencien los mismos lugares. Todas las rutas se resuelven
a partir de la ubicación de este archivo, por lo que el proyecto puede
moverse de carpeta sin romper las referencias.
"""

from pathlib import Path

# Raíz del proyecto: .../PROYECTO_DESASTRES
RAIZ = Path(__file__).resolve().parents[1]

# --- Carpetas de datos -------------------------------------------------
DATOS_ORIGINALES = RAIZ / "datos" / "originales"
DATOS_PROCESADOS = RAIZ / "datos" / "procesados"
DATOS_GEOGRAFICOS = RAIZ / "datos" / "geograficos"

# Shapefile de límites territoriales (Natural Earth 110m)
MAPA_SHP = DATOS_GEOGRAFICOS / "ne_110m_admin_0_countries"

# Dataset integrado y validado (Actividad 1)
DATASET_INTEGRADO = DATOS_PROCESADOS / "EMDAT_integrado_WDI_validado.csv"

# --- Carpetas de salida ------------------------------------------------
RESULTADOS = RAIZ / "resultados"
RESULTADOS_GRAFICAS = RESULTADOS / "graficas"
RESULTADOS_TABLAS = RESULTADOS / "tablas"

# Aplicación web (Actividad 3 en adelante)
APP = RAIZ / "app"
APP_DATOS = APP / "datos"

# Notebooks y reportes
NOTEBOOKS = RAIZ / "notebooks"
REPORTES = RAIZ / "reportes"


def asegurar_carpetas() -> None:
    """Crea las carpetas de salida del proyecto si no existen."""
    for carpeta in (
        RESULTADOS,
        RESULTADOS_GRAFICAS,
        RESULTADOS_TABLAS,
        APP_DATOS,
    ):
        carpeta.mkdir(parents=True, exist_ok=True)
