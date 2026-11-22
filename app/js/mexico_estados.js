/* =========================================================================
   mexico_estados.js — Vista de México por estados (CENAPRED / ANR)
   -------------------------------------------------------------------------
   Carga los indicadores estatales generados por src/mexico_estados.py y los
   dibuja en un mapa coroplético con MapLibre. Permite filtrar por variable,
   rango de años y tipo de fenómeno, consultar la ficha de cada estado y
   abrir las cuatro fichas de desastres destacadas.

   Depende de config.js (paletas) y escalas.js (rampas y formato).
   ========================================================================= */

(() => {
  "use strict";

  const RUTAS = {
    datos: "datos/mexico_estados.json",
    geo: "datos/estados_mexico.geojson",
  };

  const VARIABLES = {
    dano_mxn: {
      etiqueta: "Daños",
      unidad: "pesos mexicanos",
      paleta: "dano_ajustado",
      escala: "log",
      formato: "moneda",
    },
    defunciones: {
      etiqueta: "Defunciones",
      unidad: "personas",
      paleta: "fallecidos",
      escala: "log",
      formato: "entero",
    },
    afectados: {
      etiqueta: "Población afectada",
      unidad: "personas",
      paleta: "afectados",
      escala: "log",
      formato: "entero",
    },
    eventos: {
      etiqueta: "Eventos registrados",
      unidad: "eventos",
      paleta: "eventos",
      escala: "lineal",
      formato: "entero",
    },
    viviendas: {
      etiqueta: "Viviendas dañadas",
      unidad: "viviendas",
      paleta: "prom_afectados",
      escala: "log",
      formato: "entero",
    },
  };

  const INDICADORES = [
    ["dano_mxn", "Daños"],
    ["defunciones", "Defunciones"],
    ["afectados", "Afectados"],
    ["eventos", "Eventos"],
    ["viviendas", "Viviendas"],
  ];

  const estado = {
    datos: null,
    geo: null,
    mapa: null,
    iso: null,
    filtros: { variable: "dano_mxn", min: 2000, max: 2024, tipo: "todos" },
    agregados: {},
    nacional: null,
    cargado: false,
    abierto: false,
    /* Parámetros de capa temática (equivalentes al mapa global) */
    variableAltura: "defunciones",
    recurso: "elevacion", // "elevacion" | "deformacion" | "ninguno"
    intensidad: 0.7,
    alturaMaxima: 120000,
    escala: "auto", // "auto" | "lineal" | "log"
  };

  const ui = {};

  /** Expone la instancia del mapa para herramientas externas (capturas). */
  window.__mapaMexico = () => estado.mapa;

  /* ---------------------------------------------------------------------- *
   * 1. Utilidades de formato                                               *
   * ---------------------------------------------------------------------- */

  const numero = new Intl.NumberFormat("es-MX");

  function formatear(variable, valor) {
    if (valor === null || valor === undefined || Number.isNaN(valor)) return "—";
    return Escalas.formatearValor(valor, VARIABLES[variable].formato);
  }

  function formatearSimple(valor) {
    if (valor === null || valor === undefined || Number.isNaN(valor)) return "—";
    return numero.format(Math.round(valor));
  }

  function porcentaje(valor, total) {
    if (!total) return "0 %";
    return `${((100 * valor) / total).toFixed(1)} %`;
  }

  function escapar(texto) {
    return String(texto)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function nombreEstado(iso) {
    return (estado.datos.estados[iso] || {}).nombre || iso;
  }

  /** Área aproximada de un anillo de coordenadas (grados cuadrados). */
  function areaAnillo(anillo) {
    let suma = 0;
    for (let i = 0; i < anillo.length; i += 1) {
      const [x1, y1] = anillo[i];
      const [x2, y2] = anillo[(i + 1) % anillo.length];
      suma += x1 * y2 - x2 * y1;
    }
    return Math.abs(suma / 2);
  }

  /**
   * Conserva solo el polígono principal de cada estado.
   * Elimina islas y fragmentos pequeños que quedaban flotando en el mapa.
   */
  function limpiarIslas(geo) {
    const features = geo.features.map((rasgo) => {
      if (rasgo.geometry.type !== "MultiPolygon") return rasgo;
      const partes = rasgo.geometry.coordinates
        .map((parte) => ({ parte, area: areaAnillo(parte[0]) }))
        .sort((a, b) => b.area - a.area);
      if (!partes.length) return rasgo;
      return {
        ...rasgo,
        geometry: { ...rasgo.geometry, coordinates: [partes[0].parte] },
      };
    });
    return { ...geo, features };
  }

  /* ---------------------------------------------------------------------- *
   * 2. Agregación con filtros                                              *
   * ---------------------------------------------------------------------- */

  function recalcular() {
    const { serie } = estado.datos;
    const { min, max, tipo } = estado.filtros;
    const agregados = {};
    const total = {
      eventos: 0,
      dano_mxn: 0,
      defunciones: 0,
      afectados: 0,
      viviendas: 0,
    };
    let estadosConDatos = 0;

    Object.keys(serie).forEach((iso) => {
      const acc = {
        eventos: 0,
        dano_mxn: 0,
        defunciones: 0,
        afectados: 0,
        viviendas: 0,
      };
      serie[iso].forEach((fila) => {
        const [anio, tipoFila, dano, def, afectados, viviendas] = fila;
        if (anio < min || anio > max) return;
        if (tipo !== "todos" && tipoFila !== tipo) return;
        acc.eventos += 1;
        acc.dano_mxn += dano;
        acc.defunciones += def;
        acc.afectados += afectados;
        acc.viviendas += viviendas;
      });
      agregados[iso] = acc;
      if (acc.eventos > 0) estadosConDatos += 1;
      total.eventos += acc.eventos;
      total.dano_mxn += acc.dano_mxn;
      total.defunciones += acc.defunciones;
      total.afectados += acc.afectados;
      total.viviendas += acc.viviendas;
    });

    estado.agregados = agregados;
    estado.nacional = { ...total, estadosConDatos };
  }

  function valoresDe(variable) {
    return Object.keys(estado.agregados)
      .map((iso) => estado.agregados[iso][variable] || 0)
      .filter((valor) => valor > 0);
  }

  function rangoDe(variable) {
    const valores = valoresDe(variable);
    if (!valores.length) return { min: 0, max: 1 };
    return {
      min: Math.min(...valores),
      max: Math.max(...valores),
    };
  }

  function rankingDe(variable) {
    return Object.keys(estado.agregados)
      .filter((iso) => (estado.agregados[iso][variable] || 0) > 0)
      .sort((a, b) => estado.agregados[b][variable] - estado.agregados[a][variable]);
  }

  function normalizador(variable) {
    const cfg = VARIABLES[variable];
    const rango = rangoDe(variable);
    if (cfg.escala === "log") {
      return Escalas.crearNormalizador(Math.max(rango.min, 1), rango.max, "log", rango.max);
    }
    return Escalas.crearNormalizador(0, rango.max, "lineal", rango.max);
  }

  /* ---------------------------------------------------------------------- *
   * 4a. Relieve 3D (equivalente al mapa global)                            *
   * ---------------------------------------------------------------------- */

  /** Rango efectivo para la variable de altura. */
  function rangoEscalaAltura(variable) {
    const valores = valoresDe(variable);
    if (!valores.length) return { min: 0, max: 1, tope: 1 };
    const min = 0;
    const max = Math.max(...valores);
    return { min, max, tope: max };
  }

  /** Normalizador de la variable de altura. */
  function normalizadorAltura(variable) {
    const { min, max, tope } = rangoEscalaAltura(variable);
    const escala = estado.escala === "auto" ? VARIABLES[variable].escala : estado.escala;
    return Escalas.crearNormalizador(min, max, escala, tope);
  }

  /** Altura en metros de un estado para el recurso 3D activo. */
  function alturaTerritorio(valor, normalizarAltura) {
    if (estado.recurso === "ninguno") return 0;

    if (valor === null || valor === undefined || valor <= 0) {
      // Los estados sin datos conservan una base mínima visible.
      return estado.mostrarSinDatos !== false ? 1500 : 0;
    }

    const t = normalizarAltura(valor);

    if (estado.recurso === "deformacion") {
      const base = 1500;
      return base + t * (estado.alturaMaxima * 0.45);
    }

    // Elevación: prisma proporcional al valor.
    const base = 1500;
    return base + t * estado.alturaMaxima;
  }

  /** Color de un estado para la variable de coloración, con intensidad. */
  function colorTerritorio(valor, variable, normalizar) {
    if (!valor) return CONFIG.colores.sinDatos;
    const paleta = CONFIG.paletas[VARIABLES[variable].paleta].colores;
    const t = normalizar(valor);
    return Escalas.aplicarIntensidad(Escalas.colorRampa(paleta, t), estado.intensidad);
  }

  /* ---------------------------------------------------------------------- *
   * 4. Mapa                                                                *
   * ---------------------------------------------------------------------- */

  function datosPintados() {
    const variable = estado.filtros.variable;
    const alturaVariable = estado.variableAltura;
    const normalizar = normalizador(variable);
    const normalizarAltura = normalizadorAltura(alturaVariable);
    const rasgos = estado.geo.features.map((rasgo) => {
      const iso = rasgo.properties.id;
      const agg = estado.agregados[iso] || {};
      const valor = agg[variable] || 0;
      const alturaValor = agg[alturaVariable] || 0;
      return {
        ...rasgo,
        properties: {
          ...rasgo.properties,
          valor,
          altura: alturaTerritorio(alturaValor, normalizarAltura),
          color: colorTerritorio(valor, variable, normalizar),
        },
      };
    });
    return { type: "FeatureCollection", features: rasgos };
  }

  /* ---------------------------------------------------------------------- *
   * 3. Leyenda                                                             *
   * ---------------------------------------------------------------------- */

  function pintarLeyenda(variable) {
    const cfg = VARIABLES[variable];
    const rango = rangoDe(variable);
    const paleta = CONFIG.paletas[cfg.paleta].colores;

    ui.leyendaTitulo.textContent = cfg.etiqueta;
    ui.leyendaUnidad.textContent = cfg.unidad;

    ui.leyendaBarra.innerHTML = "";
    paleta.forEach((color) => {
      const bloque = document.createElement("span");
      bloque.style.background = color;
      ui.leyendaBarra.appendChild(bloque);
    });

    const etiquetas = [0, 0.5, 1].map((t) => {
      if (cfg.escala === "log") {
        const min = Math.max(rango.min, 1);
        const valor = 10 ** (Math.log10(min) + t * (Math.log10(rango.max) - Math.log10(min))) - 1;
        return formatear(variable, Math.max(0, valor));
      }
      return formatear(variable, rango.max * t);
    });

    ui.leyendaMin.textContent = etiquetas[0];
    ui.leyendaMax.textContent = etiquetas[2];
    ui.leyendaNota.textContent =
      cfg.escala === "log"
        ? `Escala logarítmica · máximo ${formatear(variable, rango.max)}`
        : `Escala lineal · máximo ${formatear(variable, rango.max)}`;
  }

  function crearMapa() {
    estado.mapa = new maplibregl.Map({
      container: "mapa-mexico",
      style: {
        version: 8,
        sources: {},
        layers: [
          { id: "fondo", type: "background", paint: { "background-color": "#fbf8f3" } },
        ],
      },
      center: [-102.2, 23.6],
      zoom: 4.1,
      minZoom: 2.5,
      maxZoom: 9,
      pitch: 35,
      bearing: 0,
      maxPitch: 85,
      attributionControl: false,
    });

    estado.mapa.addControl(
      new maplibregl.NavigationControl({ showCompass: false, visualizePitch: true }),
      "top-right"
    );
    estado.mapa.addControl(
      new maplibregl.ScaleControl({ maxWidth: 120, unit: "metric" }),
      "bottom-right"
    );

    // La luz solo puede aplicarse cuando el estilo ya terminó de cargar.
    estado.mapa.on("style.load", () => {
      estado.mapa.setLight({
        anchor: "viewport",
        position: [0.5, 0, 1],
        color: "#ffffff",
        intensity: 0.15,
      });
    });

    estado.mapa.on("load", () => {
      estado.mapa.addSource("estados", { type: "geojson", data: datosPintados() });

      // --- 1. Coloración -------------------------------------------------
      estado.mapa.addLayer({
        id: "estados-fill",
        type: "fill",
        source: "estados",
        paint: {
          "fill-color": ["get", "color"],
          "fill-opacity": 0.94,
        },
      });

      // --- 2. Relieve 3D (elevación / deformación) -----------------------
      estado.mapa.addLayer({
        id: "estados-relieve",
        type: "fill-extrusion",
        source: "estados",
        paint: {
          "fill-extrusion-color": ["get", "color"],
          "fill-extrusion-height": ["get", "altura"],
          "fill-extrusion-base": 0,
          "fill-extrusion-opacity": 0.88,
          "fill-extrusion-vertical-gradient": false,
        },
      });

      // --- 3. Bordes territoriales ---------------------------------------
      estado.mapa.addLayer({
        id: "estados-line",
        type: "line",
        source: "estados",
        paint: {
          "line-color": "#ffffff",
          "line-width": 1.1,
        },
      });

      // --- 4. Resalte del estado seleccionado ----------------------------
      estado.mapa.addLayer({
        id: "estados-sel",
        type: "line",
        source: "estados",
        filter: ["==", ["get", "id"], estado.iso || ""],
        paint: {
          "line-color": "#38146f",
          "line-width": 2.8,
        },
      });

      conectarMapa();

      // Deja libre el espacio de los controles para que el país no quede debajo.
      const movil = window.matchMedia("(max-width: 900px)").matches;
      estado.mapa.fitBounds(
        [
          [-118.6, 14.2],
          [-86.2, 32.9],
        ],
        {
          padding: { top: 20, bottom: 30, left: movil ? 20 : 390, right: 20 },
          duration: 0,
        }
      );
    });
  }

  function conectarMapa() {
    const mapa = estado.mapa;

    mapa.on("mousemove", "estados-fill", (evento) => {
      const rasgo = evento.features[0];
      const iso = rasgo.properties.id;
      const variable = estado.filtros.variable;
      const valor = (estado.agregados[iso] || {})[variable] || 0;
      const posicion = rankingDe(variable).indexOf(iso) + 1;

      mapa.getCanvas().style.cursor = "pointer";
      ui.tooltip.innerHTML = `
        <strong>${escapar(nombreEstado(iso))}</strong>
        <span class="tooltip__fila">${escapar(VARIABLES[variable].etiqueta)} <b>${formatear(
        variable,
        valor
      )}</b></span>
        <span class="tooltip__fila">Lugar nacional <b>${posicion ? `#${posicion}` : "—"}</b></span>
      `;
      ui.tooltip.style.left = `${evento.point.x + 16}px`;
      ui.tooltip.style.top = `${evento.point.y + 16}px`;
      ui.tooltip.classList.add("visible");
      ui.tooltip.setAttribute("aria-hidden", "false");
    });

    mapa.on("mouseleave", "estados-fill", () => {
      mapa.getCanvas().style.cursor = "";
      ui.tooltip.classList.remove("visible");
      ui.tooltip.setAttribute("aria-hidden", "true");
    });

    mapa.on("click", "estados-fill", (evento) => {
      seleccionar(evento.features[0].properties.id);
    });
  }

  function refrescarMapa() {
    if (!estado.mapa || !estado.mapa.getSource("estados")) return;
    estado.mapa.getSource("estados").setData(datosPintados());
    estado.mapa.setFilter("estados-sel", ["==", ["get", "id"], estado.iso || ""]);
    pintarLeyenda(estado.filtros.variable);

    // Ajustar visibilidad del relieve según el recurso activo.
    const mostrarRelieve = estado.recurso !== "ninguno";
    estado.mapa.setLayoutProperty(
      "estados-relieve",
      "visibility",
      mostrarRelieve ? "visible" : "none"
    );
  }

  function seleccionar(iso) {
    estado.iso = iso;
    if (estado.mapa && estado.mapa.getLayer("estados-sel")) {
      estado.mapa.setFilter("estados-sel", ["==", ["get", "id"], iso || ""]);
    }
    pintarEstado();
    if (ui.panel) {
      ui.panel.insertBefore(ui.estado, ui.nacional);
      ui.panel.scrollTop = 0;
    }
  }

  function enfocarEstado(iso) {
    seleccionar(iso);
    if (!estado.mapa) return;
    const rasgo = estado.geo.features.find((f) => f.properties.id === iso);
    if (!rasgo) return;
    const caja = cajaDe(rasgo.geometry.coordinates);
    estado.mapa.fitBounds(caja, { padding: 70, duration: 700, maxZoom: 7.5 });
  }

  function cajaDe(coordenadas) {
    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    const recorrer = (punto) => {
      if (typeof punto[0] === "number") {
        minX = Math.min(minX, punto[0]);
        maxX = Math.max(maxX, punto[0]);
        minY = Math.min(minY, punto[1]);
        maxY = Math.max(maxY, punto[1]);
        return;
      }
      punto.forEach(recorrer);
    };
    recorrer(coordenadas);
    return [
      [minX, minY],
      [maxX, maxY],
    ];
  }

  /* ---------------------------------------------------------------------- *
   * 5. Paneles                                                             *
   * ---------------------------------------------------------------------- */

  function pintarNacional() {
    const variable = estado.filtros.variable;
    const total = estado.nacional;
    const top = rankingDe(variable).slice(0, 5);

    ui.nacional.innerHTML = `
      <p class="mexico-panel__kicker">MÉXICO · FILTRO ACTUAL</p>
      <div class="mexico-nacional__grid">
        <div><span>Daños</span><strong>${formatear("dano_mxn", total.dano_mxn)}</strong></div>
        <div><span>Defunciones</span><strong>${formatearSimple(total.defunciones)}</strong></div>
        <div><span>Afectados</span><strong>${formatearSimple(total.afectados)}</strong></div>
        <div><span>Eventos</span><strong>${formatearSimple(total.eventos)}</strong></div>
      </div>
      <p class="mexico-nacional__nota">
        ${total.estadosConDatos} de 32 estados con registros ·
        ${formatear("viviendas", total.viviendas)} viviendas dañadas
      </p>
      <p class="mexico-nacional__titulo">Estados punteros</p>
      <ol class="mexico-top">
        ${top
          .map(
            (iso, indice) => `
          <li>
            <button type="button" data-iso="${iso}">
              <span class="mexico-top__lugar">${indice + 1}</span>
              <span class="mexico-top__nombre">${escapar(nombreEstado(iso))}</span>
              <span class="mexico-top__valor">${formatear(
                variable,
                estado.agregados[iso][variable]
              )}</span>
            </button>
          </li>`
          )
          .join("")}
      </ol>
    `;

    ui.nacional.querySelectorAll("[data-iso]").forEach((boton) => {
      boton.addEventListener("click", () => {
        seleccionar(boton.dataset.iso);
        if (window.matchMedia("(max-width: 1080px)").matches) {
          ui.panel.scrollTo({ top: 0, behavior: "smooth" });
        }
      });
    });
  }

  function eventosFiltrados(iso) {
    const { min, max, tipo } = estado.filtros;
    return estado.datos.serie[iso]
      .filter(
        (fila) => fila[0] >= min && fila[0] <= max && (tipo === "todos" || fila[1] === tipo)
      )
      .sort((a, b) => b[2] - a[2])
      .slice(0, 4);
  }

  function pintarEstado() {
    const iso = estado.iso;
    if (!iso) {
      ui.estado.innerHTML = `<p class="mexico-vacio">Haz clic en un estado para ver su ficha.</p>`;
      if (ui.panel && ui.nacional) ui.panel.insertBefore(ui.nacional, ui.estado);
      return;
    }

    if (ui.panel && ui.nacional) ui.panel.insertBefore(ui.estado, ui.nacional);

    const variable = estado.filtros.variable;
    const datos = estado.agregados[iso] || {};
    const ranking = rankingDe(variable).indexOf(iso) + 1;
    const total = estado.nacional;
    const eventos = eventosFiltrados(iso);
    const participacion = porcentaje(datos[variable] || 0, total[variable] || 0);

    ui.estado.innerHTML = `
      <div class="mexico-estado__cabecera">
        <div>
          <p class="mexico-panel__kicker">${iso} · LUGAR #${ranking || "—"}</p>
          <h3>${escapar(nombreEstado(iso))}</h3>
        </div>
        <button type="button" class="boton-icono mexico-estado__cerrar" data-cerrar-estado aria-label="Quitar selección">×</button>
      </div>

      <div class="mexico-estado__marca">
        <span>Participación nacional en ${VARIABLES[variable].etiqueta.toLowerCase()}</span>
        <strong>${participacion}</strong>
        <div class="mexico-barra"><span style="width:${Math.min(
          100,
          (100 * (datos[variable] || 0)) / (total[variable] || 1)
        )}%"></span></div>
      </div>

      <div class="mexico-estado__kpis">
        <div><span>Daños</span><strong>${formatear("dano_mxn", datos.dano_mxn)}</strong></div>
        <div><span>Defunciones</span><strong>${formatearSimple(datos.defunciones)}</strong></div>
        <div><span>Afectados</span><strong>${formatearSimple(datos.afectados)}</strong></div>
        <div><span>Eventos</span><strong>${formatearSimple(datos.eventos)}</strong></div>
        <div><span>Viviendas</span><strong>${formatearSimple(datos.viviendas)}</strong></div>
      </div>

      <p class="mexico-estado__titulo">Eventos más costosos del filtro</p>
      <ul class="mexico-eventos">
        ${
          eventos.length
            ? eventos
                .map(
                  (fila) => `
              <li>
                <span class="mexico-eventos__anio">${fila[0]}</span>
                <span class="mexico-eventos__tipo">${escapar(fila[1])}</span>
                <span class="mexico-eventos__dato">${formatear("dano_mxn", fila[2])}</span>
              </li>`
                )
                .join("")
            : `<li class="mexico-eventos__vacio">Sin eventos con este filtro.</li>`
        }
      </ul>

      <button type="button" class="boton boton--fantasma boton--compacto" data-ver-en-mapa>
        Centrar el estado en el mapa
      </button>
    `;

    ui.estado.querySelector("[data-cerrar-estado]").addEventListener("click", () => {
      seleccionar(null);
    });
    ui.estado.querySelector("[data-ver-en-mapa]").addEventListener("click", () => {
      enfocarEstado(iso);
    });
  }

  /* ---------------------------------------------------------------------- *
   * 6. Fichas de desastres                                                 *
   * ---------------------------------------------------------------------- */

  function tarjetaDesastre(desastre) {
    const boton = document.createElement("button");
    boton.type = "button";
    boton.className = "tarjeta-desastre";
    boton.dataset.id = desastre.id;
    boton.innerHTML = `
      <span class="tarjeta-desastre__anio">${desastre.anio}</span>
      <span class="tarjeta-desastre__tipo">${escapar(desastre.tipo)}</span>
      <strong class="tarjeta-desastre__titulo">${escapar(desastre.titulo)}</strong>
      <span class="tarjeta-desastre__lugar">${escapar(desastre.estado)} · ${
      desastre.num_municipios
    } ${desastre.num_municipios === 1 ? "municipio" : "municipios"}</span>
      <dl class="tarjeta-desastre__datos">
        <div><dt>Daños</dt><dd>${formatear("dano_mxn", desastre.dano_mxn)}</dd></div>
        <div><dt>Defunciones</dt><dd>${formatearSimple(desastre.defunciones)}</dd></div>
        <div><dt>Afectados</dt><dd>${formatearSimple(desastre.afectados)}</dd></div>
      </dl>
      <span class="tarjeta-desastre__cta">Ver ficha completa →</span>
    `;
    return boton;
  }

  function pintarDestacados() {
    [ui.destacados, ui.destacadosMini].forEach((contenedor) => {
      if (!contenedor) return;
      contenedor.innerHTML = "";
      estado.datos.destacados.forEach((desastre) => {
        contenedor.appendChild(tarjetaDesastre(desastre));
      });
    });
  }

  function abrirDesastre(id) {
    const desastre = estado.datos.destacados.find((d) => d.id === id);
    if (!desastre) return;

    ui.desastreKicker.textContent = `${desastre.clasificacion.toUpperCase()} · ${desastre.anio}`;
    ui.desastreTitulo.textContent = desastre.titulo;
    ui.desastreMeta.textContent = `${desastre.estado} · ${desastre.fecha} · ${
      desastre.num_municipios
    } ${desastre.num_municipios === 1 ? "municipio" : "municipios"}`;
    ui.desastreBadge.textContent = `Estado #${desastre.ranking_estatal_dano} en daños del país`;

    const kpis = [
      ["Daños totales", formatear("dano_mxn", desastre.dano_mxn)],
      ["Defunciones", formatearSimple(desastre.defunciones)],
      ["Población afectada", formatearSimple(desastre.afectados)],
      ["Viviendas dañadas", formatearSimple(desastre.viviendas)],
      ["Escuelas · hospitales", `${formatearSimple(desastre.escuelas)} · ${formatearSimple(desastre.hospitales)}`],
      ["Participación estatal", `${desastre.participacion_estatal.toFixed(1)} %`],
    ];

    ui.desastreKpis.innerHTML = kpis
      .map(
        ([etiqueta, valor]) => `
        <div class="kpi">
          <span class="kpi__etiqueta">${etiqueta}</span>
          <strong class="kpi__valor">${valor}</strong>
        </div>`
      )
      .join("");

    ui.desastreDescripcion.textContent =
      desastre.descripcion || "La fuente no incluye una descripción narrativa de este evento.";
    ui.desastreFuente.textContent = `Fuente: ${desastre.fuente} · Atlas Nacional de Riesgos`;

    ui.desastreVerMapa.onclick = () => {
      cerrarDesastre();
      if (!estado.abierto) abrir();
      window.setTimeout(() => enfocarEstado(desastre.iso), 350);
    };

    if (!ui.modalDesastre.open) ui.modalDesastre.showModal();
  }

  function cerrarDesastre() {
    if (ui.modalDesastre.open) ui.modalDesastre.close();
  }

  /* ---------------------------------------------------------------------- *
   * 7. Controles y apertura                                                *
   * ---------------------------------------------------------------------- */

  function llenarControles() {
    const anios = [];
    for (let anio = 2000; anio <= 2024; anio += 1) anios.push(anio);

    [ui.anioMin, ui.anioMax].forEach((selector) => {
      selector.innerHTML = "";
      anios.forEach((anio) => {
        const opcion = document.createElement("option");
        opcion.value = String(anio);
        opcion.textContent = String(anio);
        selector.appendChild(opcion);
      });
    });

    ui.anioMin.value = String(estado.filtros.min);
    ui.anioMax.value = String(estado.filtros.max);

    ui.tipo.innerHTML = `<option value="todos">Todos los tipos</option>`;
    estado.datos.tipos.forEach((fila) => {
      const opcion = document.createElement("option");
      opcion.value = fila.tipo;
      opcion.textContent = `${fila.tipo} (${fila.eventos})`;
      ui.tipo.appendChild(opcion);
    });
  }

  function aplicarFiltros() {
    const variable = ui.variable.value;
    const min = Number(ui.anioMin.value);
    const max = Number(ui.anioMax.value);

    estado.filtros.variable = variable;
    estado.filtros.min = Math.min(min, max);
    estado.filtros.max = Math.max(min, max);
    estado.filtros.tipo = ui.tipo.value;

    // Sincronizar parámetros de relieve desde los controles.
    estado.variableAltura = ui.variableAltura.value;
    estado.recurso = ui.recursoActivo();
    estado.intensidad = Number(ui.intensidad.value) / 100;
    estado.alturaMaxima = Number(ui.escalaAltura.value);
    estado.escala = ui.escala.value;

    recalcular();
    refrescarMapa();
    pintarNacional();
    pintarEstado();
  }

  function restablecer() {
    ui.variable.value = "dano_mxn";
    ui.anioMin.value = "2000";
    ui.anioMax.value = "2024";
    ui.tipo.value = "todos";
    ui.variableAltura.value = "defunciones";
    ui.intensidad.value = "70";
    ui.escalaAltura.value = "120000";
    ui.escala.value = "auto";
    // Reactivar el segmento de elevación.
    ui.controles.querySelectorAll(".segmento").forEach((s) => {
      s.classList.remove("activo");
      s.setAttribute("aria-checked", "false");
    });
    const segmentoElev = ui.controles.querySelector('[data-recurso="elevacion"]');
    if (segmentoElev) {
      segmentoElev.classList.add("activo");
      segmentoElev.setAttribute("aria-checked", "true");
    }
    estado.iso = null;
    aplicarFiltros();
  }

  function abrir() {
    if (!estado.cargado) return;
    ui.vista.hidden = false;
    estado.abierto = true;
    document.body.classList.add("mexico-abierto");

    if (window.matchMedia("(max-width: 900px)").matches) {
      ui.controles.classList.remove("visible");
      ui.btnFiltros.setAttribute("aria-expanded", "false");
    }

    if (!estado.mapa) {
      crearMapa();
    }

    if (!estado.iso) {
      const puntero = rankingDe(estado.filtros.variable)[0];
      if (puntero) seleccionar(puntero);
    }

    window.requestAnimationFrame(() => {
      if (estado.mapa) estado.mapa.resize();
    });
    window.setTimeout(() => {
      if (estado.mapa) estado.mapa.resize();
    }, 220);

    ui.cerrar.focus();

    document.dispatchEvent(
      new CustomEvent("atlas:mexico", { detail: { abierto: true } })
    );
  }

  function cerrar() {
    if (!estado.abierto) return;
    ui.vista.hidden = true;
    estado.abierto = false;
    document.body.classList.remove("mexico-abierto");
    if (ui.btnAbrir && typeof ui.btnAbrir.focus === "function") {
      ui.btnAbrir.focus({ preventScroll: true });
    }
    document.dispatchEvent(
      new CustomEvent("atlas:mexico", { detail: { abierto: false } })
    );
  }

  function renderMini() {
    const total = estado.datos.total;
    if (ui.mini) {
      ui.mini.innerHTML = `
        <div class="mexico-mini__dato"><span>Eventos</span><strong>${formatearSimple(
          total.eventos
        )}</strong></div>
        <div class="mexico-mini__dato"><span>Defunciones</span><strong>${formatearSimple(
          total.defunciones
        )}</strong></div>
        <div class="mexico-mini__dato"><span>Afectados</span><strong>${formatearSimple(
          total.afectados
        )}</strong></div>
        <div class="mexico-mini__dato"><span>Daños</span><strong>${formatear(
          "dano_mxn",
          total.dano_mxn
        )}</strong></div>
      `;
    }
    if (ui.sub) {
      ui.sub.textContent = `${formatearSimple(total.eventos)} desastres naturales · 32 estados · 2000–2024`;
    }
  }

  function conectarEventos() {
    ui.btnAbrir.addEventListener("click", abrir);
    ui.cerrar.addEventListener("click", cerrar);

    document.addEventListener("keydown", (evento) => {
      if (evento.key === "Escape" && estado.abierto) cerrar();
    });

    [ui.variable, ui.anioMin, ui.anioMax, ui.tipo, ui.variableAltura, ui.escala].forEach(
      (control) => {
        control.addEventListener("change", aplicarFiltros);
      }
    );

    [ui.intensidad, ui.escalaAltura].forEach((control) => {
      control.addEventListener("input", aplicarFiltros);
      control.addEventListener("input", (evento) => {
        const id = evento.target.id;
        let clave = id.replace("mexico-", "");
        if (clave === "escala-altura") clave = "altura";
        const mostrar = document.getElementById(`mexico-valor-${clave}`);
        if (mostrar) {
          mostrar.textContent =
            id === "mexico-intensidad"
              ? `${evento.target.value} %`
              : `${Math.round(evento.target.value / 1000)} km`;
        }
      });
    });

    // Segmentos de recurso visual 3D.
    ui.controles.querySelectorAll(".segmento").forEach((boton) => {
      boton.addEventListener("click", () => {
        ui.controles.querySelectorAll(".segmento").forEach((s) => {
          s.classList.remove("activo");
          s.setAttribute("aria-checked", "false");
        });
        boton.classList.add("activo");
        boton.setAttribute("aria-checked", "true");
        aplicarFiltros();
      });
    });

    ui.recursoActivo = () => {
      const activo = ui.controles.querySelector(".segmento.activo");
      return activo ? activo.dataset.recurso : "elevacion";
    };

    ui.reset.addEventListener("click", restablecer);

    ui.btnFiltros.addEventListener("click", () => {
      const visible = ui.controles.classList.toggle("visible");
      ui.btnFiltros.setAttribute("aria-expanded", String(visible));
    });

    if (ui.destacadosMini) {
      ui.destacadosMini.addEventListener("click", (evento) => {
        const boton = evento.target.closest("[data-id]");
        if (boton) abrirDesastre(boton.dataset.id);
      });
    }

    if (ui.destacados) {
      ui.destacados.addEventListener("click", (evento) => {
        const boton = evento.target.closest("[data-id]");
        if (boton) abrirDesastre(boton.dataset.id);
      });
    }

    ui.cerrarDesastre.addEventListener("click", cerrarDesastre);
    ui.modalDesastre.addEventListener("click", (evento) => {
      if (evento.target === ui.modalDesastre) cerrarDesastre();
    });

    window.addEventListener("resize", () => {
      if (estado.abierto && estado.mapa) estado.mapa.resize();
    });
  }

  function cachearUi() {
    ui.vista = document.getElementById("vista-mexico");
    ui.btnAbrir = document.getElementById("btn-abrir-mexico");
    ui.cerrar = document.getElementById("mexico-cerrar");
    ui.controles = document.getElementById("mexico-controles");
    ui.btnFiltros = document.getElementById("mexico-filtros");
    ui.variable = document.getElementById("mexico-variable");
    ui.anioMin = document.getElementById("mexico-anio-min");
    ui.anioMax = document.getElementById("mexico-anio-max");
    ui.tipo = document.getElementById("mexico-tipo");
    ui.reset = document.getElementById("mexico-reset");
    ui.leyendaTitulo = document.getElementById("mexico-leyenda-titulo");
    ui.leyendaUnidad = document.getElementById("mexico-leyenda-unidad");
    ui.leyendaBarra = document.getElementById("mexico-leyenda-barra");
    ui.leyendaMin = document.getElementById("mexico-leyenda-min");
    ui.leyendaMax = document.getElementById("mexico-leyenda-max");
    ui.leyendaNota = document.getElementById("mexico-leyenda-nota");
    ui.tooltip = document.getElementById("mexico-tooltip");
    ui.nacional = document.getElementById("mexico-nacional");
    ui.estado = document.getElementById("mexico-estado");
    ui.panel = document.querySelector(".mexico-panel");
    ui.destacados = document.getElementById("mexico-destacados");
    ui.destacadosMini = document.getElementById("mexico-destacados-mini");
    ui.mini = document.getElementById("mexico-mini");
    ui.sub = document.getElementById("mexico-sub");
    ui.modalDesastre = document.getElementById("modal-desastre");
    ui.desastreKicker = document.getElementById("desastre-kicker");
    ui.desastreTitulo = document.getElementById("desastre-titulo");
    ui.desastreMeta = document.getElementById("desastre-meta");
    ui.desastreBadge = document.getElementById("desastre-badge");
    ui.desastreKpis = document.getElementById("desastre-kpis");
    ui.desastreDescripcion = document.getElementById("desastre-descripcion");
    ui.desastreFuente = document.getElementById("desastre-fuente");
    ui.desastreVerMapa = document.getElementById("desastre-ver-mapa");
    ui.cerrarDesastre = document.getElementById("desastre-cerrar");

    /* Controles de capa temática / relieve (equivalentes al mapa global) */
    ui.variableAltura = document.getElementById("mexico-variable-altura");
    ui.intensidad = document.getElementById("mexico-intensidad");
    ui.escalaAltura = document.getElementById("mexico-escala-altura");
    ui.escala = document.getElementById("mexico-escala");
  }

  async function cargarJSON(ruta) {
    const respuesta = await fetch(ruta);
    if (!respuesta.ok) throw new Error(`No se pudo cargar ${ruta} (${respuesta.status})`);
    return respuesta.json();
  }

  async function iniciar() {
    cachearUi();
    if (!ui.vista || !ui.btnAbrir) return;

    conectarEventos();

    try {
      const [datos, geo] = await Promise.all([
        cargarJSON(RUTAS.datos),
        cargarJSON(RUTAS.geo),
      ]);
      estado.datos = datos;
      estado.geo = limpiarIslas(geo);
      estado.cargado = true;

      llenarControles();
      recalcular();
      pintarLeyenda(estado.filtros.variable);
      pintarNacional();
      pintarEstado();
      pintarDestacados();
      renderMini();
    } catch (error) {
      console.error("[México] No se pudieron cargar los datos:", error);
      if (ui.nacional) {
        ui.nacional.innerHTML = `<p class="mexico-vacio">No se pudieron cargar los datos de México.</p>`;
      }
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", iniciar);
  } else {
    iniciar();
  }
})();
