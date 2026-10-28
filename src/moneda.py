# -*- coding: utf-8 -*-
"""
moneda.py — Conversión del dataset validado a pesos mexicanos
-------------------------------------------------------------
EM-DAT publica los montos en dólares estadounidenses y el Banco Mundial
también entrega el PIB en USD. Como el proyecto trabaja en pesos mexicanos,
este módulo reemplaza esas columnas por su equivalente en MXN y deja el
dataset validado listo para usarse.

Se aplica un tipo de cambio fijo para que las cifras sean reproducibles: no
se busca actualizar el valor histórico de cada año, sino expresar el monto en
la moneda del proyecto.

El archivo se convierte **en el mismo lugar** (sobrescribe la versión
validada). Los datos originales de EM-DAT y del Banco Mundial se conservan en
datos/originales/ por si hace falta revisar algún detalle.

Orden del proceso:
    1. Actividad 1 genera datos/procesados/EMDAT_integrado_WDI_validado.csv
    2. Este módulo lo pasa a pesos mexicanos (mismo archivo)
    3. La capa temática y los filtros leen ese archivo

La conversión es idempotente: si el archivo ya está en MXN no lo vuelve a
multiplicar.

Uso:
    python -m src.moneda
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import DATASET_INTEGRADO, TIPO_CAMBIO_MXN  # noqa: E402

# Columnas monetarias del dataset (todas en USD) y su nombre final en pesos.
# Las columnas "'000 US$" están expresadas en miles de dólares, así que al
# multiplicarlas por el tipo de cambio quedan en miles de pesos.
RENOMBRES = {
    "AID Contribution ('000 US$)": "AID Contribution ('000 MXN)",
    "Reconstruction Costs ('000 US$)": "Reconstruction Costs ('000 MXN)",
    "Reconstruction Costs, Adjusted ('000 US$)": (
        "Reconstruction Costs, Adjusted ('000 MXN)"
    ),
    "Insured Damage ('000 US$)": "Insured Damage ('000 MXN)",
    "Insured Damage, Adjusted ('000 US$)": "Insured Damage, Adjusted ('000 MXN)",
    "Total Damage ('000 US$)": "Total Damage ('000 MXN)",
    "Total Damage, Adjusted ('000 US$)": "Total Damage, Adjusted ('000 MXN)",
    "PIB_USD_corrientes": "PIB_MXN_corrientes",
}

COLUMNAS_USD = list(RENOMBRES.keys())
COLUMNA_CONTROL = "Total Damage, Adjusted ('000 MXN)"


def esta_en_mxn(df: pd.DataFrame) -> bool:
    """Indica si el dataset ya fue convertido a pesos mexicanos."""
    return COLUMNA_CONTROL in df.columns


def convertir(df: pd.DataFrame, tipo_cambio: float = TIPO_CAMBIO_MXN) -> pd.DataFrame:
    """Devuelve una copia del dataset con los montos en pesos mexicanos."""
    if esta_en_mxn(df):
        return df.copy()

    datos = df.copy()
    faltantes = [c for c in COLUMNAS_USD if c not in datos.columns]
    if faltantes:
        raise KeyError(
            "El dataset no tiene las columnas monetarias esperadas: "
            + ", ".join(faltantes)
        )

    for columna in COLUMNAS_USD:
        valores = pd.to_numeric(datos[columna], errors="coerce")
        datos[columna] = (valores * tipo_cambio).round(2)

    return datos.rename(columns=RENOMBRES)


def generar(
    ruta: Path = DATASET_INTEGRADO,
    tipo_cambio: float = TIPO_CAMBIO_MXN,
) -> Path:
    """Convierte el dataset validado a MXN sobrescribiéndolo."""
    df = pd.read_csv(ruta, low_memory=False)

    if esta_en_mxn(df):
        return ruta

    convertido = convertir(df, tipo_cambio)
    convertido.to_csv(ruta, index=False, encoding="utf-8-sig")
    return ruta


def main() -> None:
    ruta = DATASET_INTEGRADO
    antes = pd.read_csv(ruta, nrows=2, low_memory=False)

    if esta_en_mxn(antes):
        print("El dataset ya está en pesos mexicanos; no se modificó.")
        print(f"Archivo: {ruta}")
        return

    print(f"Tipo de cambio aplicado: 1 USD = {TIPO_CAMBIO_MXN} MXN")
    generar(ruta)
    tam_mb = ruta.stat().st_size / (1024 * 1024)
    print(f"Archivo convertido: {ruta}")
    print(f"Tamaño: {tam_mb:.1f} MB")


if __name__ == "__main__":
    main()
