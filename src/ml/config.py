"""Configuración común de las actividades de machine learning (8–13).

Todas las rutas se resuelven desde la raíz del proyecto para que los
notebooks y los scripts produzcan exactamente los mismos archivos.
"""

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]

DATOS_PROCESADOS = RAIZ / "datos" / "procesados"
DATASET = DATOS_PROCESADOS / "EMDAT_integrado_WDI_validado.csv"
SOCIO = RAIZ / "app" / "datos" / "paises_socio.json"
GEOJSON_PAISES = RAIZ / "app" / "datos" / "paises.geojson"

MODELOS = RAIZ / "modelos"
MODELOS_APP = RAIZ / "app" / "modelos"
RESULTADOS_ML = RAIZ / "resultados" / "ml"
GRAFICAS_ML = RAIZ / "resultados" / "graficas" / "ml"
TABLAS_ML = RAIZ / "resultados" / "tablas"

SEMILLA = 42

# Partición temporal. El conjunto de prueba no se usa para ajustar nada.
ANIO_ENTRENAMIENTO_FIN = 2022
ANIO_VALIDACION = 2023
ANIO_PRUEBA_INICIO = 2024
ANIO_PRUEBA_FIN = 2025

# Columnas categóricas y numéricas que entran al modelo. Todas se conocen
# al inicio del evento: no se usan fallecidos, afectados ni daños.
CAT_COLS = [
    "tipo",
    "subtipo",
    "subgrupo",
    "region",
    "subregion",
    "iso",
    "escala",
]

NUM_COLS = [
    "pib_pc_log",
    "poblacion_log",
    "densidad_log",
    "mes_sin",
    "mes_cos",
    "duracion_log",
    "magnitud_faltante",
    "mes_faltante",
    "duracion_faltante",
    "pib_faltante",
]

# Se agrega en el preprocesador porque necesita las medias por escala.
NUM_COLS_MODELO = NUM_COLS + ["magnitud_z"]

# Frecuencia mínima por categoría. Las categorías raras se agrupan en OTRO.
MIN_FRECUENCIA = {
    "tipo": 20,
    "subtipo": 20,
    "subgrupo": 20,
    "region": 10,
    "subregion": 20,
    "iso": 5,
    "escala": 10,
}

# Etiquetas legibles para la aplicación y los reportes.
ETIQUETAS = {
    "tipo": "Tipo de desastre",
    "subtipo": "Subtipo",
    "subgrupo": "Subgrupo",
    "region": "Región",
    "subregion": "Subregión",
    "iso": "País",
    "escala": "Escala de magnitud",
    "pib_pc_log": "PIB per cápita",
    "poblacion_log": "Población",
    "densidad_log": "Densidad de población",
    "mes_sin": "Estacionalidad (seno)",
    "mes_cos": "Estacionalidad (coseno)",
    "duracion_log": "Duración del evento",
    "magnitud_z": "Magnitud típica",
    "magnitud_faltante": "Magnitud no reportada",
    "mes_faltante": "Mes no reportado",
    "duracion_faltante": "Duración no reportada",
    "pib_faltante": "PIB no disponible",
}

MESES = [
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
]
