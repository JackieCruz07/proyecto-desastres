# -*- coding: utf-8 -*-
"""Genera app/datos/filtros.json con agregados por país, año y tipo."""

from pathlib import Path
import json

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
CSV = RAIZ / "datos" / "procesados" / "EMDAT_integrado_WDI_validado.csv"
SALIDA = RAIZ / "app" / "datos" / "filtros.json"

df = pd.read_csv(CSV, low_memory=False)

df["Start Year"] = pd.to_numeric(df["Start Year"], errors="coerce")
df = df.dropna(subset=["Start Year", "ISO", "Disaster Type"])

df["fallecidos"] = pd.to_numeric(df["Total Deaths"], errors="coerce").fillna(0)
df["afectados"] = pd.to_numeric(df["Total Affected"], errors="coerce").fillna(0)
df["dano_usd"] = (
    pd.to_numeric(df["Total Damage, Adjusted ('000 US$)"], errors="coerce").fillna(0) * 1000.0
)

grupo = (
    df.groupby(["ISO", "Start Year", "Disaster Type"], as_index=False)
    .agg(
        eventos=("ISO", "size"),
        fallecidos=("fallecidos", "sum"),
        afectados=("afectados", "sum"),
        dano_usd=("dano_usd", "sum"),
    )
)

datos = {}
for fila in grupo.itertuples(index=False):
    iso = str(fila.ISO)
    datos.setdefault(iso, []).append(
        [
            int(fila._1),                 # año
            str(fila._2),                 # tipo
            int(fila.eventos),
            int(round(fila.fallecidos)),
            int(round(fila.afectados)),
            float(round(fila.dano_usd, 2)),
        ]
    )

tipos = sorted(df["Disaster Type"].dropna().unique().tolist())

salida = {
    "periodo": {
        "inicio": int(df["Start Year"].min()),
        "fin": int(df["Start Year"].max()),
    },
    "tipos": tipos,
    "datos": datos,
}

SALIDA.write_text(json.dumps(salida, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

tam = SALIDA.stat().st_size / 1024
print(f"Generado {SALIDA.name}: {len(datos)} países, {len(grupo)} combinaciones, {tam:.0f} KB")
