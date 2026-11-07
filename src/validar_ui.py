"""
Auditoría automática de la interfaz (Actividad 6).

Comprueba la coherencia entre el HTML, el CSS y el JavaScript de la
aplicación, con énfasis en:

• Referencias de identificadores entre JS y HTML.
• Atributos ARIA, roles, etiquetas y regiones vivas.
• Contraste de color según WCAG 2.1 (AA).
• Presencia de foco visible, movimiento reducido y tamaños táctiles.
• Sincronización de eventos entre app.js y ui_shell.js.
• Enlaces profundos, persistencia y panel móvil.

Genera:
    resultados/tablas/validacion_ui.csv

Uso:
    python -m src.validar_ui
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

RAIZ = Path(__file__).resolve().parents[1]
HTML = RAIZ / "app" / "index.html"
CSS = RAIZ / "app" / "css" / "estilos.css"
APP_JS = RAIZ / "app" / "js" / "app.js"
SHELL_JS = RAIZ / "app" / "js" / "ui_shell.js"
SALIDA = RAIZ / "resultados" / "tablas" / "validacion_ui.csv"

EVENTOS = [
    "atlas:filtros",
    "atlas:seleccion",
    "atlas:modal",
    "atlas:proyeccion",
    "atlas:pestana",
    "atlas:mexico",
    "atlas:listo",
]

# Pares de color que se usan como texto sobre un fondo en la interfaz.
# (variable o color de texto, variable o color de fondo, uso, mínimo WCAG)
PARES_CONTRASTE = [
    ("--tinta", "--superficie", "Títulos sobre tarjetas", 4.5),
    ("--texto", "--superficie", "Texto de cuerpo sobre tarjetas", 4.5),
    ("--texto", "--fondo", "Texto de cuerpo sobre el fondo cálido", 4.5),
    ("--muted", "--superficie", "Texto secundario sobre tarjetas", 4.5),
    ("--purpura", "--superficie", "Cifras y enlaces sobre tarjetas", 4.5),
    ("#ffffff", "--purpura", "Texto blanco sobre púrpura", 4.5),
    ("#8a5200", "--amarillo-suave", "Insignias ámbar", 4.5),
    ("#a12c40", "--rosa-suave", "Sello de fuente rosa", 4.5),
    ("#a12c20", "#ffe8e4", "Chip de filtros desactivados", 4.5),
    ("#5c3700", "--amarillo", "Puesto de ranking sobre amarillo", 4.5),
    ("--purpura-3", "--purpura-suave", "Pestañas inactivas", 4.5),
    ("#d9d0ee", "#241b3a", "Barra de estado sobre fondo oscuro", 4.5),
]


def leer(ruta: Path) -> str:
    return ruta.read_text(encoding="utf-8")


def variables_css(texto: str) -> dict[str, str]:
    """Extrae las variables de color declaradas en :root."""
    bloque = re.search(r":root\s*\{(.*?)\}", texto, re.S)
    variables: dict[str, str] = {}
    if not bloque:
        return variables
    for nombre, valor in re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", bloque.group(1)):
        variables[nombre] = valor.strip()
    return variables


def resolver(color: str, variables: dict[str, str]) -> str:
    color = color.strip()
    if color.startswith("var("):
        color = color[4:-1].strip()
    if color.startswith("--"):
        return resolver(variables.get(color, "#000000"), variables)
    return color


def a_rgb(color: str) -> tuple[float, float, float]:
    color = color.strip().lstrip("#")
    if len(color) == 3:
        color = "".join(c * 2 for c in color)
    if len(color) != 6:
        raise ValueError(f"Color no reconocido: {color}")
    return tuple(int(color[i : i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def luminancia(color: str) -> float:
    canales = []
    for canal in a_rgb(color):
        canales.append(canal / 12.92 if canal <= 0.04045 else ((canal + 0.055) / 1.055) ** 2.4)
    r, g, b = canales
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(color_a: str, color_b: str) -> float:
    la, lb = luminancia(color_a), luminancia(color_b)
    claro, oscuro = max(la, lb), min(la, lb)
    return (claro + 0.05) / (oscuro + 0.05)


def ids_referenciados_js(texto_js: str) -> set[str]:
    patrones = [
        r"getElementById\(\s*[\"']([^\"']+)[\"']",
        r"\$\(\s*[\"']([^\"']+)[\"']",
        r"querySelector\(\s*[\"']#([\w-]+)[\"']",
    ]
    encontrados: set[str] = set()
    for patron in patrones:
        encontrados.update(re.findall(patron, texto_js))
    return encontrados


def main() -> int:
    html_texto = leer(HTML)
    css_texto = leer(CSS)
    app_texto = leer(APP_JS)
    shell_texto = leer(SHELL_JS)
    js_texto = "\n".join(leer(ruta) for ruta in sorted((RAIZ / "app" / "js").glob("*.js")))

    sopa = BeautifulSoup(html_texto, "html.parser")
    ids = [elemento.get("id") for elemento in sopa.find_all(id=True)]
    conjunto_ids = set(ids)

    filas: list[dict[str, str]] = []

    def agregar(categoria: str, comprobacion: str, correcto: bool, detalle: str, nivel: str = "error") -> None:
        filas.append(
            {
                "categoria": categoria,
                "comprobacion": comprobacion,
                "resultado": "OK" if correcto else "REVISAR",
                "nivel": "informativo" if correcto else nivel,
                "detalle": detalle,
            }
        )

    # ------------------------------------------------------------------ #
    # 1. Estructura y semántica                                          #
    # ------------------------------------------------------------------ #
    agregar(
        "Estructura",
        "Idioma del documento declarado",
        sopa.html is not None and sopa.html.get("lang") == "es",
        f"lang={sopa.html.get('lang') if sopa.html else 'sin html'}",
    )

    landmarks = {etiqueta.name for etiqueta in sopa.find_all(["header", "main", "nav", "aside", "footer"])}
    faltantes = {"header", "main", "nav", "aside", "footer"} - landmarks
    agregar(
        "Estructura",
        "Landmarks principales presentes",
        not faltantes,
        "header, main, nav, aside y footer" if not faltantes else f"faltan: {', '.join(sorted(faltantes))}",
    )

    duplicados = sorted({identificador for identificador in ids if ids.count(identificador) > 1})
    agregar(
        "Estructura",
        "Identificadores únicos",
        not duplicados,
        f"{len(ids)} IDs declarados" if not duplicados else f"duplicados: {', '.join(duplicados)}",
    )

    saltos = sopa.select("a.saltar")
    agregar(
        "Estructura",
        "Enlaces para saltar contenido",
        len(saltos) >= 2 and all((enlace.get("href") or "").startswith("#") for enlace in saltos),
        f"{len(saltos)} enlaces de salto",
    )

    # ------------------------------------------------------------------ #
    # 2. Accesibilidad                                                   #
    # ------------------------------------------------------------------ #
    anuncio = sopa.find(id="anuncio-lector")
    agregar(
        "Accesibilidad",
        "Región viva para anuncios",
        anuncio is not None
        and anuncio.get("role") == "status"
        and anuncio.get("aria-live") == "polite",
        "#anuncio-lector con role=status y aria-live=polite",
    )

    pestanas = sopa.select('[role="tab"]')
    problemas_pestanas = []
    for pestana in pestanas:
        controles = pestana.get("aria-controls")
        if pestana.get("aria-selected") not in {"true", "false"}:
            problemas_pestanas.append(f"{pestana.get('id')} sin aria-selected")
        if not controles or controles not in conjunto_ids:
            problemas_pestanas.append(f"{pestana.get('id')} sin aria-controls válido")
    agregar(
        "Accesibilidad",
        "Pestañas con estado y panel asociado",
        len(pestanas) == 4 and not problemas_pestanas,
        f"{len(pestanas)} pestañas" if not problemas_pestanas else "; ".join(problemas_pestanas),
    )

    paneles = sopa.select('[role="tabpanel"]')
    problemas_paneles = []
    for panel in paneles:
        referencia = panel.get("aria-labelledby")
        if not referencia or referencia not in conjunto_ids:
            problemas_paneles.append(f"{panel.get('id')} sin aria-labelledby válido")
    agregar(
        "Accesibilidad",
        "Paneles de pestaña etiquetados",
        len(paneles) == 4 and not problemas_paneles,
        f"{len(paneles)} paneles" if not problemas_paneles else "; ".join(problemas_paneles),
    )

    sin_nombre = []
    for boton in sopa.find_all("button"):
        nombre = (boton.get_text(" ", strip=True) or boton.get("aria-label") or boton.get("title") or "").strip()
        if not nombre:
            sin_nombre.append(boton.get("id") or boton.get("class") or "botón sin identificar")
    agregar(
        "Accesibilidad",
        "Botones con nombre accesible",
        not sin_nombre,
        f"{len(sopa.find_all('button'))} botones" if not sin_nombre else f"sin nombre: {', '.join(sin_nombre)}",
    )

    campos_sin_etiqueta = []
    for campo in sopa.find_all(["input", "select", "textarea"]):
        if campo.get("type") in {"hidden", "submit", "button"}:
            continue
        tiene_label = campo.find_parent("label") is not None
        tiene_aria = bool(campo.get("aria-label") or campo.get("aria-labelledby"))
        if not (tiene_label or tiene_aria):
            campos_sin_etiqueta.append(campo.get("id") or campo.name)
    agregar(
        "Accesibilidad",
        "Campos de formulario etiquetados",
        not campos_sin_etiqueta,
        f"{len(sopa.find_all(['input', 'select', 'textarea']))} campos" if not campos_sin_etiqueta else f"sin etiqueta: {', '.join(campos_sin_etiqueta)}",
    )

    dialogos = sopa.find_all("dialog")
    problemas_dialogos = []
    for dialogo in dialogos:
        referencia = dialogo.get("aria-labelledby")
        if not referencia or referencia not in conjunto_ids:
            problemas_dialogos.append(dialogo.get("id") or "diálogo sin id")
    agregar(
        "Accesibilidad",
        "Diálogos etiquetados",
        not problemas_dialogos,
        f"{len(dialogos)} diálogos" if not problemas_dialogos else f"sin etiqueta: {', '.join(problemas_dialogos)}",
    )

    referencias_aria = []
    for atributo in ("aria-controls", "aria-labelledby", "aria-describedby"):
        for elemento in sopa.find_all(attrs={atributo: True}):
            for referencia in (elemento.get(atributo) or "").split():
                if referencia not in conjunto_ids:
                    referencias_aria.append(f"{atributo}={referencia}")
    agregar(
        "Accesibilidad",
        "Referencias ARIA existentes",
        not referencias_aria,
        "todas las referencias apuntan a IDs reales" if not referencias_aria else "; ".join(referencias_aria),
    )

    agregar(
        "Accesibilidad",
        "Foco visible en controles",
        ":focus-visible" in css_texto,
        "reglas :focus-visible declaradas en el CSS",
    )

    agregar(
        "Accesibilidad",
        "Respeto al movimiento reducido",
        "prefers-reduced-motion" in css_texto,
        "@media (prefers-reduced-motion: reduce) presente",
    )

    agregar(
        "Accesibilidad",
        "Tamaños táctiles mínimos",
        "pointer: coarse" in css_texto and "min-height" in css_texto,
        "regla @media (pointer: coarse) con min-height",
    )

    # ------------------------------------------------------------------ #
    # 3. Integración JS ↔ HTML                                           #
    # ------------------------------------------------------------------ #
    referenciados = ids_referenciados_js(app_texto) | ids_referenciados_js(shell_texto)
    inexistentes = sorted(referenciados - conjunto_ids)
    agregar(
        "Integración",
        "IDs usados por JS existen en el HTML",
        not inexistentes,
        f"{len(referenciados)} IDs verificados" if not inexistentes else f"no existen: {', '.join(inexistentes)}",
    )

    emitidos = {
        evento
        for evento in EVENTOS
        if re.search(rf"(?:emitir|CustomEvent)\(\s*[\"']{re.escape(evento)}[\"']", js_texto)
    }
    agregar(
        "Integración",
        "Eventos de sincronización emitidos",
        len(emitidos) == len(EVENTOS),
        f"{len(emitidos)}/{len(EVENTOS)} eventos: {', '.join(sorted(emitidos))}",
    )

    escuchados = {evento for evento in EVENTOS if re.search(rf"addEventListener\(\s*[\"']{re.escape(evento)}[\"']", shell_texto)}
    agregar(
        "Integración",
        "Eventos de sincronización escuchados",
        len(escuchados) == len(EVENTOS),
        f"{len(escuchados)}/{len(EVENTOS)} eventos: {', '.join(sorted(escuchados))}",
    )

    orden_scripts = re.findall(r'<script src="js/([\w_]+\.js)"', html_texto)
    agregar(
        "Integración",
        "ui_shell.js se carga después de app.js",
        "app.js" in orden_scripts
        and "ui_shell.js" in orden_scripts
        and orden_scripts.index("app.js") < orden_scripts.index("ui_shell.js"),
        " → ".join(orden_scripts),
    )

    metodos_api = ["abrirPais", "cerrarPais", "aplicarFiltros", "activarPestana", "cambiarProyeccion", "seleccionar", "estado"]
    faltan_api = [metodo for metodo in metodos_api if not re.search(rf"{metodo}\s*[:(]", app_texto)]
    agregar(
        "Integración",
        "API pública AtlasApp completa",
        not faltan_api,
        f"{len(metodos_api)} métodos expuestos" if not faltan_api else f"faltan: {', '.join(faltan_api)}",
    )

    agregar(
        "Integración",
        "Buscador de países conectado",
        sopa.find(id="buscador-pais") is not None
        and sopa.find(id="buscador-resultados") is not None
        and "buscador-pais" in shell_texto
        and "buscador-resultados" in shell_texto,
        "entrada y lista de resultados presentes y conectadas",
    )

    agregar(
        "Integración",
        "Chips de filtros activos",
        sopa.find(id="filtros-activos") is not None and "pintarChips" in shell_texto,
        "#filtros-activos renderizado por ui_shell.js",
    )

    agregar(
        "Integración",
        "Enlaces profundos y persistencia",
        "location.hash" in shell_texto
        and "history.replaceState" in shell_texto
        and "localStorage" in shell_texto,
        "hash, replaceState y localStorage integrados",
    )

    agregar(
        "Integración",
        "Panel colapsable en móvil",
        sopa.find(id="btn-panel-movil") is not None
        and "panel-abierto" in css_texto
        and "panel-abierto" in shell_texto,
        "botón, clase de estado y estilos móviles",
    )

    # ------------------------------------------------------------------ #
    # 4. Contraste WCAG AA                                               #
    # ------------------------------------------------------------------ #
    variables = variables_css(css_texto)
    for texto, fondo, uso, minimo in PARES_CONTRASTE:
        color_texto = resolver(texto, variables)
        color_fondo = resolver(fondo, variables)
        try:
            razon = contraste(color_texto, color_fondo)
        except ValueError as error:
            agregar("Contraste", uso, False, str(error))
            continue
        agregar(
            "Contraste",
            uso,
            razon >= minimo,
            f"{color_texto} sobre {color_fondo} = {razon:.2f}:1 (mínimo {minimo}:1)",
            nivel="advertencia",
        )

    # ------------------------------------------------------------------ #
    # 5. Exportación                                                     #
    # ------------------------------------------------------------------ #
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    with SALIDA.open("w", encoding="utf-8", newline="") as archivo:
        escritor = csv.DictWriter(
            archivo,
            fieldnames=["categoria", "comprobacion", "resultado", "nivel", "detalle"],
        )
        escritor.writeheader()
        escritor.writerows(filas)

    errores = [fila for fila in filas if fila["resultado"] != "OK" and fila["nivel"] == "error"]
    advertencias = [fila for fila in filas if fila["resultado"] != "OK" and fila["nivel"] == "advertencia"]

    print(f"Validación de interfaz: {len(filas)} comprobaciones")
    print(f"  Correctas: {len(filas) - len(errores) - len(advertencias)}")
    print(f"  Errores: {len(errores)}")
    print(f"  Advertencias: {len(advertencias)}")
    for fila in errores + advertencias:
        print(f"  [{fila['resultado']}] {fila['categoria']} · {fila['comprobacion']}: {fila['detalle']}")
    print(f"Reporte: {SALIDA.relative_to(RAIZ)}")

    return 1 if errores else 0


if __name__ == "__main__":
    raise SystemExit(main())
