"""
Contexto externo de Our World in Data (OWID).

OWID publica series de desastres construidas a partir de EM-DAT, pero con
un criterio de agregación distinto. Sirven como referencia independiente:
si el orden de magnitud de un país coincide, la integración va bien.

Se usan dos archivos:

* natural-disasters-by-yearly-impact.csv  → eventos por tamaño
* natural-disasters-people-affected.csv   → personas afectadas por tipo

Salida
------
app/datos/owid.json

Uso:
    python -m src.owid
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import APP_DATOS, DATOS_ORIGINALES  # noqa: E402

ARCHIVO_IMPACTO = DATOS_ORIGINALES / "natural-disasters-by-yearly-impact.csv"
ARCHIVO_AFECTADOS = DATOS_ORIGINALES / "natural-disasters-people-affected.csv"

ANIO_INICIO = 2000


def construir() -> dict:
    """Combina ambos archivos en una estructura por país y año."""
    impacto = pd.read_csv(ARCHIVO_IMPACTO, low_memory=False)
    afectados = pd.read_csv(ARCHIVO_AFECTADOS, low_memory=False)

    impacto = impacto[impacto["year"] >= ANIO_INICIO]
    afectados = afectados[afectados["year"] >= ANIO_INICIO]

    impacto = impacto.rename(
        columns={
            "n_small_events_yearly": "pequenos",
            "n_medium_events_yearly": "medianos",
            "n_large_events_yearly": "grandes",
        }
    )

    unido = impacto.merge(
        afectados[["code", "year", "total_affected_all_disasters_yearly"]],
        on=["code", "year"],
        how="outer",
    )
    unido = unido.rename(columns={"total_affected_all_disasters_yearly": "afectados"})

    columnas = ["pequenos", "medianos", "grandes", "afectados"]
    for columna in columnas:
        unido[columna] = pd.to_numeric(unido[columna], errors="coerce").fillna(0)

    unido = unido.dropna(subset=["code"])
    unido["year"] = unido["year"].astype(int)

    paises: dict[str, list] = {}
    for codigo, grupo in unido.groupby("code"):
        filas = [
            [
                int(f["year"]),
                int(f["afectados"]),
                int(f["pequenos"]),
                int(f["medianos"]),
                int(f["grandes"]),
            ]
            for _, f in grupo.sort_values("year").iterrows()
        ]
        paises[str(codigo)] = filas

    return {
        "meta": {
            "fuente": "Our World in Data (OWID), a partir de EM-DAT",
            "archivos": [ARCHIVO_IMPACTO.name, ARCHIVO_AFECTADOS.name],
            "periodo": [ANIO_INICIO, int(unido["year"].max())],
            "campos": ["anio", "afectados", "pequenos", "medianos", "grandes"],
            "nota": (
                "OWID agrega EM-DAT con otro criterio, así que sus cifras no "
                "tienen que coincidir exactamente con las del panel; sirven "
                "como referencia de orden de magnitud."
            ),
        },
        "paises": paises,
    }


def main() -> None:
    print("Leyendo archivos de OWID…")
    contenido = construir()

    ruta = APP_DATOS / "owid.json"
    with open(ruta, "w", encoding="utf-8") as archivo:
        json.dump(contenido, archivo, ensure_ascii=False, separators=(",", ":"))

    tamano = ruta.stat().st_size / 1024
    print(f"  Países: {len(contenido['paises'])}")
    print(f"  Contexto OWID: {ruta} ({tamano:,.0f} KB)")
    print("\nListo. Contexto de OWID preparado.")


if __name__ == "__main__":
    main()
