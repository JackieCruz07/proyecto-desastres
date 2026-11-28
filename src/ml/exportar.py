"""Exporta los modelos a JSON para la aplicación web sin servidor.

La app recibe el vocabulario, las medianas, los pesos de la red, los árboles
de XGBoost y un catálogo de países. Todo se calcula en el navegador.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from . import config
from .datos import cargar_nombres_paises
from .red_neuronal import exportar_pesos


CONTINENTE_A_REGION = {
    "Africa": "Africa",
    "Asia": "Asia",
    "Europe": "Europe",
    "North America": "Americas",
    "South America": "Americas",
    "Oceania": "Oceania",
}

DESCRIPCION_ESCALA = {
    "Km2": "km² (área afectada)",
    "Kph": "km/h (velocidad del viento)",
    "Moment Magnitude": "magnitud de momento",
    "°C": "°C (temperatura)",
    "Vaccinated": "personas vacunadas",
    "Sin dato": "No especificada",
}


def _moda(serie: pd.Series) -> str:
    valores = serie.dropna().astype("string")
    if not len(valores):
        return "Sin dato"
    return str(valores.mode().iloc[0])


def _catalogo_paises(datos: dict) -> list[dict]:
    nombres = cargar_nombres_paises()
    socio = datos["socio"].set_index("iso")
    df = datos["df"]

    modas = df.groupby("iso").agg(
        region=("region", _moda),
        subregion=("subregion", _moda),
        eventos=("DisNo.", "size"),
    )
    mediana_pib = float(socio["pib_pc_mxn"].median())
    mediana_poblacion = float(socio["poblacion"].median())
    mediana_densidad = float(socio["densidad"].median())
    mediana_pib_region: dict[str, float] = {}

    for region in df["region"].dropna().unique():
        isos = df.loc[df["region"] == region, "iso"].unique()
        valores = socio.loc[socio.index.intersection(isos), "pib_pc_mxn"].dropna()
        if len(valores):
            mediana_pib_region[str(region)] = float(valores.median())

    paises = []
    for _, fila in nombres.iterrows():
        iso = str(fila["iso"])
        if iso not in socio.index and iso not in modas.index:
            continue
        datos_socio = socio.loc[iso] if iso in socio.index else None
        region = (
            str(modas.loc[iso, "region"])
            if iso in modas.index
            else CONTINENTE_A_REGION.get(str(fila.get("continente")), "Sin dato")
        )
        subregion = str(modas.loc[iso, "subregion"]) if iso in modas.index else "Sin dato"

        pib = float(datos_socio["pib_pc_mxn"]) if datos_socio is not None and pd.notna(datos_socio["pib_pc_mxn"]) else np.nan
        faltante_pib = int(np.isnan(pib))
        if np.isnan(pib):
            pib = mediana_pib_region.get(region, mediana_pib)

        poblacion = (
            float(datos_socio["poblacion"])
            if datos_socio is not None and pd.notna(datos_socio["poblacion"])
            else mediana_poblacion
        )
        densidad = (
            float(datos_socio["densidad"])
            if datos_socio is not None and pd.notna(datos_socio["densidad"])
            else mediana_densidad
        )

        paises.append(
            {
                "iso": iso,
                "nombre": str(fila.get("nombre") or iso),
                "region": region,
                "subregion": subregion,
                "pib_pc_mxn": round(pib, 2),
                "poblacion": round(poblacion, 0),
                "densidad": round(densidad, 2),
                "pib_faltante": faltante_pib,
                "eventos": int(modas.loc[iso, "eventos"]) if iso in modas.index else 0,
            }
        )

    return sorted(paises, key=lambda p: p["nombre"])


def _catalogo_tipos(datos: dict) -> tuple[list[dict], dict, dict]:
    df = datos["df"]
    conteo = df["tipo"].value_counts()
    tipos = [
        {"valor": str(tipo), "eventos": int(n)}
        for tipo, n in conteo.items()
        if str(tipo) != "Sin dato"
    ]
    subgrupo_por_tipo = {
        str(tipo): _moda(grupo["subgrupo"]) for tipo, grupo in df.groupby("tipo")
    }
    subtipos: dict[str, list[dict]] = {}
    for tipo, grupo in df.groupby("tipo"):
        cuentas = grupo["subtipo"].value_counts()
        subtipos[str(tipo)] = [
            {"valor": str(sub), "eventos": int(n)}
            for sub, n in cuentas.items()
            if str(sub) != "Sin dato"
        ]
    return tipos, subgrupo_por_tipo, subtipos


def _catalogo_escalas(datos: dict) -> list[dict]:
    conteo = datos["df"]["escala"].value_counts()
    escalas = []
    for escala, n in conteo.items():
        valor = str(escala)
        escalas.append(
            {
                "valor": valor,
                "etiqueta": DESCRIPCION_ESCALA.get(valor, valor),
                "eventos": int(n),
            }
        )
    return escalas


def _metricas_app(metricas: dict) -> dict:
    clasificacion = metricas["clasificacion"]
    return {
        "clasificacion": {
            "red_neuronal": clasificacion["red_neuronal"]["prueba"],
            "xgboost": clasificacion["xgboost"]["prueba"],
            "comparacion": clasificacion["comparacion_nn_vs_xgb"],
        },
        "regresion_afectados": metricas["regresion_afectados"],
        "regresion_dano": metricas["regresion_dano"],
    }


def _ejemplo_clasificacion(
    datos: dict,
    preprocesador,
    nn: dict,
    xgb: dict,
) -> dict:
    test = datos["test"][datos["test"]["elegible_clasificacion"] == 1].reset_index(drop=True)
    Xc, Xn = preprocesador.transform_nn(test.iloc[[0]])
    Xx = preprocesador.transform_xgb(test.iloc[[0]])
    return {
        "descripcion": "Primer evento de prueba 2024–2025",
        "cat_codes": Xc[0].astype(int).tolist(),
        "num_scaled": [round(float(v), 7) for v in Xn[0]],
        "vector_xgb": [round(float(v), 7) for v in Xx.iloc[0].to_numpy()],
        "prob_nn": round(float(nn["prob_test"][0]), 7),
        "prob_xgb": round(float(xgb["prob_test"][0]), 7),
        "y": int(test.iloc[0]["alto_impacto"]),
    }


def _ejemplo_regresion(preprocesador, regresion: dict, nombre: str) -> dict:
    test = regresion["test"].reset_index(drop=True)
    Xc, Xn = preprocesador.transform_nn(test.iloc[[0]])
    Xx = preprocesador.transform_xgb(test.iloc[[0]])
    return {
        "descripcion": f"Primer evento de prueba con {nombre} observado",
        "cat_codes": Xc[0].astype(int).tolist(),
        "num_scaled": [round(float(v), 7) for v in Xn[0]],
        "vector_xgb": [round(float(v), 7) for v in Xx.iloc[0].to_numpy()],
        "pred_nn": round(float(regresion["pred_nn_test"][0]), 7),
        "pred_xgb": round(float(regresion["pred_xgb_test"][0]), 7),
        "y": round(float(regresion["y_test"][0]), 7),
    }


def exportar_modelos_app(
    datos: dict,
    preprocesador,
    nn: dict,
    xgb: dict,
    afectados: dict,
    dano: dict,
    metricas: dict,
) -> Path:
    """Construye ``app/modelos/modelo_prediccion.json``."""
    config.MODELOS_APP.mkdir(parents=True, exist_ok=True)

    tipos, subgrupo_por_tipo, subtipos = _catalogo_tipos(datos)
    escalas = _catalogo_escalas(datos)
    paises = _catalogo_paises(datos)
    entrenamiento = datos["train"][datos["train"]["elegible_clasificacion"] == 1]

    clasificacion = {
        "red_neuronal": {
            "pesos": exportar_pesos(nn["modelos"]),
            "temperatura": nn["temperatura"],
            "umbral": nn["umbral"],
        },
        "xgboost": {
            "arboles": xgb["exportado"],
            "temperatura": xgb["temperatura"],
            "umbral": xgb["umbral"],
        },
    }

    regresion = {
        "afectados": {
            "red_neuronal": {
                "pesos": exportar_pesos(afectados["modelos"]),
                "estadisticas": afectados["estadisticas"],
            },
            "xgboost": {
                "arboles": afectados["exportado"],
                "q10_residual": afectados["metricas"]["xgboost"]["intervalos"]["q10_residual"],
                "q90_residual": afectados["metricas"]["xgboost"]["intervalos"]["q90_residual"],
            },
            "metricas": afectados["metricas"],
        },
        "dano": {
            "red_neuronal": {
                "pesos": exportar_pesos(dano["modelos"]),
                "estadisticas": dano["estadisticas"],
            },
            "xgboost": {
                "arboles": dano["exportado"],
                "q10_residual": dano["metricas"]["xgboost"]["intervalos"]["q10_residual"],
                "q90_residual": dano["metricas"]["xgboost"]["intervalos"]["q90_residual"],
            },
            "metricas": dano["metricas"],
            "exploratorio": True,
        },
    }

    paquete = {
        "version": 1,
        "generado": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "fuente": "EM-DAT integrado con WDI, 2000–2025",
        "unidad_dano": "miles de pesos mexicanos ajustados",
        "target": {
            "clasificacion": "alto_impacto",
            "definicion_alto_impacto": datos["umbrales"]["definicion"],
            "umbral_muertes": datos["umbrales"]["muertes_p75"],
            "umbral_afectados": datos["umbrales"]["afectados_p75"],
            "afectados": "log1p(Total Affected)",
            "dano": "log1p(Total Damage, Adjusted, miles de MXN)",
        },
        "particiones": {
            "entrenamiento": "2000–2022",
            "validacion": "2023",
            "prueba": "2024–2025",
            "n_entrenamiento": int(len(entrenamiento)),
        },
        "esquema": preprocesador.to_dict(),
        "catalogo": {
            "paises": paises,
            "tipos": tipos,
            "subgrupo_por_tipo": subgrupo_por_tipo,
            "subtipos_por_tipo": subtipos,
            "escalas": escalas,
            "meses": config.MESES,
        },
        "perfil_promedio": preprocesador.perfil_promedio(entrenamiento),
        "clasificacion": clasificacion,
        "regresion": regresion,
        "metricas": _metricas_app(metricas),
        "ejemplos": {
            "clasificacion": _ejemplo_clasificacion(datos, preprocesador, nn, xgb),
            "afectados": _ejemplo_regresion(preprocesador, afectados, "afectados"),
            "dano": _ejemplo_regresion(preprocesador, dano, "dano"),
        },
        "advertencia": (
            "Estimación estadística basada en EM-DAT 2000–2025. No es una "
            "alerta oficial ni una predicción determinista: los registros "
            "históricos tienen subregistro y los daños económicos faltan en "
            "cerca de 70 % de los eventos."
        ),
    }

    destino = config.MODELOS_APP / "modelo_prediccion.json"
    destino.write_text(
        json.dumps(paquete, ensure_ascii=False, separators=(",", ":"), default=float),
        encoding="utf-8",
    )
    return destino
