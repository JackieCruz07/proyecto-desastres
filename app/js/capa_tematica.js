/* =========================================================================
   capa_tematica.js — Capa de visualización temática sobre el mapa 3D
   -------------------------------------------------------------------------
   Este es el módulo central de la Actividad 3. Construye y actualiza las
   capas de MapLibre GL que representan las variables seleccionadas:

     1. relleno-coloreado   → coloración (mapa de calor por país)
     2. relleno-relieve     → elevación y deformación de la superficie
                              (fill-extrusion: el polígono se levanta en 3D)
     3. borde-territorio    → contorno de los territorios
     4. resalte             → territorio seleccionado

   Terminología:
     * Elevación   → prisma vertical proporcional al valor (más alto = mayor).
     * Deformación → relieve continuo que comprime visualmente el territorio
                     hacia arriba buscando una superficie ondulada.
   ========================================================================= */

const CapaTematica = (() => {
  const IDs = {
    origen: "territorios",
    rellenoColor: "relleno-coloreado",
    rellenoRelieve: "relleno-relieve",
    borde: "borde-territorio",
    resalte: "resalte-territorio",
  };

  /* Estado interno de la capa temática. */
  const estado = {
    variableColor: "eventos",
    variableAltura: "fallecidos",
    recurso: "elevacion", // "elevacion" | "deformacion" | "ninguno"
    intensidad: 0.6,
    alturaMaxima: 400000,
    escala: "lineal",
    mostrarSinDatos: true,
    metadatos: null,
    seleccionado: null,
    territorios: [],
    normalizadorColor: () => 0,
    normalizadorAltura: () => 0,
    estadisticosOverride: null,
    respaldo: null,
  };

  let mapa = null;

  /* ---------------------------------------------------------------------- *
   * Utilidades                                                             *
   * ---------------------------------------------------------------------- */

  /** Devuelve la definición de una variable desde los metadatos. */
  function definicion(variable) {
    return estado.metadatos.variables[variable];
  }

  /**
   * Estadísticos vigentes de una variable. Si hay un filtro activo se usan
   * los que se calcularon con los datos filtrados, para que la escala de
   * color se adapte a lo que el usuario está viendo.
   */
  function estadisticos(variable) {
    const filtrados = estado.estadisticosOverride;
    if (filtrados && filtrados[variable]) return filtrados[variable];
    return definicion(variable).estadisticos;
  }

  /** Calcula el rango efectivo de la escala para una variable. */
  function rangoEscala(variable, tipoEscala) {
    const stats = estadisticos(variable);
    // El mínimo se fija en 0 para incluir territorios con valor nulo.
    const min = 0;
    // El máximo se acota al percentil 99 para que un solo valor extremo
    // no aplane el resto de la escala.
    const max = stats.p99 || stats.max || 1;
    return { min, max, tope: stats.max || max };
  }

  /**
   * Color de un territorio para la variable de coloración.
   * @param {object} territorio  Propiedades del feature.
   */
  function colorTerritorio(territorio) {
    const valor = territorio[estado.variableColor];

    if (valor === null || valor === undefined) {
      return CONFIG.colores.sinDatos;
    }

    const rampa = CONFIG.paletas[estado.variableColor].colores;
    const t = estado.normalizadorColor(valor);
    return Escalas.aplicarIntensidad(
      Escalas.colorRampa(rampa, t),
      estado.intensidad
    );
  }

  /**
   * Altura en metros de un territorio para el recurso 3D activo.
   * @param {object} territorio  Propiedades del feature.
   */
  function alturaTerritorio(territorio) {
    if (estado.recurso === "ninguno") return 0;

    const valor = territorio[estado.variableAltura];

    if (valor === null || valor === undefined) {
      // Los territorios sin datos conservan una base mínima visible.
      return estado.mostrarSinDatos ? 12000 : 0;
    }

    const t = estado.normalizadorAltura(valor);

    if (estado.recurso === "deformacion") {
      // Deformación: relieve continuo desde una base para dar sensación
      // de superficie ondulada (no prismas altos, sino un terreno temático).
      const base = 8000;
      return base + t * (estado.alturaMaxima * 0.42);
    }

    // Elevación: prisma proporcional al valor.
    const base = 4000;
    return base + t * estado.alturaMaxima;
  }

  /* ---------------------------------------------------------------------- *
   * Construcción de las capas                                              *
   * ---------------------------------------------------------------------- */

  /** Devuelve la expresión MapLibre de color por valor temático. */
  function expresionColor() {
    const expresion = ["case"];

    // Los territorios sin datos usan un color neutro.
    const sinDatos = ["==", ["get", estado.variableColor], null];
    expresion.push(sinDatos, CONFIG.colores.sinDatos);

    // Valor mínimo y máximo de la escala, para la interpolación.
    const pasos = 12;
    const interpolacion = ["interpolate", ["linear"], ["get", estado.variableColor]];

    for (let i = 0; i <= pasos; i += 1) {
      const t = i / pasos;
      const valor = valorEnPosicion(estado.variableColor, t);
      interpolacion.push(
        valor,
        Escalas.aplicarIntensidad(
          Escalas.colorRampa(CONFIG.paletas[estado.variableColor].colores, t),
          estado.intensidad
        )
      );
    }

    expresion.push(interpolacion);
    return expresion;
  }

  /**
   * Valor numérico correspondiente a una posición t ∈ [0,1] de la escala.
   * Permite construir las paradas de la expresión de interpolación.
   */
  function valorEnPosicion(variable, t) {
    const { min, max } = rangoEscala(variable, estado.escala);
    if (estado.escala === "log") {
      const logMin = Math.log10(Math.max(min + 1, 1));
      const logMax = Math.log10(max + 1);
      return Math.pow(10, logMin + t * (logMax - logMin)) - 1;
    }
    return min + t * (max - min);
  }

  /** Añade el origen de datos y todas las capas temáticas al mapa. */
  function agregarCapas(geojson) {
    mapa.addSource(IDs.origen, {
      type: "geojson",
      data: geojson,
    });

    // --- 1. Coloración -------------------------------------------------
    mapa.addLayer({
      id: IDs.rellenoColor,
      type: "fill",
      source: IDs.origen,
      paint: {
        "fill-color": expresionColor(),
        "fill-opacity": 0.9,
      },
    });

    // --- 2. Elevación / deformación de la superficie -------------------
    mapa.addLayer({
      id: IDs.rellenoRelieve,
      type: "fill-extrusion",
      source: IDs.origen,
      paint: {
        "fill-extrusion-color": expresionColor(),
        "fill-extrusion-height": ["get", "altura"],
        "fill-extrusion-base": 0,
        "fill-extrusion-opacity": 0.88,
      },
    });

    // --- 3. Bordes territoriales ---------------------------------------
    mapa.addLayer({
      id: IDs.borde,
      type: "line",
      source: IDs.origen,
      paint: {
        "line-color": CONFIG.colores.bordeTerritorio,
        "line-width": [
          "interpolate",
          ["linear"],
          ["zoom"],
          0,
          0.15,
          3,
          0.6,
          6,
          1.1,
        ],
        "line-opacity": 0.55,
      },
    });

    // --- 4. Resalte del territorio seleccionado ------------------------
    mapa.addLayer({
      id: IDs.resalte,
      type: "line",
      source: IDs.origen,
      filter: ["==", ["get", "codigo"], estado.seleccionado || "__ninguno__"],
      paint: {
        "line-color": "#0f172a",
        "line-width": 2.2,
      },
    });
  }

  /* ---------------------------------------------------------------------- *
   * Actualización de la geometría con alturas                              *
   * ---------------------------------------------------------------------- */

  /** Recalcula las alturas de todos los territorios y refresca el origen. */
  function recalcularAlturas() {
    const datos = estado.geojson;
    if (!datos) return;

    datos.features.forEach((feature) => {
      feature.properties.altura = alturaTerritorio(feature.properties);
      feature.properties.color = colorTerritorio(feature.properties);
    });

    const origen = mapa.getSource(IDs.origen);
    if (origen) origen.setData(datos);
  }

  /* ---------------------------------------------------------------------- *
   * Reconstrucción completa tras un cambio de variable                     *
   * ---------------------------------------------------------------------- */

  /** Recalcula normalizadores, expresiones y alturas. */
  function refrescar() {
    // Normalizador de la variable de color.
    const rangoColor = rangoEscala(estado.variableColor, estado.escala);
    estado.normalizadorColor = Escalas.crearNormalizador(
      rangoColor.min,
      rangoColor.max,
      estado.escala,
      rangoColor.tope
    );

    // Normalizador de la variable de altura (permite log) usando los
    // estadísticos p99 como tope visual.
    const rangoAltura = rangoEscala(estado.variableAltura, estado.escala);
    estado.normalizadorAltura = Escalas.crearNormalizador(
      rangoAltura.min,
      rangoAltura.max,
      estado.escala,
      rangoAltura.tope
    );

    // Actualiza el color de la capa de relleno.
    mapa.setPaintProperty(IDs.rellenoColor, "fill-color", expresionColor());
    mapa.setPaintProperty(
      IDs.rellenoRelieve,
      "fill-extrusion-color",
      expresionColor()
    );

    // Actualiza alturas.
    recalcularAlturas();
    mapa.setPaintProperty(IDs.rellenoRelieve, "fill-extrusion-height", [
      "get",
      "altura",
    ]);

    // Visibilidad de los territorios sin datos.
    const filtroSinDatos = [
      "any",
      ["!=", ["get", estado.variableColor], null],
      ["!=", ["get", estado.variableAltura], null],
    ];
    const filtro = estado.mostrarSinDatos
      ? ["literal", true]
      : filtroSinDatos;
    mapa.setFilter(IDs.rellenoColor, filtro);
    mapa.setFilter(IDs.rellenoRelieve, filtro);

    // Leyenda y paleta.
    const rampa = CONFIG.paletas[estado.variableColor].colores;
    Leyenda.actualizar({
      titulo: definicion(estado.variableColor).etiqueta,
      unidad: definicion(estado.variableColor).unidad,
      formato: definicion(estado.variableColor).formato,
      rampa: CONFIG.paletas[estado.variableColor].nombre,
      colores: estado.mostrarSinDatos ? rampa : rampa,
      min: rangoColor.min,
      max: rangoColor.max,
    });
    Leyenda.pintarPaleta(rampa);
    Leyenda.marcarRecursos({
      color: true,
      elevacion: estado.recurso === "elevacion",
      deformacion: estado.recurso === "deformacion",
    });

    document.getElementById("nota-escala").textContent =
      `Escala ${estado.escala === "log" ? "logarítmica" : "lineal"} · ` +
      `rampa ${CONFIG.paletas[estado.variableColor].nombre} · ` +
      `intensidad ${Math.round(estado.intensidad * 100)} %`;

    document.getElementById("insignia-modo").textContent = [
      definicion(estado.variableColor).etiqueta,
      estado.recurso === "elevacion"
        ? "elevación"
        : estado.recurso === "deformacion"
        ? "deformación"
        : null,
    ]
      .filter(Boolean)
      .join(" · ");
  }

  /* ---------------------------------------------------------------------- *
   * API pública                                                            *
   * ---------------------------------------------------------------------- */

  return {
    estado,

    /** Inicializa la capa sobre una instancia de mapa ya creada. */
    iniciar(instanciaMapa, geojson, metadatos) {
      mapa = instanciaMapa;
      estado.geojson = geojson;
      estado.metadatos = metadatos;
      estado.territorios = geojson.features.map((f) => f.properties);
      estado.escala = CONFIG.escalaAutomatica[estado.variableColor] || "lineal";

      // Respaldo de los valores originales (periodo completo, todos los tipos)
      // para poder restaurarlos al quitar los filtros.
      estado.respaldo = {};
      geojson.features.forEach((f) => {
        const p = f.properties;
        estado.respaldo[p.codigo] = {
          eventos: p.eventos,
          fallecidos: p.fallecidos,
          afectados: p.afectados,
          dano_ajustado: p.dano_ajustado,
          prom_fallecidos: p.prom_fallecidos,
          prom_afectados: p.prom_afectados,
        };
      });

      agregarCapas(geojson);
      refrescar();
    },

    /** Cambia la variable representada por el color. */
    setVariableColor(variable) {
      estado.variableColor = variable;
      estado.escala = CONFIG.escalaAutomatica[variable] || estado.escala;
      refrescar();
    },

    /** Cambia la variable representada por la altura. */
    setVariableAltura(variable) {
      estado.variableAltura = variable;
      refrescar();
    },

    /** Cambia el recurso 3D: elevacion | deformacion | ninguno. */
    setRecurso(recurso) {
      estado.recurso = recurso;
      mapa.setLayoutProperty(
        IDs.rellenoRelieve,
        "visibility",
        recurso === "ninguno" ? "none" : "visible"
      );
      refrescar();
    },

    /** Ajusta la intensidad de color ∈ [0, 1]. */
    setIntensidad(valor) {
      estado.intensidad = valor;
      refrescar();
    },

    /** Ajusta la altura máxima del relieve en metros. */
    setAlturaMaxima(metros) {
      estado.alturaMaxima = metros;
      recalcularAlturas();
    },

    /** Cambia la escala de la variable: lineal | log. */
    setEscala(tipo) {
      estado.escala =
        tipo === "auto"
          ? CONFIG.escalaAutomatica[estado.variableColor] || "lineal"
          : tipo;
      refrescar();
    },

    /** Muestra u oculta los territorios sin indicadores. */
    setMostrarSinDatos(mostrar) {
      estado.mostrarSinDatos = mostrar;
      refrescar();
    },

    /** Resalta visualmente el territorio seleccionado. */
    setSeleccionado(codigo) {
      estado.seleccionado = codigo;
      mapa.setFilter(IDs.resalte, [
        "==",
        ["get", "codigo"],
        codigo || "__ninguno__",
      ]);
    },

    /** Devuelve las propiedades de un territorio por su código. */
    territorio(codigo) {
      return estado.territorios.find((t) => t.codigo === codigo) || null;
    },

    /**
     * Aplica al mapa un conjunto de valores ya filtrados por periodo y tipo.
     * @param {object} valoresPorPais  { ISO: {eventos, fallecidos, ...} }
     * @param {object} stats           Estadísticos recalculados por variable.
     */
    setFiltro(valoresPorPais, stats) {
      if (!estado.geojson) return;

      estado.geojson.features.forEach((feature) => {
        const p = feature.properties;
        const valor = valoresPorPais[p.codigo];

        if (valor) {
          p.eventos = valor.eventos;
          p.fallecidos = valor.fallecidos;
          p.afectados = valor.afectados;
          p.dano_ajustado = valor.dano_mxn;
          p.prom_fallecidos = valor.eventos ? valor.fallecidos / valor.eventos : 0;
          p.prom_afectados = valor.eventos ? valor.afectados / valor.eventos : 0;
        } else {
          p.eventos = null;
          p.fallecidos = null;
          p.afectados = null;
          p.dano_ajustado = null;
          p.prom_fallecidos = null;
          p.prom_afectados = null;
        }
      });

      estado.estadisticosOverride = stats || null;
      refrescar();
    },

    /** Vuelve a los valores del periodo completo y todos los tipos. */
    quitarFiltro() {
      if (!estado.geojson || !estado.respaldo) return;

      estado.geojson.features.forEach((feature) => {
        const p = feature.properties;
        const original = estado.respaldo[p.codigo];
        if (!original) return;
        Object.assign(p, original);
      });

      estado.estadisticosOverride = null;
      refrescar();
    },

    /** Estadísticos actualmente en uso (filtrados o globales). */
    estadisticos,

    /** Expone el color calculado (útil para la leyenda del tooltip). */
    colorDe(codigo) {
      const territorio = this.territorio(codigo);
      return territorio ? colorTerritorio(territorio) : CONFIG.colores.sinDatos;
    },
  };
})();

window.CapaTematica = CapaTematica;
