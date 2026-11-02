"""
Impacto de los desastres naturales en México por estado (CENAPRED / ANR).

Fuente
------
Atlas Nacional de Riesgos (CENAPRED):
"Base de datos sobre el impacto socioeconómico de los daños y pérdidas
ocasionados por los desastres en México de 2000 a 2024".
https://www.atlasnacionalderiesgos.gob.mx/descargas/Basehistorica_2000_a_2024.xlsx

El archivo trae 10,354 registros con estado, municipios afectados, tipo de
fenómeno, defunciones, población afectada, viviendas, escuelas, hospitales,
comercios, superficie de cultivo y daños totales en MILLONES DE PESOS.

Decisiones de integración
-------------------------
1. Solo se usan fenómenos naturales: clasificación Hidrometeorológico,
   Geológico y Sanitario. Se excluyen los sociorganizativos y químicos
   (accidentes, explosiones, fugas) porque no son desastres naturales.
2. Los incendios forestales de CENAPRED se excluyen para no duplicar la capa
   de CONAFOR, que ya tiene 74,853 registros con coordenadas.
3. Los montos ya vienen en pesos mexicanos: no se aplica tipo de cambio.
4. Los 11 registros que listan varios estados se reparten en partes iguales
   entre los estados mencionados y se documenta la aproximación.
5. Los nombres de estado se homologan contra el GeoJSON de los 32 estados.

Salidas
-------
app/datos/mexico_estados.json        indicadores por estado, año y tipo
app/datos/estados_mexico.geojson     polígonos de los 32 estados
resultados/tablas/mexico_estados_resumen.csv

Uso:
    python -m src.mexico_estados
"""

from __future__ import annotations

import json
import sys
import unicodedata
from pathlib import Path

import pandas as pd

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import (  # noqa: E402
    APP_DATOS,
    DATOS_GEOGRAFICOS,
    DATOS_ORIGINALES,
    RESULTADOS_TABLAS,
    asegurar_carpetas,
)

ARCHIVO_CENAPRED = DATOS_ORIGINALES / "CENAPRED_impacto_2000_2024.xlsx"
GEOJSON_ESTADOS = DATOS_GEOGRAFICOS / "estados_mexico_raw.geojson"

CLASIFICACIONES_NATURALES = {"Hidrometeorológico", "Geológico", "Sanitario"}

# Registros destacados: (año, fecha ISO, tipo, estado, título)
DESTACADOS = [
    (2023, "2023-10-24", "Ciclón tropical", "Guerrero", "Huracán Otis"),
    (2017, "2017-09-19", "Sismo", "Ciudad de México", "Sismo del 19S"),
    (2007, "2007-10-24", "Lluvias", "Tabasco", "Inundación de Tabasco 2007"),
    (2020, "2020-10-29", "Lluvias", "Tabasco", "Inundación de Tabasco 2020"),
]

# Variantes observadas en la fuente → nombre oficial del GeoJSON.
ALIAS_ESTADOS = {
    "cdmx": "Ciudad de México",
    "distrito federal": "Ciudad de México",
    "ciudad de mexico": "Ciudad de México",
    "estado de mexico": "México",
    "mexico": "México",
    "michoacan": "Michoacán",
    "nuevo leon": "Nuevo León",
    "queretaro": "Querétaro",
    "san luis potosi": "San Luis Potosí",
    "yucatan": "Yucatán",
    "coahuila": "Coahuila",
    "veracruz": "Veracruz",
}

TIPOS_CANONICOS = {
    "lluvia": "Lluvias",
    "lluvias": "Lluvias",
    "inundacion": "Inundación",
    "ciclón tropical": "Ciclón tropical",
    "cICLON TROPICAL": "Ciclón tropical",
    "sismo": "Sismo",
    "sequia": "Sequía",
    "bajas temperaturas": "Bajas temperaturas",
    "temperatura extrema": "Temperatura extrema",
    "helada": "Helada",
    "nevada": "Nevada",
    "granizada": "Granizada",
    "fuertes vientos": "Fuertes vientos",
    "tormenta severa": "Tormenta severa",
    "tormenta tropical": "Tormenta tropical",
    "tormenta electrica": "Tormenta eléctrica",
    "tornado": "Tornado",
    "mar de fondo": "Mar de fondo",
    "marea de tormenta": "Marea de tormenta",
    "deslizamiento": "Deslizamiento",
    "derrumbe": "Derrumbe",
    "hundimiento": "Hundimiento",
    "agrietamiento": "Agrietamiento",
    "actividad volcanica": "Actividad volcánica",
    "proceso de remocion en masa": "Remoción en masa",
    "epidemia": "Epidemia",
    "plaga": "Plaga",
    "marea roja": "Marea roja",
    "intoxicacion": "Intoxicación",
    "enfermedad": "Enfermedad",
}


