/* =========================================================================
   escalas.js — Escalas de color e interpolación temática
   -------------------------------------------------------------------------
   Convierte valores numéricos (y valores normalizados 0–1 para la altura)
   en colores del mapa. Implementa las escalas lineal y logarítmica y la
   "intensidad de color" que ajusta la saturación de la rampa.
   ========================================================================= */

/* ------------------------------------------------------------------------ *
 * Interpolación de color en el espacio RGB                                  *
 * ------------------------------------------------------------------------ */

/** Convierte "#rrggbb" en [r, g, b]. */
function hexARgb(hex) {
  const limpio = hex.replace("#", "");
  return [
    parseInt(limpio.slice(0, 2), 16),
    parseInt(limpio.slice(2, 4), 16),
    parseInt(limpio.slice(4, 6), 16),
  ];
}

/** Mezcla linealmente dos colores con un factor t ∈ [0, 1]. */
function mezclarColor(colorA, colorB, t) {
  const a = hexARgb(colorA);
  const b = hexARgb(colorB);
  const mezcla = a.map((canal, i) => Math.round(canal + (b[i] - canal) * t));
  return `rgb(${mezcla[0]}, ${mezcla[1]}, ${mezcla[2]})`;
}

/**
 * Muestrea una rampa de color en la posición t ∈ [0, 1].
 * @param {string[]} rampa  Lista de colores ordenados de menor a mayor.
 * @param {number}   t      Posición normalizada dentro de la rampa.
 */
function colorRampa(rampa, t) {
  const valor = Math.min(1, Math.max(0, t));
  const tramos = rampa.length - 1;
  const posicion = valor * tramos;
  const indice = Math.min(tramos - 1, Math.floor(posicion));
  return mezclarColor(rampa[indice], rampa[indice + 1], posicion - indice);
}

/* ------------------------------------------------------------------------ *
 * Escalas de valor                                                          *
 * ------------------------------------------------------------------------ */

/**
 * Construye una función de normalización [min, max] → [0, 1].
 * @param {number} min
 * @param {number} max
 * @param {"lineal"|"log"} tipo
 * @param {number} maximo  Máximo absoluto observado (tope de la escala).
 */
function crearNormalizador(min, max, tipo, maximo) {
  const tope = Math.max(maximo, max, 1);

  if (tipo === "log") {
    // Desplazamos para evitar log(0) y conservamos el orden de magnitud.
    const desplazamiento = 1;
    const logMin = Math.log10(Math.max(min + desplazamiento, 1));
    const logMax = Math.log10(tope + desplazamiento);
    const rango = Math.max(logMax - logMin, 1e-9);
    return (valor) => (Math.log10(valor + desplazamiento) - logMin) / rango;
  }

  const rango = Math.max(tope - min, 1e-9);
  return (valor) => (valor - min) / rango;
}

/* ------------------------------------------------------------------------ *
 * Intensidad de color                                                       *
 * ------------------------------------------------------------------------ */

/**
 * Ajusta la saturación de un color según la intensidad solicitada.
 * A intensidad 0 el color se acerca a un gris uniforme; a 100 conserva
 * la rampa original completa.
 *
 * @param {string} color   Color "rgb(r, g, b)" o "#rrggbb".
 * @param {number} factor  Intensidad ∈ [0, 1].
 */
function aplicarIntensidad(color, factor) {
  if (factor >= 0.999) return color;

  let rgb;
  if (color.startsWith("rgb")) {
    rgb = color
      .replace(/[^\d,]/g, "")
      .split(",")
      .map(Number);
  } else {
    rgb = hexARgb(color);
  }

  const luminancia = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2];
  const gris = [luminancia, luminancia, luminancia];

  // La intensidad mínima deja un 35 % de color para no perder la escala.
  const mezcla = 0.35 + 0.65 * factor;
  const final = rgb.map((canal, i) =>
    Math.round(gris[i] + (canal - gris[i]) * mezcla)
  );

  return `rgb(${final[0]}, ${final[1]}, ${final[2]})`;
}

/* ------------------------------------------------------------------------ *
 * Formato de valores                                                        *
 * ------------------------------------------------------------------------ */

/** Etiquetas legibles para números grandes (1.2 mil, 3.4 M, 5.1 MM). */
const ESCALAS_NUMERO = [
  { limite: 1e12, sufijo: " B", decimales: 1 },
  { limite: 1e9, sufijo: " MM", decimales: 1 },
  { limite: 1e6, sufijo: " M", decimales: 1 },
  { limite: 1e3, sufijo: " mil", decimales: 0 },
];

/**
 * Formatea un valor según el tipo declarado en los metadatos.
 * Los montos ya vienen en pesos mexicanos desde el dataset.
 * @param {number} valor
 * @param {"entero"|"decimal"|"moneda"} formato
 */
function formatearValor(valor, formato = "entero") {
  if (valor === null || valor === undefined || Number.isNaN(valor)) {
    return "Sin datos";
  }

  if (formato === "moneda") {
    if (valor === 0) return "$0 MXN";
    const abs = Math.abs(valor);
    const escala = ESCALAS_NUMERO.find((e) => abs >= e.limite);
    if (escala) {
      const reducido = valor / escala.limite;
      const decimales = Math.abs(reducido) < 10 ? 2 : escala.decimales;
      return `$${reducido.toFixed(decimales)}${escala.sufijo} MXN`;
    }
    return `$${valor.toLocaleString("es-MX")} MXN`;
  }

  if (formato === "decimal") {
    if (Math.abs(valor) >= 1000) return formatearValor(valor, "entero");
    return valor.toLocaleString("es-MX", { maximumFractionDigits: 1 });
  }

  // Formato entero con separador de miles.
  return Math.round(valor).toLocaleString("es-MX");
}

window.Escalas = {
  crearNormalizador,
  colorRampa,
  aplicarIntensidad,
  formatearValor,
  mezclarColor,
};
