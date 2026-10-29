"""
Integración de indicadores socioeconómicos por país (Actividad 1).

El enunciado del proyecto pide complementar EM-DAT con datos generales de
los países: población, producto interno bruto (PIB), superficie y otros
indicadores. Este módulo toma los archivos abiertos del Banco Mundial
(World Development Indicators) que están en `datos/originales/`, los
homologa por código ISO de tres letras y construye una tabla por país.

Archivos que usa
----------------
* API_NY.GDP.MKTP.CD_*.csv  → PIB a precios corrientes (USD)
* API_SP.POP.TOTL_*.csv     → población total
* API_AG.SRF.TOTL.K2_*.csv  → superficie total (km²)

La superficie no venía descargada, así que el módulo la baja una sola vez
de la API del Banco Mundial y la guarda con el mismo formato que los otros
dos archivos. Si no hay conexión y el archivo no existe, la superficie
queda vacía y el resto del pipeline sigue funcionando.

Moneda
------
El PIB se convierte a pesos mexicanos con el tipo de cambio fijo del
proyecto (`src.config.TIPO_CAMBIO_MXN`), igual que el resto de los montos.

Uso:
    python -m src.integracion_paises
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

import pandas as pd

# Permite ejecutar el archivo directamente sin instalar el paquete src.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import (  # noqa: E402
    APP_DATOS,
    DATOS_ORIGINALES,
    RESULTADOS_TABLAS,
    TIPO_CAMBIO_MXN,
    asegurar_carpetas,
)

# --- Archivos de entrada -----------------------------------------------
ARCHIVO_PIB = DATOS_ORIGINALES / "API_NY.GDP.MKTP.CD_DS2_EN_csv_v2_20.csv"
ARCHIVO_POBLACION = DATOS_ORIGINALES / "API_SP.POP.TOTL_DS2_EN_csv_v2_26.csv"
ARCHIVO_SUPERFICIE = DATOS_ORIGINALES / "API_AG.SRF.TOTL.K2_DS2_es_csv_v2.csv"

# Indicador del Banco Mundial para la superficie total.
INDICADOR_SUPERFICIE = "AG.SRF.TOTL.K2"

# Año límite: el dataset de desastres llega hasta 2026, pero los
# indicadores del Banco Mundial se publican con retraso.
ANIO_MAXIMO = 2024

# Códigos que EM-DAT y la cartografía escriben distinto al Banco Mundial.
ALIAS_ISO = {
    "PSX": "PSE",  # Estado de Palestina
    "SDS": "SSD",  # Sudán del Sur
}

# Etiquetas legibles para los metadatos del panel.
ETIQUETAS = {
    "poblacion": ("Población total", "habitantes"),
    "superficie_km2": ("Superficie", "km²"),
    "pib_mxn": ("PIB", "MXN"),
    "pib_pc_mxn": ("PIB por habitante", "MXN"),
    "densidad": ("Densidad de población", "hab/km²"),
}


# ---------------------------------------------------------------------------
# 1. LECTURA DE LOS ARCHIVOS DEL BANCO MUNDIAL
# ---------------------------------------------------------------------------

def leer_wdi(ruta: Path) -> pd.DataFrame:
    """Lee un archivo WDI en formato ancho y devuelve el último dato por país.

    El Banco Mundial entrega una columna por año. Para el panel se usa el
    año más reciente con información disponible en cada país.
    """
    if not ruta.exists():
        return pd.DataFrame(columns=["codigo", "nombre_wdi", "valor", "anio"])

    # Los archivos descargados del Banco Mundial traen cuatro líneas de
    # encabezado; el que genera este módulo ya empieza en la tabla.
    with open(ruta, encoding="utf-8-sig") as archivo:
        primera = archivo.readline()

    datos = pd.read_csv(
        ruta,
        skiprows=0 if primera.startswith("Country Name") else 4,
        low_memory=False,
    )
    datos = datos.dropna(axis=1, how="all")
    columnas_anio = [c for c in datos.columns if str(c).isdigit()]
    columnas_anio = [c for c in columnas_anio if int(c) <= ANIO_MAXIMO]

    largo = datos.melt(
        id_vars=["Country Code", "Country Name"],
        value_vars=columnas_anio,
        var_name="anio",
        value_name="valor",
    )
    largo["anio"] = pd.to_numeric(largo["anio"], errors="coerce")
    largo["valor"] = pd.to_numeric(largo["valor"], errors="coerce")
    largo = largo.dropna(subset=["valor", "anio"])

    # Último año con dato por país.
    largo = largo.sort_values("anio").groupby("Country Code", as_index=False).tail(1)

    return largo.rename(
        columns={"Country Code": "codigo", "Country Name": "nombre_wdi"}
    )[["codigo", "nombre_wdi", "valor", "anio"]]


def descargar_superficie(destino: Path = ARCHIVO_SUPERFICIE) -> bool:
    """Descarga la superficie total de los países desde la API del Banco Mundial.

    Guarda el resultado con el mismo formato ancho que los otros archivos
    del WDI para que `leer_wdi` lo procese igual. Devuelve True si el
    archivo quedó disponible.
    """
    if destino.exists():
        return True

    url = (
        "https://api.worldbank.org/v2/country/all/indicator/"
        f"{INDICADOR_SUPERFICIE}?format=json&per_page=20000&date=1960:2024"
    )
    try:
        with urllib.request.urlopen(url, timeout=60) as respuesta:
            carga = json.load(respuesta)
    except Exception as error:  # sin conexión o API caída
        print(f"  Aviso: no se pudo descargar la superficie ({error}).")
        return False

    filas = [
        {
            "Country Name": registro["country"]["value"],
            "Country Code": registro["countryiso3code"],
            "Indicator Name": "Surface area (sq. km)",
            "Indicator Code": INDICADOR_SUPERFICIE,
            "anio": registro["date"],
            "valor": registro["value"],
        }
        for registro in carga[1]
        if registro.get("value") is not None
    ]
    if not filas:
        return False

    largo = pd.DataFrame(filas)
    ancho = largo.pivot_table(
        index=["Country Name", "Country Code", "Indicator Name", "Indicator Code"],
        columns="anio",
        values="valor",
    ).reset_index()
    ancho.columns.name = None
    ancho.to_csv(destino, index=False, encoding="utf-8-sig")
    print(f"  Superficie descargada: {destino.name}")
    return True


# ---------------------------------------------------------------------------
# 2. TABLA SOCIOECONÓMICA POR PAÍS
# ---------------------------------------------------------------------------

def construir_tabla() -> pd.DataFrame:
    """Construye la tabla por país con población, PIB y superficie.

    Devuelve un DataFrame indexado por código ISO de tres letras con las
    columnas que consume la aplicación web.
    """
    pib = leer_wdi(ARCHIVO_PIB).rename(
        columns={"valor": "pib_usd", "anio": "anio_pib"}
    )
    poblacion = leer_wdi(ARCHIVO_POBLACION).rename(
        columns={"valor": "poblacion", "anio": "anio_poblacion"}
    )
    descargar_superficie()
    superficie = leer_wdi(ARCHIVO_SUPERFICIE).rename(
        columns={"valor": "superficie_km2", "anio": "anio_superficie"}
    )

    tabla = pib.merge(
        poblacion[["codigo", "poblacion", "anio_poblacion"]],
        on="codigo",
        how="outer",
    ).merge(
        superficie[["codigo", "superficie_km2", "anio_superficie"]],
        on="codigo",
        how="outer",
    )

    # El PIB se guarda en pesos mexicanos desde el pipeline, nunca en el
    # navegador. La conversión usa el tipo de cambio fijo del proyecto.
    tabla["pib_mxn"] = (tabla["pib_usd"] * TIPO_CAMBIO_MXN).round(0)

    # Indicadores derivados.
    tabla["pib_pc_mxn"] = (
        tabla["pib_mxn"] / tabla["poblacion"].replace(0, pd.NA)
    ).round(0)
    tabla["densidad"] = (
        tabla["poblacion"] / tabla["superficie_km2"].replace(0, pd.NA)
    ).round(1)

    # Año de referencia del bloque socioeconómico (el más reciente).
    tabla["anio_socio"] = tabla[
        ["anio_pib", "anio_poblacion", "anio_superficie"]
    ].max(axis=1)

    tabla = tabla.set_index("codigo")

    # Alias para los códigos que la cartografía escribe distinto.
    for codigo_mapa, codigo_wdi in ALIAS_ISO.items():
        if codigo_wdi in tabla.index and codigo_mapa not in tabla.index:
            tabla.loc[codigo_mapa] = tabla.loc[codigo_wdi]

    return tabla


def integrar_eventos(df: pd.DataFrame, tabla: pd.DataFrame | None = None) -> pd.DataFrame:
    """Agrega las columnas socioeconómicas al dataset de eventos.

    Sirve para dejar la integración documentada dentro del dataset de la
    Actividad 1: cada evento hereda los datos generales de su país.
    """
    if tabla is None:
        tabla = construir_tabla()

    datos = df.copy()
    datos["ISO_norm"] = datos["ISO"].astype(str).str.strip().str.upper()

    columnas = ["poblacion", "superficie_km2", "pib_mxn", "pib_pc_mxn", "densidad"]
    unido = datos.merge(
        tabla[columnas],
        left_on="ISO_norm",
        right_index=True,
        how="left",
    )
    unido = unido.drop(columns=["ISO_norm"])

    return unido.rename(
        columns={
            "poblacion": "Poblacion",
            "superficie_km2": "Superficie_km2",
            "pib_mxn": "PIB_MXN_actual",
            "pib_pc_mxn": "PIB_per_capita_MXN",
            "densidad": "Densidad_hab_km2",
        }
    )


# ---------------------------------------------------------------------------
# 3. EXPORTACIÓN PARA LA APLICACIÓN
# ---------------------------------------------------------------------------

def exportar_json(tabla: pd.DataFrame, ruta: Path | None = None) -> Path:
    """Escribe `app/datos/paises_socio.json` con la tabla por país."""
    if ruta is None:
        ruta = APP_DATOS / "paises_socio.json"

    paises = {}
    for codigo, fila in tabla.iterrows():
        if not isinstance(codigo, str):
            continue
        registro = {
            "poblacion": _numero(fila.get("poblacion")),
            "superficie_km2": _numero(fila.get("superficie_km2")),
            "pib_mxn": _numero(fila.get("pib_mxn")),
            "pib_pc_mxn": _numero(fila.get("pib_pc_mxn")),
            "densidad": _numero(fila.get("densidad")),
            "anio": _numero(fila.get("anio_socio")),
            "nombre_wdi": fila.get("nombre_wdi") if isinstance(fila.get("nombre_wdi"), str) else None,
        }
        if any(registro[k] is not None for k in ("poblacion", "pib_mxn", "superficie_km2")):
            paises[codigo] = registro

    contenido = {
        "fuente": "World Bank — World Development Indicators (WDI)",
        "indicadores": {
            "poblacion": "SP.POP.TOTL",
            "pib_usd": "NY.GDP.MKTP.CD",
            "superficie_km2": "AG.SRF.TOTL.K2",
        },
        "moneda": "MXN",
        "tipo_cambio_usd": TIPO_CAMBIO_MXN,
        "anio_maximo": ANIO_MAXIMO,
        "etiquetas": {k: {"etiqueta": v[0], "unidad": v[1]} for k, v in ETIQUETAS.items()},
        "paises": paises,
    }

    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as archivo:
        json.dump(contenido, archivo, ensure_ascii=False, separators=(",", ":"))

    return ruta


def _numero(valor) -> float | None:
    """Convierte un valor de pandas a número JSON, o None si no existe."""
    if valor is None or pd.isna(valor):
        return None
    return float(valor)


# ---------------------------------------------------------------------------
# 4. EJECUCIÓN
# ---------------------------------------------------------------------------

def main() -> None:
    asegurar_carpetas()

    print("Integrando indicadores del Banco Mundial…")
    tabla = construir_tabla()

    con_pib = int(tabla["pib_mxn"].notna().sum())
    con_poblacion = int(tabla["poblacion"].notna().sum())
    con_superficie = int(tabla["superficie_km2"].notna().sum())
    print(f"  Países con PIB: {con_pib}")
    print(f"  Países con población: {con_poblacion}")
    print(f"  Países con superficie: {con_superficie}")

    ruta_json = exportar_json(tabla)
    print(f"  JSON para la app: {ruta_json}")

    # Evidencia tabular de la integración.
    ruta_tabla = RESULTADOS_TABLAS / "resumen_indicadores_paises.csv"
    tabla.reset_index().rename(columns={"index": "codigo"}).to_csv(
        ruta_tabla, index=False, encoding="utf-8-sig"
    )
    print(f"  Evidencia: {ruta_tabla}")

    print("\nListo. Indicadores socioeconómicos integrados.")


if __name__ == "__main__":
    main()
