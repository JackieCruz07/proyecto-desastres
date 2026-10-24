/* =========================================================================
   app.js — Orquestador de la aplicación web
   -------------------------------------------------------------------------
   Crea el mapa 3D (globo/plano), carga la capa temática, sincroniza los
   controles del panel y gestiona la interacción con el usuario
   (tooltip, selección de territorio y ficha de información).
   ========================================================================= */

(() => {
  "use strict";

  /* ---------------------------------------------------------------------- *
   * 1. Elementos de la interfaz                                            *
   * ---------------------------------------------------------------------- */
  const ui = {
    mapa: document.getElementById("mapa"),
    tooltip: document.getElementById("tooltip"),
    selectorColor: document.getElementById("selector-color"),
    selectorAltura: document.getElementById("selector-elevacion"),
    selectorEscala: document.getElementById("selector-escala"),
    intensidad: document.getElementById("intensidad"),
    escalaAltura: document.getElementById("escala-altura"),
    valorAltura: document.getElementById("valor-altura"),
    chkSinDatos: document.getElementById("chk-sin-datos"),
    ficha: document.getElementById("ficha"),
    btnGlobo: document.getElementById("btn-globo"),
    btnPlano: document.getElementById("btn-plano"),
    segmentos: document.querySelectorAll(".segmento[data-recurso]"),
  };

  let mapa = null;
  let hoverId = null;

  /** Expone la instancia del mapa para herramientas externas (capturas). */
  window.__mapa = () => mapa;

  /* ---------------------------------------------------------------------- *
   * 2. Carga de datos                                                      *
   * ---------------------------------------------------------------------- */
  async function cargarJSON(ruta) {
    const respuesta = await fetch(ruta);
    if (!respuesta.ok) {
      throw new Error(`No se pudo cargar ${ruta} (${respuesta.status})`);
    }
    return respuesta.json();
  }

  /* ---------------------------------------------------------------------- *
   * 3. Construcción del mapa                                               *
   * ---------------------------------------------------------------------- */
  function crearMapa() {
    mapa = new maplibregl.Map({
      container: "mapa",
      style: CONFIG.estiloBase,
      center: CONFIG.vistaInicial.center,
      zoom: CONFIG.vistaInicial.zoom,
      pitch: CONFIG.vistaInicial.pitch,
      bearing: CONFIG.vistaInicial.bearing,
      attributionControl: { compact: true },
      maxPitch: 85,
    });

    mapa.addControl(
      new maplibregl.NavigationControl({ visualizePitch: true }),
      "bottom-right"
    );
    mapa.addControl(new maplibregl.GlobeControl(), "bottom-right");
    mapa.addControl(
      new maplibregl.ScaleControl({ maxWidth: 120, unit: "metric" }),
      "bottom-left"
    );

    mapa.on("style.load", () => {
      // El globo se activa sobre el estilo base.
      mapa.setProjection({ type: "globe" });
      mapa.setSky({
        "sky-color": CONFIG.colores.oceano,
        "horizon-color": CONFIG.colores.atmosfera,
        "fog-color": CONFIG.colores.oceano,
        "sky-horizon-blend": 0.55,
        "horizon-fog-blend": 0.6,
        "fog-ground-blend": 0.5,
      });
    });

    return new Promise((resolve) => {
      mapa.on("load", () => resolve(mapa));
    });
  }

  /** Alterna entre proyección globo y plana (Mercator). */
  function cambiarProyeccion(tipo) {
    if (tipo === "globo") {
      mapa.setProjection({ type: "globe" });
      mapa.setSky({
        "sky-color": CONFIG.colores.oceano,
        "horizon-color": CONFIG.colores.atmosfera,
        "fog-color": CONFIG.colores.oceano,
        "sky-horizon-blend": 0.55,
        "horizon-fog-blend": 0.6,
        "fog-ground-blend": 0.5,
      });
    } else {
      mapa.setProjection({ type: "mercator" });
      mapa.setSky({});
    }
    ui.btnGlobo.classList.toggle("activo", tipo === "globo");
    ui.btnPlano.classList.toggle("activo", tipo === "plano");
  }

  /* ---------------------------------------------------------------------- *
   * 4. Panel de control                                                    *
   * ---------------------------------------------------------------------- */
  function poblarSelectores(metadatos) {
    const variables = Object.entries(metadatos.variables);

    variables.forEach(([clave, definicion]) => {
      const opcionColor = document.createElement("option");
      opcionColor.value = clave;
      opcionColor.textContent = definicion.etiqueta;
      ui.selectorColor.appendChild(opcionColor);

      const opcionAltura = document.createElement("option");
      opcionAltura.value = clave;
      opcionAltura.textContent = definicion.etiqueta;
      ui.selectorAltura.appendChild(opcionAltura);
    });

    ui.selectorColor.value = CapaTematica.estado.variableColor;
    ui.selectorAltura.value = CapaTematica.estado.variableAltura;
  }

  function conectarControles() {
    ui.selectorColor.addEventListener("change", (e) => {
      CapaTematica.setVariableColor(e.target.value);
      actualizarTarjetas();
    });

    ui.selectorAltura.addEventListener("change", (e) => {
      CapaTematica.setVariableAltura(e.target.value);
    });

    ui.selectorEscala.addEventListener("change", (e) => {
      CapaTematica.setEscala(e.target.value);
    });

    ui.intensidad.addEventListener("input", (e) => {
      CapaTematica.setIntensidad(Number(e.target.value) / 100);
    });

    ui.escalaAltura.addEventListener("input", (e) => {
      const metros = Number(e.target.value);
      ui.valorAltura.textContent = `${Math.round(metros / 1000)} km`;
      CapaTematica.setAlturaMaxima(metros);
    });

    ui.chkSinDatos.addEventListener("change", (e) => {
      CapaTematica.setMostrarSinDatos(e.target.checked);
      actualizarTarjetas();
    });

    ui.segmentos.forEach((boton) => {
      boton.addEventListener("click", () => {
        ui.segmentos.forEach((b) => {
          b.classList.remove("activo");
          b.setAttribute("aria-checked", "false");
        });
        boton.classList.add("activo");
        boton.setAttribute("aria-checked", "true");
        CapaTematica.setRecurso(boton.dataset.recurso);
        actualizarTarjetas();
      });
    });

    ui.btnGlobo.addEventListener("click", () => cambiarProyeccion("globo"));
    ui.btnPlano.addEventListener("click", () => cambiarProyeccion("plano"));
  }

  /* ---------------------------------------------------------------------- *
   * 5. Interacción: tooltip y selección                                    *
   * ---------------------------------------------------------------------- */
  function conectarInteraccion() {
    const capaInteractiva = "relleno-coloreado";

    mapa.on("mousemove", capaInteractiva, (e) => {
      if (!e.features || !e.features.length) return;
      mapa.getCanvas().style.cursor = "pointer";

      const territorio = e.features[0].properties;
      if (hoverId !== territorio.codigo) {
        hoverId = territorio.codigo;
        mostrarTooltip(territorio, e.point);
      } else {
        moverTooltip(e.point);
      }
    });

    mapa.on("mouseleave", capaInteractiva, () => {
      mapa.getCanvas().style.cursor = "";
      hoverId = null;
      ocultarTooltip();
    });

    mapa.on("click", capaInteractiva, (e) => {
      if (!e.features || !e.features.length) return;
      const codigo = e.features[0].properties.codigo;
      CapaTematica.setSeleccionado(codigo);
      mostrarFicha(codigo);
    });

    mapa.on("click", (e) => {
      // Clic en el océano: limpia la selección.
      const capas = mapa.getLayer(capaInteractiva)
        ? mapa.queryRenderedFeatures(e.point, { layers: [capaInteractiva] })
        : [];
      if (!capas.length) {
        CapaTematica.setSeleccionado(null);
        fichaInicial();
      }
    });
  }

  /** Inserta el HTML del tooltip con los indicadores principales. */
  function contenidoTooltip(territorio) {
    const variables = CapaTematica.estado.metadatos.variables;
    const filas = ["eventos", "fallecidos", "afectados", "dano_ajustado"]
      .map((clave) => {
        const definicion = variables[clave];
        return `
          <div class="tooltip__fila">
            <span>${definicion.etiqueta}</span>
            <strong>${Escalas.formatearValor(
              territorio[clave],
              definicion.formato,
              clave === "dano_ajustado" ? { mostrarMXN: true } : {}
            )}</strong>
          </div>`;
      })
      .join("");

    return `
      <div class="tooltip__titulo">${territorio.nombre}</div>
      ${filas}
    `;
  }

  function mostrarTooltip(territorio, punto) {
    ui.tooltip.innerHTML = contenidoTooltip(territorio);
    ui.tooltip.classList.add("visible");
    ui.tooltip.setAttribute("aria-hidden", "false");
    moverTooltip(punto);
  }

  function moverTooltip(punto) {
    const margen = 16;
    const ancho = ui.tooltip.offsetWidth;
    const alto = ui.tooltip.offsetHeight;

    let x = punto.x + margen;
    let y = punto.y + margen;

    if (x + ancho > ui.mapa.clientWidth) x = punto.x - ancho - margen;
    if (y + alto > ui.mapa.clientHeight) y = punto.y - alto - margen;

    ui.tooltip.style.left = `${Math.max(4, x)}px`;
    ui.tooltip.style.top = `${Math.max(4, y)}px`;
  }

  function ocultarTooltip() {
    ui.tooltip.classList.remove("visible");
    ui.tooltip.setAttribute("aria-hidden", "true");
  }

  /* ---------------------------------------------------------------------- *
   * 6. Ficha del territorio                                                *
   * ---------------------------------------------------------------------- */
  function fichaInicial() {
    ui.ficha.innerHTML = `
      <div class="ficha__vacio">
        <div style="font-size:30px;color:#60a5fa">◎</div>
        <p>Selecciona un territorio en el mapa para consultar sus
        indicadores.</p>
      </div>`;
  }

  function mostrarFicha(codigo) {
    const territorio = CapaTematica.territorio(codigo);
    if (!territorio) {
      fichaInicial();
      return;
    }

    const variables = CapaTematica.estado.metadatos.variables;
    const conDatos = territorio.eventos !== null;

    const metricas = [
      "eventos",
      "fallecidos",
      "afectados",
      "dano_ajustado",
      "prom_fallecidos",
      "prom_afectados",
    ]
      .map((clave) => {
        const definicion = variables[clave];
        return `
          <div class="metrica" style="border-left-color:${CapaTematica.colorDe(
            codigo
          )}">
            <span class="metrica__nombre">${definicion.etiqueta}</span>
            <span class="metrica__valor">${Escalas.formatearValor(
              territorio[clave],
              definicion.formato,
              clave === "dano_ajustado" ? { mostrarMXN: true } : {}
            )}</span>
          </div>`;
      })
      .join("");

    ui.ficha.innerHTML = `
      <p class="ficha__nombre">${territorio.nombre}</p>
      <p class="ficha__codigo">Código geográfico: ${territorio.codigo} ·
        ${territorio.continente || "—"}</p>
      <span class="ficha__estado ${conDatos ? "con-datos" : "sin-datos"}">
        ${territorio.disponibilidad}
      </span>
      <div class="ficha__metricas">${metricas}</div>
      <p class="ficha__observacion">${territorio.observacion}</p>
    `;
  }

  /* ---------------------------------------------------------------------- *
   * 7. Tarjetas de resumen                                                 *
   * ---------------------------------------------------------------------- */
  function actualizarTarjetas() {
    const metadatos = CapaTematica.estado.metadatos;
    const territorios = CapaTematica.estado.territorios;
    const variable = CapaTematica.estado.variableColor;
    const definicion = metadatos.variables[variable];
    const stats = definicion.estadisticos;

    const conDatos = territorios.filter((t) => t[variable] !== null).length;

    Estado.tarjetas([
      {
        titulo: "Territorios",
        valor: metadatos.n_territorios.toLocaleString("es-MX"),
        nota: "Unidades cartográficas en el mapa",
      },
      {
        titulo: "Con indicadores",
        valor: conDatos.toLocaleString("es-MX"),
        nota: "Territorios con datos de la variable",
      },
      {
        titulo: definicion.etiqueta,
        valor: Escalas.formatearValor(stats.max, definicion.formato),
        nota: "Valor máximo registrado",
      },
      {
        titulo: "Mediana",
        valor: Escalas.formatearValor(stats.p50, definicion.formato),
        nota: `${stats.n} territorios con datos`,
      },
    ]);
  }

  /* ---------------------------------------------------------------------- *
   * 8. Arranque de la aplicación                                           *
   * ---------------------------------------------------------------------- */
  async function iniciar() {
    try {
      Estado.mensaje("Cargando capa temática…");

      const [geojson, metadatos] = await Promise.all([
        cargarJSON(CONFIG.rutaDatos),
        cargarJSON(CONFIG.rutaMetadatos),
      ]);

      await crearMapa();

      CapaTematica.iniciar(mapa, geojson, metadatos);

      poblarSelectores(metadatos);
      conectarControles();
      conectarInteraccion();
      actualizarTarjetas();
      fichaInicial();
      try {
        if (typeof poblarFiltroTipos === "function") poblarFiltroTipos();
        document.getElementById("filtro-anio-min")?.addEventListener("input", actualizarFiltroPeriodo);
        document.getElementById("filtro-anio-max")?.addEventListener("input", actualizarFiltroPeriodo);
        document.getElementById("selector-tipo")?.addEventListener("change", actualizarFiltroPeriodo);
        document.getElementById("chk-aplicar-filtros")?.addEventListener("change", actualizarFiltroPeriodo);
        document.getElementById("btn-reset-filtros")?.addEventListener("click", () => {
          document.getElementById("filtro-anio-min").value = 2000;
          document.getElementById("filtro-anio-max").value = 2026;
          document.getElementById("selector-tipo").value = "todos";
          document.getElementById("chk-aplicar-filtros").checked = true;
          if (typeof actualizarFiltroPeriodo === "function") actualizarFiltroPeriodo();
        });
        if (typeof actualizarFiltroPeriodo === "function") actualizarFiltroPeriodo();
      } catch(e) { console.warn(e); }

      // Nota metodológica desde los metadatos.
      document.getElementById("nota-metodologica").textContent =
        `${metadatos.fuente}. Periodo ${metadatos.periodo.inicio}–` +
        `${metadatos.periodo.fin} · ${metadatos.n_eventos.toLocaleString(
          "es-MX"
        )} eventos. La ausencia de indicadores no implica ausencia de ` +
        `desastres. Los territorios sin datos se muestran con color neutro.`;

      Estado.mensaje(
        `Capa temática lista · ${metadatos.n_eventos.toLocaleString(
          "es-MX"
        )} eventos · ${metadatos.n_territorios} territorios`,
        "ok"
      );

      // Oculta el tooltip al desplazar el mapa.
      mapa.on("movestart", ocultarTooltip);
    } catch (error) {
      console.error(error);
      Estado.mensaje(`Error: ${error.message}`, "error");
    }
  }

  document.addEventListener("DOMContentLoaded", iniciar);
})();