# ---------------------------------------------------------------------------
# 1. LIMPIEZA Y HOMOLOGACIÓN
# ---------------------------------------------------------------------------

def _sin_acentos(texto: str) -> str:
    """Devuelve el texto en minúsculas y sin acentos, para comparar."""
    base = unicodedata.normalize("NFKD", str(texto))
    return "".join(c for c in base if not unicodedata.combining(c)).strip().lower()


def _canonico_tipo(valor: str) -> str:
    """Unifica mayúsculas, acentos y variantes de escritura del tipo."""
    clave = _sin_acentos(valor)
    if clave in TIPOS_CANONICOS:
        return TIPOS_CANONICOS[clave]
    return str(valor).strip().capitalize()


def _separar_estados(valor: str) -> list[str]:
    """Parte un campo que puede traer varios estados: 'A, B y C'."""
    limpio = str(valor).replace(" y ", ", ").replace(";", ",")
    return [p.strip() for p in limpio.split(",") if p.strip()]


def cargar_geojson() -> tuple[dict, dict]:
    """Lee los 32 estados y devuelve (nombre → id, id → nombre)."""
    with open(GEOJSON_ESTADOS, encoding="utf-8") as f:
        datos = json.load(f)
    nombre_a_id = {}
    id_a_nombre = {}
    for rasgo in datos["features"]:
        props = rasgo["properties"]
        nombre = props["name"]
        nombre_a_id[nombre] = props["id"]
        id_a_nombre[props["id"]] = nombre
    return nombre_a_id, id_a_nombre


def normalizar_estado(valor: str, nombre_a_id: dict) -> str | None:
    """Convierte cualquier variante al nombre oficial del GeoJSON."""
    texto = str(valor).strip()
    if not texto:
        return None
    if texto in nombre_a_id:
        return texto
    clave = _sin_acentos(texto)
    if clave in ALIAS_ESTADOS:
        return ALIAS_ESTADOS[clave]
    for nombre in nombre_a_id:
        if _sin_acentos(nombre) == clave:
            return nombre
    return None


def cargar_cenapred() -> pd.DataFrame:
    """Lee el Excel de CENAPRED y homologa columnas y tipos."""
    df = pd.read_excel(ARCHIVO_CENAPRED)
    df = df.rename(
        columns={
            "Fecha de Inicio": "fecha_inicio",
            "Fecha de Fin": "fecha_fin",
            "Año": "anio",
            "Clasificación del fenómeno": "clasificacion",
            "Tipo de fenómeno": "tipo",
            "Estado": "estado_crudo",
            "Municipios Afectados": "municipios",
            "Descripcion general de los daños": "descripcion",
            "Defunciones": "defunciones",
            "Población afectada ": "afectados",
            "Viviendas dañadas": "viviendas",
            "Escuelas": "escuelas",
            "Hospitales ": "hospitales",
            "Comercios": "comercios",
            "Area de cultivo dañada / pastizales (h)": "cultivos_ha",
            "Total de daños (millones de pesos)": "dano_millones",
            "Fuente": "fuente",
        }
    )
    df["fecha_inicio"] = pd.to_datetime(df["fecha_inicio"], errors="coerce")
    df["anio"] = pd.to_numeric(df["anio"], errors="coerce").astype("Int64")
    for col in (
        "defunciones",
        "afectados",
        "viviendas",
        "escuelas",
        "hospitales",
        "comercios",
        "cultivos_ha",
        "dano_millones",
    ):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    df["clasificacion"] = df["clasificacion"].astype(str).str.strip()
    df["tipo"] = df["tipo"].map(_canonico_tipo)
    df["municipios"] = df["municipios"].fillna("").astype(str)
    df["descripcion"] = df["descripcion"].fillna("").astype(str)
    df["fuente"] = df["fuente"].fillna("CENAPRED").astype(str)
    return df


