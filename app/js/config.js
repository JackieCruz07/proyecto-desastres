/* =========================================================================
   config.js — Configuración visual y de la capa temática
   -------------------------------------------------------------------------
   Centraliza rutas, estilos del mapa y las paletas de color asociadas a
   cada variable temática. Ningún otro módulo define colores ni rutas.
   ========================================================================= */

const CONFIG = {
  /* Ruta al GeoJSON preparado por src/capa_tematica.py */
  rutaDatos: "datos/paises.geojson",
  rutaMetadatos: "datos/metadatos.json",

  /* Estado inicial de la vista 3D */
  vistaInicial: {
    center: [-40, 22],
    zoom: 1.5,
    pitch: 42,
    bearing: 0,
  },

  /* Mapa base: globo limpio SIN teselas externas.
     Se eliminó el mapa base remoto (antes CARTO) porque ahora exige una
     API key y mostraba el aviso "API key required" sobre el mapa. En su
     lugar se dibuja un globo azul marino limpio: la capa temática es la única
     protagonista y la aplicación no depende de teselas externas ni de
     internet para mostrar el mapa. */
  estiloBase: {
    version: 8,
    sources: {},
    layers: [
      { id: "fondo", type: "background", paint: { "background-color": "#7aa3d6" } },
    ],
  },

  /* Fondo de página */
  colores: {
    sinDatos: "#cbd5e1",
    bordeTerritorio: "#475569",
    oceano: "#7aa3d6",
    atmosfera: "#9bb8e0",
  },

  /* Tipo de cambio aproximado para mostrar daño económico en MXN */
  tipoCambioMXN: 20.8,

  /* Paletas temáticas: cada variable tiene su propia rampa perceptual.
     Como el mapa base es claro, cada rampa va de un tono suave (valores
     bajos) a un tono intenso (valores altos), para que el relieve
     temático se lea bien sobre el fondo claro. */
  paletas: {
    eventos: {
      nombre: "YlOrRd",
      colores: [
        "#fff7bc",
        "#fec44f",
        "#fe9929",
        "#ec7014",
        "#cc4c02",
        "#993404",
        "#662506",
      ],
    },
    fallecidos: {
      nombre: "Reds",
      colores: ["#fee5d9", "#fcae91", "#fb6a4a", "#de2d26", "#a50f15", "#67000d"],
    },
    afectados: {
      nombre: "Blues",
      colores: ["#eff3ff", "#c6dbef", "#9ecae1", "#6baed6", "#3182bd", "#08519c"],
    },
    dano_ajustado: {
      nombre: "Viridis",
      colores: ["#fde725", "#5ec962", "#21918c", "#3b528b", "#440154"],
    },
    prom_fallecidos: {
      nombre: "Magma",
      colores: ["#fcfdbf", "#fe9f6d", "#de4968", "#8c2981", "#3b0f70", "#000004"],
    },
    prom_afectados: {
      nombre: "Teal",
      colores: ["#ccfbf1", "#99f6e4", "#2dd4bf", "#0d9488", "#115e59", "#042f2e"],
    },
  },

  /* Variables que por su enorme rango se representan mejor en escala log. */
  escalaAutomatica: {
    eventos: "lineal",
    fallecidos: "log",
    afectados: "log",
    dano_ajustado: "log",
    prom_fallecidos: "log",
    prom_afectados: "log",
  },
};

/* Evita que el archivo se cargue dos veces por error. */
window.CONFIG = CONFIG;
