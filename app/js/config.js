/* =========================================================================
   config.js — Configuración visual y de la capa temática
   -------------------------------------------------------------------------
   Centraliza rutas, estilos del mapa y las paletas de color asociadas a
   cada variable temática. Ningún otro módulo define colores ni rutas.
   ========================================================================= */

const CONFIG = {
  /* Rutas de los archivos preparados por los módulos de src/ */
  rutaDatos: "datos/paises.geojson",
  rutaMetadatos: "datos/metadatos.json",
  rutaFiltros: "datos/filtros.json",
  rutaSocio: "datos/paises_socio.json",
  rutaEventos: "datos/eventos_pais.json",
  rutaOwid: "datos/owid.json",
  rutaIncendios: "datos/incendios_mexico.json",
  rutaPuntosIncendios: "datos/incendios_puntos.geojson",

  /* Estado inicial de la vista 3D */
  vistaInicial: {
    center: [-60, 12],
    zoom: 1.95,
    pitch: 22,
    bearing: 0,
  },

  /* Mapa base: globo limpio SIN teselas externas.
     El océano va en azul profundo para separarse del fondo púrpura de la
     página y el relieve temático va de tonos claros a intensos. */
  estiloBase: {
    version: 8,
    sources: {},
    layers: [
      { id: "fondo", type: "background", paint: { "background-color": "#1b4576" } },
    ],
  },

  /* Colores del mapa y del globo */
  colores: {
    sinDatos: "#b9aecf",
    bordeTerritorio: "#3b2a63",
    oceano: "#1b4576",
    cielo: "#2b1055",
    atmosfera: "#7c3aed",
  },

  /* Moneda del proyecto: los montos del dataset ya están en pesos mexicanos
     (la conversión desde USD se hace en src/moneda.py). */
  moneda: "MXN",

  /* Paletas temáticas: cada variable tiene su propia rampa perceptual.
     Como el mapa base es claro, cada rampa va de un tono suave (valores
     bajos) a un tono intenso (valores altos), para que el relieve
     temático se lea bien sobre el fondo claro. */
  paletas: {
    eventos: {
      nombre: "Ámbar",
      colores: ["#fff2cc", "#ffd977", "#ffb71b", "#ff8a5f", "#ee3e29", "#b01e10"],
    },
    fallecidos: {
      nombre: "Coral",
      colores: ["#fde8ec", "#f9b3be", "#fa8a9a", "#ee3e29", "#b31f14", "#6d0f08"],
    },
    afectados: {
      nombre: "Lila",
      colores: ["#f1e9fb", "#d3bdf0", "#ad8ade", "#8256c9", "#5b2fa8", "#38146f"],
    },
    dano_ajustado: {
      nombre: "Amanecer",
      colores: ["#fff6e0", "#ffd166", "#ffb71b", "#fa8a9a", "#a855c9", "#4c1d95"],
    },
    prom_fallecidos: {
      nombre: "Terracota",
      colores: ["#fff1e8", "#ffc8a8", "#ff8a5f", "#ee3e29", "#a81c10", "#5e0d06"],
    },
    prom_afectados: {
      nombre: "Violeta",
      colores: ["#f5ecff", "#dcc6f5", "#b98ee6", "#8b5cc9", "#5b2fa8", "#2c0f5c"],
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