def explotar_estados(df: pd.DataFrame, nombre_a_id: dict) -> tuple[pd.DataFrame, dict]:
    """
    Convierte cada registro en una fila por estado.

    Si el registro menciona varios estados, los indicadores se reparten en
    partes iguales para no duplicar el total nacional.
    """
    filas = []
    descartados = {"sin_estado": 0, "nacional": 0}
    for _, fila in df.iterrows():
        partes = _separar_estados(fila["estado_crudo"])
        oficiales = []
        for parte in partes:
            nombre = normalizar_estado(parte, nombre_a_id)
            if nombre is None:
                if _sin_acentos(parte) in {"todo el pais", "varios estados"}:
                    descartados["nacional"] += 1
                else:
                    descartados["sin_estado"] += 1
            elif nombre not in oficiales:
                oficiales.append(nombre)
        if not oficiales:
            continue
        factor = 1.0 / len(oficiales)
        for nombre in oficiales:
            registro = fila.copy()
            registro["estado"] = nombre
            registro["iso"] = nombre_a_id[nombre]
            for col in (
                "defunciones",
                "afectados",
                "viviendas",
                "escuelas",
                "hospitales",
                "comercios",
                "cultivos_ha",
                "dano_millones",
            ):
                registro[col] = fila[col] * factor
            filas.append(registro)
    return pd.DataFrame(filas), descartados


# ---------------------------------------------------------------------------
# 2. AGREGACIÓN
# ---------------------------------------------------------------------------

def _redondear(valor: float, decimales: int = 0) -> float:
    return round(float(valor), decimales)


def agregar_estados(df: pd.DataFrame, id_a_nombre: dict) -> dict:
    """Construye el bloque de indicadores por estado."""
    total_dano = df["dano_millones"].sum()
    total_def = df["defunciones"].sum()
    total_eventos = len(df)

    ranking_dano = (
        df.groupby("iso")["dano_millones"].sum().sort_values(ascending=False).index.tolist()
    )
    ranking_def = (
        df.groupby("iso")["defunciones"].sum().sort_values(ascending=False).index.tolist()
    )
    ranking_eventos = df.groupby("iso").size().sort_values(ascending=False).index.tolist()

    salida = {}
    for iso, grupo in df.groupby("iso"):
        anios = grupo["anio"].dropna()
        salida[iso] = {
            "iso": iso,
            "nombre": id_a_nombre.get(iso, iso),
            "eventos": int(len(grupo)),
            "defunciones": _redondear(grupo["defunciones"].sum()),
            "afectados": _redondear(grupo["afectados"].sum()),
            "dano_mxn": _redondear(grupo["dano_millones"].sum() * 1_000_000),
            "viviendas": _redondear(grupo["viviendas"].sum()),
            "escuelas": _redondear(grupo["escuelas"].sum()),
            "hospitales": _redondear(grupo["hospitales"].sum()),
            "comercios": _redondear(grupo["comercios"].sum()),
            "cultivos_ha": _redondear(grupo["cultivos_ha"].sum(), 1),
            "anio_min": int(anios.min()) if not anios.empty else None,
            "anio_max": int(anios.max()) if not anios.empty else None,
            "ranking_dano": ranking_dano.index(iso) + 1,
            "ranking_defunciones": ranking_def.index(iso) + 1,
            "ranking_eventos": ranking_eventos.index(iso) + 1,
            "participacion_dano": _redondear(
                100 * grupo["dano_millones"].sum() / total_dano, 2
            ) if total_dano else 0,
            "participacion_eventos": _redondear(100 * len(grupo) / total_eventos, 2),
            "participacion_defunciones": _redondear(
                100 * grupo["defunciones"].sum() / total_def, 2
            ) if total_def else 0,
        }
    return salida


def agregar_series(df: pd.DataFrame) -> tuple[dict, dict, dict]:
    """Series por estado y año, por estado y tipo, y nacional por año."""
    por_anio: dict[str, dict[str, list]] = {}
    por_tipo: dict[str, dict[str, list]] = {}
    for iso, grupo in df.groupby("iso"):
        anios = {}
        for anio, sub in grupo.groupby("anio"):
            if pd.isna(anio):
                continue
            anios[str(int(anio))] = [
                int(len(sub)),
                _redondear(sub["dano_millones"].sum() * 1_000_000),
                _redondear(sub["defunciones"].sum()),
                _redondear(sub["afectados"].sum()),
            ]
        por_anio[iso] = dict(sorted(anios.items()))

        tipos = {}
        for tipo, sub in grupo.groupby("tipo"):
            tipos[str(tipo)] = [
                int(len(sub)),
                _redondear(sub["dano_millones"].sum() * 1_000_000),
                _redondear(sub["defunciones"].sum()),
            ]
        por_tipo[iso] = dict(
            sorted(tipos.items(), key=lambda kv: kv[1][0], reverse=True)
        )

    nacional = {}
    for anio, sub in df.groupby("anio"):
        if pd.isna(anio):
            continue
        nacional[str(int(anio))] = [
            int(len(sub)),
            _redondear(sub["dano_millones"].sum() * 1_000_000),
            _redondear(sub["defunciones"].sum()),
            _redondear(sub["afectados"].sum()),
        ]
    return por_anio, por_tipo, dict(sorted(nacional.items()))


