# -*- coding: utf-8 -*-
"""
diccionario_desastres.py — Nombres de los desastres en español
--------------------------------------------------------------
EM-DAT registra los tipos de desastre en inglés ("Flood", "Storm", ...).
En la app y en los reportes se muestran en español.

Este módulo es la fuente única del diccionario: de aquí se genera el archivo
JavaScript que usa la aplicación, para que no haya dos listas distintas.
"""

from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
RUTA_JS = RAIZ / "app" / "js" / "diccionario_desastres.js"

DICCIONARIO: dict[str, str] = {
    "Flood": "Inundación",
    "Storm": "Tormenta",
    "Earthquake": "Terremoto",
    "Drought": "Sequía",
    "Epidemic": "Epidemia",
    "Wildfire": "Incendio forestal",
    "Extreme temperature": "Temperatura extrema",
    "Mass movement (wet)": "Deslizamiento (húmedo)",
    "Mass movement (dry)": "Deslizamiento (seco)",
    "Volcanic activity": "Actividad volcánica",
    "Infestation": "Infestación",
    "Glacial lake outburst flood": "Ruptura de lago glacial",
    "Impact": "Impacto",
    "Animal incident": "Incidente con animales",
}


def traducir(tipo: str) -> str:
    """Devuelve el nombre en español de un tipo de desastre."""
    if not tipo:
        return tipo
    return DICCIONARIO.get(tipo, tipo)


def traducir_serie(valores):
    """Traduce una lista o Serie de pandas conservando el orden."""
    return [traducir(v) for v in valores]


def exportar_js(ruta: Path = RUTA_JS) -> Path:
    """Escribe el diccionario como archivo JavaScript para la app."""
    lineas = [
        "/* =========================================================================\n",
        "   diccionario_desastres.js — Traducción de tipos de desastre EN -> ES\n",
        "   -------------------------------------------------------------------------\n",
        "   Archivo generado desde src/diccionario_desastres.py.\n",
        "   No editar a mano: cambiar el diccionario en Python y regenerarlo.\n",
        "   ========================================================================= */\n",
        "\n",
        "const DICCIONARIO_DESASTRES = {\n",
    ]

    entradas = list(DICCIONARIO.items())
    for i, (ingles, espanol) in enumerate(entradas):
        coma = "," if i < len(entradas) - 1 else ""
        lineas.append(f'  "{ingles}": "{espanol}"{coma}\n')

    lineas.extend(
        [
            "};\n",
            "\n",
            "function traducirTipoDesastre(tipo) {\n",
            "  if (!tipo) return tipo;\n",
            "  return DICCIONARIO_DESASTRES[tipo] || tipo;\n",
            "}\n",
            "\n",
            "window.DICCIONARIO_DESASTRES = DICCIONARIO_DESASTRES;\n",
            "window.traducirTipoDesastre = traducirTipoDesastre;\n",
        ]
    )

    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text("".join(lineas), encoding="utf-8")
    return ruta


if __name__ == "__main__":
    destino = exportar_js()
    print(f"Generado {destino.relative_to(RAIZ)} con {len(DICCIONARIO)} traducciones")
