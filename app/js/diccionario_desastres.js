/* =========================================================================
   diccionario_desastres.js — Traducción de tipos de desastre EN -> ES
   ========================================================================= */

const DICCIONARIO_DESASTRES = {
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
  "Animal incident": "Incidente con animales"
};

function traducirTipoDesastre(tipo) {
  if (!tipo) return tipo;
  return DICCIONARIO_DESASTRES[tipo] || tipo;
}

window.DICCIONARIO_DESASTRES = DICCIONARIO_DESASTRES;
window.traducirTipoDesastre = traducirTipoDesastre;