def resumen_tipos(df: pd.DataFrame) -> list[dict]:
    """Totales nacionales por tipo de fenómeno."""
    filas = []
    for tipo, grupo in df.groupby("tipo"):
        filas.append(
            {
                "tipo": tipo,
                "eventos": int(len(grupo)),
                "dano_mxn": _redondear(grupo["dano_millones"].sum() * 1_000_000),
                "defunciones": _redondear(grupo["defunciones"].sum()),
                "afectados": _redondear(grupo["afectados"].sum()),
            }
        )
    return sorted(filas, key=lambda f: f["eventos"], reverse=True)


def serie_por_estado(df: pd.DataFrame) -> dict:
    """Serie compacta por estado para filtrar en el navegador.

    Cada fila es [año, tipo, daño_mxn, defunciones, afectados, viviendas].
    """
    salida = {}
    for iso, grupo in df.groupby("iso"):
        filas = []
        for _, fila in grupo.iterrows():
            if pd.isna(fila["anio"]):
                continue
            filas.append(
                [
                    int(fila["anio"]),
                    str(fila["tipo"]),
                    _redondear(fila["dano_millones"] * 1_000_000, 2),
                    _redondear(fila["defunciones"], 2),
                    _redondear(fila["afectados"], 2),
                    _redondear(fila["viviendas"], 2),
                ]
            )
        salida[iso] = sorted(filas, key=lambda f: (f[0], -f[2]))
    return salida


def top_eventos(df: pd.DataFrame, limite: int = 4) -> dict:
    """Los eventos más costosos de cada estado, para la ficha estatal."""
    salida = {}
    for iso, grupo in df.groupby("iso"):
        grupo = grupo.sort_values("dano_millones", ascending=False).head(limite)
        salida[iso] = [
            {
                "anio": int(fila["anio"]) if not pd.isna(fila["anio"]) else None,
                "fecha": (
                    fila["fecha_inicio"].strftime("%Y-%m-%d")
                    if not pd.isna(fila["fecha_inicio"])
                    else ""
                ),
                "tipo": str(fila["tipo"]),
                "municipios": len(
                    [m for m in str(fila["municipios"]).split(",") if m.strip()]
                ),
                "defunciones": _redondear(fila["defunciones"]),
                "afectados": _redondear(fila["afectados"]),
                "dano_mxn": _redondear(fila["dano_millones"] * 1_000_000),
            }
            for _, fila in grupo.iterrows()
        ]
    return salida


# ---------------------------------------------------------------------------
# 3. FICHAS DESTACADAS
# ---------------------------------------------------------------------------

def construir_destacados(df: pd.DataFrame, estados: dict) -> list[dict]:
    """Localiza los cuatro desastres emblemáticos y arma su ficha."""
    salida = []
    for anio, fecha, tipo, estado, titulo in DESTACADOS:
        candidatos = df[
            (df["anio"] == anio)
            & (df["fecha_inicio"].dt.strftime("%Y-%m-%d") == fecha)
            & (df["tipo"] == tipo)
            & (df["estado"] == estado)
        ]
        if candidatos.empty:
            continue
        fila = candidatos.sort_values("dano_millones", ascending=False).iloc[0]
        iso = fila["iso"]
        municipios = [m.strip() for m in fila["municipios"].split(",") if m.strip()]
        dano = float(fila["dano_millones"]) * 1_000_000
        total_estado = estados[iso]["dano_mxn"] or 1
        ranking = (
            df.groupby("iso")["dano_millones"]
            .sum()
            .sort_values(ascending=False)
            .index.tolist()
            .index(iso)
            + 1
        )
        salida.append(
            {
                "id": f"{anio}-{iso}",
                "titulo": titulo,
                "anio": int(anio),
                "fecha": fecha,
                "tipo": tipo,
                "clasificacion": fila["clasificacion"],
                "estado": estado,
                "iso": iso,
                "municipios": municipios,
                "num_municipios": len(municipios),
                "descripcion": fila["descripcion"].strip(),
                "defunciones": _redondear(fila["defunciones"]),
                "afectados": _redondear(fila["afectados"]),
                "dano_mxn": _redondear(dano),
                "viviendas": _redondear(fila["viviendas"]),
                "escuelas": _redondear(fila["escuelas"]),
                "hospitales": _redondear(fila["hospitales"]),
                "comercios": _redondear(fila["comercios"]),
                "cultivos_ha": _redondear(fila["cultivos_ha"], 1),
                "fuente": fila["fuente"],
                "ranking_estatal_dano": ranking,
                "participacion_estatal": _redondear(100 * dano / total_estado, 1),
            }
        )
    return salida


