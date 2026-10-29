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

# --- Moneda ------------------------------------------------------------
# Tipo de cambio fijo con el que se convirtió el dataset a pesos mexicanos.
# Se fija para que las cifras sean reproducibles entre ejecuciones.
TIPO_CAMBIO_MXN = 20.8

# Dataset integrado y validado (Actividad 1). Se guarda ya en pesos
# mexicanos: src/moneda.py reemplaza ahí las columnas monetarias de USD a
# MXN. Los datos originales de EM-DAT y del Banco Mundial quedan intactos en
# DATOS_ORIGINALES.
DATASET_INTEGRADO = DATOS_PROCESADOS / "EMDAT_integrado_WDI_validado.csv"

# --- Fuentes externas (Actividad 1) ------------------------------------
# Indicadores socioeconómicos del Banco Mundial (WDI).
WDI_PIB = DATOS_ORIGINALES / "API_NY.GDP.MKTP.CD_DS2_EN_csv_v2_20.csv"
WDI_POBLACION = DATOS_ORIGINALES / "API_SP.POP.TOTL_DS2_EN_csv_v2_26.csv"
WDI_SUPERFICIE = DATOS_ORIGINALES / "API_AG.SRF.TOTL.K2_DS2_es_csv_v2.csv"

# Series de contexto de Our World in Data.
OWID_IMPACTO = DATOS_ORIGINALES / "natural-disasters-by-yearly-impact.csv"
OWID_AFECTADOS = DATOS_ORIGINALES / "natural-disasters-people-affected.csv"

# Datos de México (CONAFOR).
CONAFOR_HISTORICO = DATOS_ORIGINALES / "estadisticasincendiosforestales2015-2024.csv"
CONAFOR_2025 = DATOS_ORIGINALES / "2025_Incendios_forestales.csv"

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
