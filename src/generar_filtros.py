# -*- coding: utf-8 -*-
"""
generar_filtros.py — Datos para los filtros interactivos (Actividad 4)
---------------------------------------------------------------------
El mapa colorea cada país con un total acumulado. Para poder filtrar por
periodo y por tipo de desastre sin volver a procesar el CSV en el navegador,
genero un archivo con el detalle por país, año y tipo.

Salida: app/datos/filtros.json
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
RUTA_CSV = RAIZ / "datos" / "procesados" / "EMDAT_integrado_WDI_validado.csv"
RUTA_SALIDA = RAIZ / "app" / "datos" / "filtros.json"

# Columnas del dataset que uso para los filtros.
COL_ANIO = "Start Year"
COL_TIPO = "Disaster Type"
COL_ISO = "ISO"
COL_FALLECIDOS = "Total Deaths"
COL_AFECTADOS = "Total Affected"
COL_DANO = "Total Damage, Adjusted ('000 US$)"


def cargar_eventos(ruta: Path = RUTA_CSV) -> pd.DataFrame:
    """Carga el dataset y deja solo las columnas que necesitan los filtros."""
    df = pd.read_csv(ruta, low_memory=False)

    df[COL_ANIO] = pd.to_numeric(df[COL_ANIO], errors="coerce")
    df = df.dropna(subset=[COL_ANIO, COL_ISO, COL_TIPO])

    eventos = pd.DataFrame(
        {
            "anio": df[COL_ANIO].astype(int),
            "iso": df[COL_ISO].astype(str),
            "tipo": df[COL_TIPO].astype(str),
            "fallecidos": pd.to_numeric(df[COL_FALLECIDOS], errors="coerce").fillna(0),
            "afectados": pd.to_numeric(df[COL_AFECTADOS], errors="coerce").fillna(0),
            "dano_usd": pd.to_numeric(df[COL_DANO], errors="coerce").fillna(0) * 1000.0,
        }
    )
    return eventos


def agrupar(eventos: pd.DataFrame) -> pd.DataFrame:
    """Agrupa los eventos por país, año y tipo de desastre."""
    return (
        eventos.groupby(["iso", "anio", "tipo"], as_index=False)
        .agg(
            eventos=("iso", "size"),
            fallecidos=("fallecidos", "sum"),
            afectados=("afectados", "sum"),
            dano_usd=("dano_usd", "sum"),
        )
        .sort_values(["iso", "anio", "tipo"])
    )


def generar(ruta_salida: Path = RUTA_SALIDA) -> Path:
    """Construye filtros.json y devuelve la ruta del archivo escrito."""
    eventos = cargar_eventos()
    tabla = agrupar(eventos)

    datos: dict[str, list[list]] = {}
    for fila in tabla.itertuples(index=False):
        datos.setdefault(fila.iso, []).append(
            [
                int(fila.anio),
                fila.tipo,
                int(fila.eventos),
                int(round(fila.fallecidos)),
                int(round(fila.afectados)),
                float(round(fila.dano_usd, 2)),
            ]
        )

    salida = {
        "periodo": {
            "inicio": int(eventos["anio"].min()),
            "fin": int(eventos["anio"].max()),
        },
        "tipos": sorted(eventos["tipo"].unique().tolist()),
        "datos": datos,
    }

    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    ruta_salida.write_text(
        json.dumps(salida, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    return ruta_salida


def principal() -> None:
    ruta = generar()
    tam_kb = ruta.stat().st_size / 1024
    print(f"Generado {ruta.name}: {tam_kb:.0f} KB")


if __name__ == "__main__":
    principal()
