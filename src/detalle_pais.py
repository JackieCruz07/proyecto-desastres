"""
Detalle de eventos por país para el panel de información (Actividad 5).

El panel por país necesita mostrar los desastres con mayor impacto humano
y económico, y esa lista tiene que cambiar cuando el usuario mueve los
filtros de periodo y tipo. Por eso el detalle se guarda a nivel de evento
y no como un resumen fijo: el navegador filtra y ordena sobre esos datos.

Salida
------
app/datos/eventos_pais.json

    {
      "meta": {...},
      "paises": {
        "MEX": [[2017, "Earthquake", 369, 0, 123456789000, "Sismo"], ...]
      }
    }

Cada fila es: [año, tipo, fallecidos, afectados, daño_mxn, nombre].
Los valores desconocidos se guardan como null para no confundirlos con 0.

Uso:
    python -m src.detalle_pais
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import APP_DATOS, DATASET_INTEGRADO  # noqa: E402

# Mismos alias que la capa temática para que los códigos coincidan.
EQUIVALENCIAS_ISO = {"PSE": "PSX", "SSD": "SDS"}
FUSIONES = {"CYN": "CYP", "SOL": "SOM"}

COLUMNA_DANO = "Total Damage, Adjusted ('000 MXN)"


def _numero(valor) -> float | int | None:
    """Devuelve un número JSON o None cuando el dato no existe."""
    if valor is None or pd.isna(valor):
        return None
    numero = float(valor)
    return int(numero) if numero.is_integer() else round(numero, 2)


def construir(df: pd.DataFrame) -> dict:
    """Agrupa los eventos por código de país en arreglos compactos."""
    datos = df.copy()

    datos["ISO_mapa"] = (
        datos["ISO"].astype(str).str.strip().replace(EQUIVALENCIAS_ISO).replace(FUSIONES)
    )
    datos = datos[datos["ISO_mapa"].notna() & (datos["ISO_mapa"] != "NAN")]

    datos["anio"] = pd.to_numeric(datos["Start Year"], errors="coerce")
    datos = datos.dropna(subset=["anio"])
    datos["anio"] = datos["anio"].astype(int)

    # El daño se guarda en pesos completos (el dataset lo trae en miles).
    datos["dano_mxn"] = pd.to_numeric(datos[COLUMNA_DANO], errors="coerce") * 1000

    paises: dict[str, list] = {}
    for codigo, grupo in datos.sort_values(["anio", "DisNo."]).groupby("ISO_mapa"):
        filas = []
        for _, evento in grupo.iterrows():
            nombre = evento.get("Event Name")
            nombre = str(nombre).strip() if isinstance(nombre, str) else ""
            filas.append(
                [
                    int(evento["anio"]),
                    str(evento.get("Disaster Type") or "Unknown"),
                    _numero(evento.get("Total Deaths")),
                    _numero(evento.get("Total Affected")),
                    _numero(evento.get("dano_mxn")),
                    nombre,
                ]
            )
        paises[str(codigo)] = filas

    return {
        "meta": {
            "n_eventos": int(len(datos)),
            "n_paises": len(paises),
            "unidad_dano": "MXN",
            "campos": ["anio", "tipo", "fallecidos", "afectados", "dano_mxn", "nombre"],
            "nota": (
                "Los valores nulos representan datos no registrados en EM-DAT; "
                "no equivalen a cero."
            ),
        },
        "paises": paises,
    }


def main() -> None:
    print("Leyendo dataset integrado…")
    df = pd.read_csv(DATASET_INTEGRADO, low_memory=False)
    print(f"  Eventos: {len(df):,}")

    contenido = construir(df)

    ruta = APP_DATOS / "eventos_pais.json"
    with open(ruta, "w", encoding="utf-8") as archivo:
        json.dump(contenido, archivo, ensure_ascii=False, separators=(",", ":"))

    tamano = ruta.stat().st_size / 1024
    print(f"  Eventos por país: {ruta} ({tamano:,.0f} KB)")
    print(f"  Países: {contenido['meta']['n_paises']}")
    print("\nListo. Detalle por país preparado.")


if __name__ == "__main__":
    main()