# ---------------------------------------------------------------------------
# 4. EXPORTACIÓN
# ---------------------------------------------------------------------------

def exportar_geojson() -> None:
    """Copia los polígonos de los estados al directorio de la app."""
    with open(GEOJSON_ESTADOS, encoding="utf-8") as f:
        datos = json.load(f)
    for rasgo in datos["features"]:
        props = rasgo["properties"]
        rasgo["properties"] = {"id": props["id"], "name": props["name"]}
    destino = APP_DATOS / "estados_mexico.geojson"
    with open(destino, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, separators=(",", ":"))
    print(f"  estados_mexico.geojson  ({destino.stat().st_size / 1024:.0f} KB)")


def main() -> None:
    asegurar_carpetas()
    print("1. Leyendo CENAPRED…")
    df = cargar_cenapred()
    print(f"   {len(df):,} registros · {df['anio'].min()}–{df['anio'].max()}")

    print("2. Filtrando fenómenos naturales…")
    naturales = df[df["clasificacion"].isin(CLASIFICACIONES_NATURALES)].copy()
    print(f"   {len(naturales):,} registros naturales")

    print("3. Homologando estados…")
    nombre_a_id, id_a_nombre = cargar_geojson()
    largo, descartados = explotar_estados(naturales, nombre_a_id)
    print(
        f"   {len(largo):,} filas estado-evento · "
        f"{largo['iso'].nunique()} estados · "
        f"{descartados['nacional']} menciones nacionales · "
        f"{descartados['sin_estado']} sin identificar"
    )

    print("4. Agregando indicadores…")
    estados = agregar_estados(largo, id_a_nombre)
    por_anio, por_tipo, nacional = agregar_series(largo)
    tipos = resumen_tipos(largo)
    serie = serie_por_estado(largo)
    mejores = top_eventos(largo)
    destacados = construir_destacados(largo, estados)

    total = {
        "eventos": int(len(largo)),
        "defunciones": _redondear(largo["defunciones"].sum()),
        "afectados": _redondear(largo["afectados"].sum()),
        "dano_mxn": _redondear(largo["dano_millones"].sum() * 1_000_000),
        "viviendas": _redondear(largo["viviendas"].sum()),
    }
    print(
        f"   Nacional: {total['eventos']:,} eventos · "
        f"{total['defunciones']:,.0f} defunciones · "
        f"{total['dano_mxn'] / 1e9:,.1f} mil M MXN"
    )

    payload = {
        "meta": {
            "fuente": "CENAPRED · Atlas Nacional de Riesgos",
            "archivo": ARCHIVO_CENAPRED.name,
            "descripcion": (
                "Impacto socioeconómico de los desastres en México, 2000–2024. "
                "Solo fenómenos naturales; montos originales en pesos."
            ),
            "periodo": [int(largo["anio"].min()), int(largo["anio"].max())],
            "registros_fuente": int(len(df)),
            "registros_naturales": int(len(naturales)),
            "filas_estado_evento": int(len(largo)),
            "estados_con_datos": int(largo["iso"].nunique()),
            "actualizado": "2026-10-30",
        },
        "total": total,
        "estados": estados,
        "por_anio": por_anio,
        "por_tipo": por_tipo,
        "serie": serie,
        "top_eventos": mejores,
        "nacional_por_anio": nacional,
        "tipos": tipos,
        "destacados": destacados,
    }

    destino = APP_DATOS / "mexico_estados.json"
    with open(destino, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    print(f"5. mexico_estados.json ({destino.stat().st_size / 1024:.0f} KB)")

    exportar_geojson()

    tabla = pd.DataFrame(estados.values()).sort_values("dano_mxn", ascending=False)
    tabla = tabla[
        [
            "nombre",
            "eventos",
            "defunciones",
            "afectados",
            "dano_mxn",
            "viviendas",
            "participacion_dano",
            "ranking_dano",
        ]
    ]
    csv = RESULTADOS_TABLAS / "mexico_estados_resumen.csv"
    tabla.to_csv(csv, index=False, encoding="utf-8-sig")
    print(f"6. {csv.name} ({len(tabla)} estados)")

    print("\nDestacados:")
    for d in destacados:
        print(
            f"   {d['titulo']}: {d['estado']} · "
            f"{d['dano_mxn'] / 1e9:,.1f} mil M MXN · "
            f"{d['defunciones']:,.0f} defunciones"
        )


if __name__ == "__main__":
    main()
