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
    chkIncendios: document.getElementById("chk-incendios"),
    ficha: document.getElementById("ficha"),
    btnGlobo: document.getElementById("btn-globo"),
    btnPlano: document.getElementById("btn-plano"),
    btnAbrirPanel: document.getElementById("btn-abrir-panel"),
    modal: document.getElementById("modal-pais"),
    modalCerrar: document.getElementById("modal-cerrar"),
    segmentos: document.querySelectorAll(".segmento[data-recurso]"),
  };

  let mapa = null;
  let hoverId = null;

  /* Datos complementarios del panel por país (Actividad 5). */
  let datosSocio = null;
  let datosEventos = null;
  let datosOwid = null;
  let datosIncendios = null;
  let incendiosListos = false;
  let paisActual = null;
  let rankingsActuales = null;

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

  /** Carga los archivos del panel por país sin bloquear el mapa si falla uno. */
  async function cargarDatosPanel() {
    const [socio, eventos, owid, incendios] = await Promise.allSettled([
      cargarJSON(CONFIG.rutaSocio),
      cargarJSON(CONFIG.rutaEventos),
      cargarJSON(CONFIG.rutaOwid),
      cargarJSON(CONFIG.rutaIncendios),
    ]);

    if (socio.status === "fulfilled") datosSocio = socio.value;
    if (eventos.status === "fulfilled") datosEventos = eventos.value;
    if (owid.status === "fulfilled") datosOwid = owid.value;
    if (incendios.status === "fulfilled") datosIncendios = incendios.value;
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
      "bottom-right"
    );

    mapa.on("style.load", () => {
      // El globo se activa sobre el estilo base.
      mapa.setProjection({ type: "globe" });
      mapa.setSky({
        "sky-color": CONFIG.colores.cielo,
        "horizon-color": CONFIG.colores.atmosfera,
        "fog-color": CONFIG.colores.cielo,
        "sky-horizon-blend": 0.55,
        "horizon-fog-blend": 0.6,
        "fog-ground-blend": 0.5,
        "atmosphere-blend": 0.7,
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
        "sky-color": CONFIG.colores.cielo,
        "horizon-color": CONFIG.colores.atmosfera,
        "fog-color": CONFIG.colores.cielo,
        "sky-horizon-blend": 0.55,
        "horizon-fog-blend": 0.6,
        "fog-ground-blend": 0.5,
        "atmosphere-blend": 0.7,
      });
    } else {
      mapa.setProjection({ type: "mercator" });
      mapa.setSky({});
    }
    ui.btnGlobo.classList.toggle("activo", tipo === "globo");
    ui.btnPlano.classList.toggle("activo", tipo === "plano");
  }

  /* ---------------------------------------------------------------------- *
   * 3b. Pestañas del panel y ventana de detalle                            *
   * ---------------------------------------------------------------------- */
  function activarPestana(nombre) {
    document.querySelectorAll(".pestana[data-pestana]").forEach((boton) => {
      const activo = boton.dataset.pestana === nombre;
      boton.classList.toggle("activo", activo);
      boton.setAttribute("aria-selected", String(activo));
    });
    document.querySelectorAll(".vista[data-vista]").forEach((vista) => {
      vista.classList.toggle("activo", vista.dataset.vista === nombre);
    });
  }

  function conectarPestanas() {
    document.querySelectorAll(".pestana[data-pestana]").forEach((boton) => {
      boton.addEventListener("click", () => activarPestana(boton.dataset.pestana));
    });
  }

  function abrirModalPais(codigo) {
    if (!codigo || !ui.modal) return;
    paisActual = codigo;
    if (!ui.modal.open) ui.modal.showModal();
    const cuerpo = ui.modal.querySelector(".modal__cuerpo");
    if (cuerpo) cuerpo.scrollTop = 0;
    renderPanelPais();
  }

  function cerrarModalPais() {
    if (ui.modal && ui.modal.open) ui.modal.close();
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
      const props = e.features[0].properties || {};
      const codigo = props.codigo || props.iso_a3 || props.ISO_A3 || props.adm0_a3 || props.iso3 || props.ISO3 || props.sov_a3;
      CapaTematica.setSeleccionado(codigo);
      mostrarFicha(codigo);
      if (typeof actualizarPanelPais === "function") {
        actualizarPanelPais(codigo, props);
      }
    });

    mapa.on("dblclick", capaInteractiva, (e) => {
      if (!e.features || !e.features.length) return;
      const props = e.features[0].properties || {};
      if (props.codigo) abrirModalPais(props.codigo);
    });

    mapa.on("click", (e) => {
      // Clic en el océano: limpia la selección.
      const capas = mapa.getLayer(capaInteractiva)
        ? mapa.queryRenderedFeatures(e.point, { layers: [capaInteractiva] })
        : [];
      if (!capas.length) {
        CapaTematica.setSeleccionado(null);
        fichaInicial();
        if (typeof actualizarPanelPais === "function") {
          actualizarPanelPais(null);
        }
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
              definicion.formato
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
        <p>Selecciona un territorio en el mapa para consultar sus
        indicadores.</p>
      </div>`;
    if (ui.btnAbrirPanel) {
      ui.btnAbrirPanel.disabled = true;
      ui.btnAbrirPanel.textContent = "Abrir panel detallado";
    }
  }

  function mostrarFicha(codigo) {
    const territorio = CapaTematica.territorio(codigo);
    if (!territorio) {
      fichaInicial();
      return;
    }

    const variables = CapaTematica.estado.metadatos.variables;
    const conDatos = territorio.eventos !== null;

    const metricas = ["eventos", "fallecidos", "afectados", "dano_ajustado"]
      .map((clave) => {
        const definicion = variables[clave];
        return `
          <div class="metrica" style="border-left-color:${CapaTematica.colorDe(
            codigo
          )}">
            <span class="metrica__nombre">${definicion.etiqueta}</span>
            <span class="metrica__valor">${Escalas.formatearValor(
              territorio[clave],
              definicion.formato
            )}</span>
          </div>`;
      })
      .join("");

    // Datos generales del país (Banco Mundial) en la ficha compacta.
    const socio = (datosSocio && datosSocio.paises[codigo]) || {};
    const generales = [
      ["Población", socio.poblacion, "entero"],
      ["Superficie", socio.superficie_km2, "entero"],
      ["PIB", socio.pib_mxn, "moneda"],
      ["PIB por habitante", socio.pib_pc_mxn, "moneda"],
    ]
      .filter(([, valor]) => valor !== null && valor !== undefined)
      .map(
        ([etiqueta, valor, formato]) => `
          <div class="metrica metrica--socio">
            <span class="metrica__nombre">${etiqueta}</span>
            <span class="metrica__valor">${Escalas.formatearValor(valor, formato)}${
          etiqueta === "Superficie" ? " km²" : ""
        }</span>
          </div>`
      )
      .join("");

    ui.ficha.innerHTML = `
      <p class="ficha__nombre">${territorio.nombre}</p>
      <p class="ficha__codigo">${territorio.codigo} · ${territorio.continente || "—"}</p>
      <span class="ficha__estado ${conDatos ? "con-datos" : "sin-datos"}">
        ${territorio.disponibilidad}
      </span>
      <div class="ficha__metricas">${metricas}</div>
      ${generales ? `<div class="ficha__metricas">${generales}</div>` : ""}
      <p class="ficha__observacion">${territorio.observacion}</p>
    `;

    if (ui.btnAbrirPanel) {
      ui.btnAbrirPanel.disabled = false;
      ui.btnAbrirPanel.textContent = `Abrir panel de ${territorio.nombre}`;
    }
  }



  /* ---------------------------------------------------------------------- *
   * 7b. Filtros y controles interactivos (Actividad 4)                     *
   * ---------------------------------------------------------------------- */

  let datosFiltros = null;
  let periodoFiltros = { inicio: 2000, fin: 2026 };
  let codigoSeleccionado = null;

  async function cargarDatosFiltros() {
    try {
      const resp = await fetch("datos/filtros.json");
      if (!resp.ok) return;
      datosFiltros = await resp.json();
      if (datosFiltros.periodo) periodoFiltros = datosFiltros.periodo;
    } catch (e) {
      console.warn("No se pudo cargar filtros.json", e);
    }
  }

  /** Rellena el selector de tipos con el diccionario en español. */
  function poblarFiltroTipos() {
    const select = document.getElementById("selector-tipo");
    if (!select) return;
    const tipos = (datosFiltros && datosFiltros.tipos) || [];
    select.innerHTML = '<option value="todos">Todos los tipos</option>';
    tipos.forEach((tipo) => {
      const op = document.createElement("option");
      op.value = tipo;
      op.textContent = traducirTipoDesastre(tipo);
      select.appendChild(op);
    });
  }

  /** Lee el estado actual de los controles de filtro. */
  function leerFiltros() {
    const minEl = document.getElementById("filtro-anio-min");
    const maxEl = document.getElementById("filtro-anio-max");
    const tipoSel = document.getElementById("selector-tipo");
    const chk = document.getElementById("chk-aplicar-filtros");

    let a1 = minEl ? parseInt(minEl.value, 10) : periodoFiltros.inicio;
    let a2 = maxEl ? parseInt(maxEl.value, 10) : periodoFiltros.fin;
    if (a1 > a2) {
      const tmp = a1;
      a1 = a2;
      a2 = tmp;
    }
    return {
      a1,
      a2,
      tipo: tipoSel ? tipoSel.value : "todos",
      activo: chk ? chk.checked : true,
    };
  }

  /** Estadísticos de las variables a partir de los valores filtrados. */
  function calcularEstadisticos(valores) {
    const campos = {
      eventos: "eventos",
      fallecidos: "fallecidos",
      afectados: "afectados",
      dano_ajustado: "dano_mxn",
      prom_fallecidos: "prom_fallecidos",
      prom_afectados: "prom_afectados",
    };
    const lista = Object.values(valores);
    const salida = {};

    Object.keys(campos).forEach((variable) => {
      const campo = campos[variable];
      const serie = lista
        .map((v) => {
          if (campo === "prom_fallecidos") return v.eventos ? v.fallecidos / v.eventos : 0;
          if (campo === "prom_afectados") return v.eventos ? v.afectados / v.eventos : 0;
          return v[campo] || 0;
        })
        .filter((n) => n > 0)
        .sort((a, b) => a - b);

      if (!serie.length) {
        salida[variable] = { n: 0, min: 0, p50: 0, p99: 0, max: 0, media: 0 };
        return;
      }
      const cuantil = (p) => serie[Math.min(serie.length - 1, Math.floor(p * serie.length))];
      salida[variable] = {
        n: serie.length,
        min: serie[0],
        p50: cuantil(0.5),
        p75: cuantil(0.75),
        p90: cuantil(0.9),
        p95: cuantil(0.95),
        p99: cuantil(0.99),
        max: serie[serie.length - 1],
        media: serie.reduce((a, b) => a + b, 0) / serie.length,
      };
    });

    return salida;
  }

  /** Recalcula los valores de cada país y los aplica al mapa. */
  function aplicarFiltros() {
    const etiqueta = document.getElementById("valor-periodo");
    const nota = document.getElementById("nota-filtros");
    const filtro = leerFiltros();

    // Cualquier cambio de filtro invalida los rankings calculados.
    rankingsActuales = null;

    const minEl = document.getElementById("filtro-anio-min");
    const maxEl = document.getElementById("filtro-anio-max");
    if (minEl) minEl.value = filtro.a1;
    if (maxEl) maxEl.value = filtro.a2;
    if (etiqueta) etiqueta.textContent = `${filtro.a1} – ${filtro.a2}`;

    const etiquetaMin = document.getElementById("valor-anio-min");
    const etiquetaMax = document.getElementById("valor-anio-max");
    if (etiquetaMin) etiquetaMin.textContent = filtro.a1;
    if (etiquetaMax) etiquetaMax.textContent = filtro.a2;

    const sinCambios =
      filtro.a1 === periodoFiltros.inicio &&
      filtro.a2 === periodoFiltros.fin &&
      filtro.tipo === "todos";

    if (!filtro.activo || sinCambios) {
      CapaTematica.quitarFiltro();
      actualizarTarjetas();
      aplicarFiltroIncendios();
      if (nota) {
        nota.textContent = filtro.activo
          ? "Mostrando todos los desastres del periodo completo."
          : "Los filtros no están aplicados al mapa.";
      }
      if (codigoSeleccionado) actualizarPanelPais(codigoSeleccionado);
      return;
    }

    if (!datosFiltros || !datosFiltros.datos) {
      if (nota) nota.textContent = "No se pudieron cargar los datos de los filtros.";
      return;
    }

    const valores = {};
    let totalEventos = 0;

    Object.keys(datosFiltros.datos).forEach((iso) => {
      let eventos = 0;
      let fallecidos = 0;
      let afectados = 0;
      let dano = 0;

      datosFiltros.datos[iso].forEach((fila) => {
        if (fila[0] < filtro.a1 || fila[0] > filtro.a2) return;
        if (filtro.tipo !== "todos" && fila[1] !== filtro.tipo) return;
        eventos += fila[2];
        fallecidos += fila[3];
        afectados += fila[4];
        dano += fila[5];
      });

      if (eventos > 0) {
        valores[iso] = {
          eventos,
          fallecidos,
          afectados,
          dano_mxn: dano,
        };
        totalEventos += eventos;
      }
    });

    CapaTematica.setFiltro(valores, calcularEstadisticos(valores));
    actualizarTarjetas();
    aplicarFiltroIncendios();

    if (nota) {
      const tipoTexto =
        filtro.tipo === "todos" ? "todos los tipos" : traducirTipoDesastre(filtro.tipo);
      nota.textContent =
        `Mostrando ${totalEventos.toLocaleString("es-MX")} eventos · ` +
        `${tipoTexto} · ${filtro.a1} – ${filtro.a2}`;
    }

    if (codigoSeleccionado) actualizarPanelPais(codigoSeleccionado);
  }

  /* ---------------------------------------------------------------------- *
   * 7. Tarjetas de resumen                                                 *
   * ---------------------------------------------------------------------- */
  function actualizarTarjetas() {
    const metadatos = CapaTematica.estado.metadatos;
    const territorios = CapaTematica.estado.territorios;
    const variable = CapaTematica.estado.variableColor;
    const definicion = metadatos.variables[variable];
    const stats =
      typeof CapaTematica.estadisticos === "function"
        ? CapaTematica.estadisticos(variable)
        : definicion.estadisticos;

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
        titulo: "Máximo por territorio",
        valor: Escalas.formatearValor(stats.max, definicion.formato),
        nota: definicion.etiqueta,
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
        cargarDatosFiltros(),
        cargarDatosPanel(),
      ]);

      await crearMapa();

      CapaTematica.iniciar(mapa, geojson, metadatos);

      poblarSelectores(metadatos);
      conectarControles();
      conectarInteraccion();
      actualizarTarjetas();
      fichaInicial();
      poblarFiltroTipos();
      conectarPestanas();

      // Ventana de detalle por país (Actividad 5).
      if (ui.modalCerrar) {
        ui.modalCerrar.addEventListener("click", cerrarModalPais);
      }
      if (ui.modal) {
        ui.modal.addEventListener("click", (evento) => {
          if (evento.target === ui.modal) cerrarModalPais();
        });
      }
      if (ui.btnAbrirPanel) {
        ui.btnAbrirPanel.addEventListener("click", () => {
          if (codigoSeleccionado) abrirModalPais(codigoSeleccionado);
        });
      }
      if (ui.chkIncendios) {
        ui.chkIncendios.addEventListener("change", (evento) =>
          alternarIncendios(evento.target.checked)
        );
      }

      const minEl = document.getElementById("filtro-anio-min");
      const maxEl = document.getElementById("filtro-anio-max");
      const tipoEl = document.getElementById("selector-tipo");
      const chkEl = document.getElementById("chk-aplicar-filtros");
      const btnReset = document.getElementById("btn-reset-filtros");

      if (minEl && maxEl) {
        minEl.min = periodoFiltros.inicio;
        minEl.max = periodoFiltros.fin;
        minEl.value = periodoFiltros.inicio;
        maxEl.min = periodoFiltros.inicio;
        maxEl.max = periodoFiltros.fin;
        maxEl.value = periodoFiltros.fin;
      }
      const etiquetaPeriodo = document.getElementById("valor-periodo");
      if (etiquetaPeriodo) {
        etiquetaPeriodo.textContent = `${periodoFiltros.inicio} – ${periodoFiltros.fin}`;
      }

      [minEl, maxEl].forEach((el) => {
        if (el) el.addEventListener("input", aplicarFiltros);
      });
      if (tipoEl) tipoEl.addEventListener("change", aplicarFiltros);
      if (chkEl) chkEl.addEventListener("change", aplicarFiltros);

      if (btnReset) {
        btnReset.addEventListener("click", () => {
          if (minEl) minEl.value = periodoFiltros.inicio;
          if (maxEl) maxEl.value = periodoFiltros.fin;
          if (tipoEl) tipoEl.value = "todos";
          if (chkEl) chkEl.checked = true;
          aplicarFiltros();
        });
      }

      aplicarFiltros();

      // Nota metodológica desde los metadatos.
      document.getElementById("nota-metodologica").textContent =
        `${metadatos.fuente}. Periodo ${metadatos.periodo.inicio}–` +
        `${metadatos.periodo.fin} · ${metadatos.n_eventos.toLocaleString(
          "es-MX"
        )} eventos. La ausencia de indicadores no implica ausencia de ` +
        `desastres. Los territorios sin datos se muestran con color neutro.`;

      // API mínima para pruebas automáticas y documentación.
      window.AtlasApp = {
        mapa,
        abrirPais: abrirModalPais,
        seleccionar: (codigo) => {
          CapaTematica.setSeleccionado(codigo);
          mostrarFicha(codigo);
          actualizarPanelPais(codigo);
        },
      };

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



  /* ---------------------------------------------------------------------- *
   * 9. Panel de información por país (Actividad 5)                         *
   * ---------------------------------------------------------------------- */

  let grafEvolucionChart = null;
  let grafTiposChart = null;
  let grafImpactoChart = null;

  // Paleta de las gráficas, derivada de la identidad visual.
  const PALETA_GRAFICAS = [
    "#4c1d95",
    "#ee3e29",
    "#ffb71b",
    "#fa8a9a",
    "#6d3bc0",
    "#ff8a5f",
    "#a855c9",
    "#f9a8b2",
  ];

  const numero = new Intl.NumberFormat("es-MX");

  function formatearNumeroPais(n) {
    if (n === null || n === undefined || Number.isNaN(n)) return "—";
    return numero.format(Math.round(n));
  }

  function formatearDanoPais(n) {
    if (!n) return "—";
    return Escalas.formatearValor(n, "moneda");
  }

  function formatearSuperficie(n) {
    if (!n) return "—";
    return `${numero.format(Math.round(n))} km²`;
  }

  function formatearDecimal(n, decimales = 1) {
    if (n === null || n === undefined || Number.isNaN(n)) return "—";
    return Number(n).toLocaleString("es-MX", {
      minimumFractionDigits: decimales,
      maximumFractionDigits: decimales,
    });
  }

  /**
   * Filtro que se aplica al panel. Si el usuario desactivó la casilla
   * "Aplicar los filtros al mapa", el panel vuelve al periodo completo.
   */
  function filtroEfectivo() {
    const filtro = leerFiltros();
    if (filtro.activo) return filtro;
    return {
      a1: periodoFiltros.inicio,
      a2: periodoFiltros.fin,
      tipo: "todos",
      activo: false,
    };
  }

  /* ---------------------- 9.1 Resumen del país ------------------------ */

  /** Resumen de un país aplicando el periodo y el tipo seleccionados. */
  function infoPaisFiltrada(codigo) {
    const filtro = filtroEfectivo();
    const filas = (datosFiltros && datosFiltros.datos[codigo]) || [];
    const porAnio = {};
    const porTipo = {};
    let totalEventos = 0;
    let totalFallecidos = 0;
    let totalAfectados = 0;
    let totalDano = 0;

    filas.forEach((fila) => {
      const anio = fila[0];
      const tipoFila = fila[1];

      if (anio < filtro.a1 || anio > filtro.a2) return;
      if (filtro.tipo !== "todos" && tipoFila !== filtro.tipo) return;

      totalEventos += fila[2];
      totalFallecidos += fila[3];
      totalAfectados += fila[4];
      totalDano += fila[5];

      if (!porAnio[anio]) {
        porAnio[anio] = { anio, eventos: 0, fallecidos: 0, afectados: 0, dano_mxn: 0 };
      }
      porAnio[anio].eventos += fila[2];
      porAnio[anio].fallecidos += fila[3];
      porAnio[anio].afectados += fila[4];
      porAnio[anio].dano_mxn += fila[5];

      if (!porTipo[tipoFila]) {
        porTipo[tipoFila] = {
          tipo: tipoFila,
          eventos: 0,
          fallecidos: 0,
          afectados: 0,
          dano_mxn: 0,
        };
      }
      porTipo[tipoFila].eventos += fila[2];
      porTipo[tipoFila].fallecidos += fila[3];
      porTipo[tipoFila].afectados += fila[4];
      porTipo[tipoFila].dano_mxn += fila[5];
    });

    const anios = Object.keys(porAnio)
      .map((k) => porAnio[k])
      .sort((a, b) => a.anio - b.anio);
    const tipos = Object.keys(porTipo)
      .map((k) => porTipo[k])
      .sort((a, b) => b.eventos - a.eventos);

    return {
      filtro,
      totales: {
        eventos: totalEventos,
        fallecidos: totalFallecidos,
        afectados: totalAfectados,
        dano_mxn: totalDano,
        primer_anio: anios.length ? anios[0].anio : null,
        ultimo_anio: anios.length ? anios[anios.length - 1].anio : null,
      },
      por_anio: anios,
      por_tipo: tipos,
    };
  }

  /* --------------------- 9.2 Rankings mundiales ----------------------- */

  /** Posición del país entre los territorios con datos, según el filtro. */
  function calcularRankings() {
    if (rankingsActuales) return rankingsActuales;
    if (!datosFiltros || !datosFiltros.datos) return null;

    const filtro = filtroEfectivo();
    const lista = [];

    Object.keys(datosFiltros.datos).forEach((iso) => {
      let eventos = 0;
      let fallecidos = 0;
      let afectados = 0;
      let dano = 0;

      datosFiltros.datos[iso].forEach((fila) => {
        if (fila[0] < filtro.a1 || fila[0] > filtro.a2) return;
        if (filtro.tipo !== "todos" && fila[1] !== filtro.tipo) return;
        eventos += fila[2];
        fallecidos += fila[3];
        afectados += fila[4];
        dano += fila[5];
      });

      if (eventos > 0) {
        lista.push({ iso, eventos, victimas: fallecidos + afectados, dano });
      }
    });

    const construirPuestos = (campo) => {
      const orden = [...lista].sort((a, b) => b[campo] - a[campo]);
      const puestos = {};
      orden.forEach((fila, indice) => {
        const previo = indice > 0 ? orden[indice - 1] : null;
        if (previo && fila[campo] === previo[campo]) {
          puestos[fila.iso] = puestos[previo.iso];
        } else {
          puestos[fila.iso] = indice + 1;
        }
      });
      return puestos;
    };

    rankingsActuales = {
      eventos: construirPuestos("eventos"),
      victimas: construirPuestos("victimas"),
      dano: construirPuestos("dano"),
      n: lista.length,
    };
    return rankingsActuales;
  }

  /* ------------------- 9.3 Comparación de periodos -------------------- */

  /** Totales del periodo actual y de un intervalo de comparación. */
  function compararPeriodo(codigo, filtro) {
    const filas = (datosFiltros && datosFiltros.datos[codigo]) || [];
    const largo = filtro.a2 - filtro.a1 + 1;

    const sumar = (desde, hasta) => {
      let eventos = 0;
      let fallecidos = 0;
      let afectados = 0;
      let dano = 0;
      filas.forEach((fila) => {
        if (fila[0] < desde || fila[0] > hasta) return;
        if (filtro.tipo !== "todos" && fila[1] !== filtro.tipo) return;
        eventos += fila[2];
        fallecidos += fila[3];
        afectados += fila[4];
        dano += fila[5];
      });
      return { eventos, fallecidos, afectados, dano };
    };

    const anteriorDesde = filtro.a1 - largo;
    const anteriorHasta = filtro.a1 - 1;

    // Si el periodo anterior cae fuera del dataset, divido el periodo
    // seleccionado en dos mitades para que la comparación siga teniendo
    // sentido con el rango completo (2000–2026).
    if (anteriorDesde < periodoFiltros.inicio && largo >= 2) {
      const mitad = Math.floor((filtro.a1 + filtro.a2) / 2);
      return {
        modo: "mitades",
        anterior: sumar(filtro.a1, mitad),
        actual: sumar(mitad + 1, filtro.a2),
        etiquetaAnterior: `${filtro.a1}–${mitad}`,
        etiquetaActual: `${mitad + 1}–${filtro.a2}`,
      };
    }

    if (anteriorDesde < periodoFiltros.inicio) {
      return {
        modo: "sin",
        anterior: { eventos: 0, fallecidos: 0, afectados: 0, dano: 0 },
        actual: sumar(filtro.a1, filtro.a2),
        etiquetaAnterior: "—",
        etiquetaActual: `${filtro.a1}`,
      };
    }

    return {
      modo: "anterior",
      anterior: sumar(anteriorDesde, anteriorHasta),
      actual: sumar(filtro.a1, filtro.a2),
      etiquetaAnterior: `${anteriorDesde}–${anteriorHasta}`,
      etiquetaActual: `${filtro.a1}–${filtro.a2}`,
    };
  }

  /* --------------------- 9.4 Eventos del país ------------------------- */

  /** Eventos del país que caen dentro del periodo y tipo seleccionados. */
  function eventosFiltrados(codigo, filtro) {
    const filas = (datosEventos && datosEventos.paises[codigo]) || [];
    return filas.filter(
      ([anio, tipo]) =>
        anio >= filtro.a1 &&
        anio <= filtro.a2 &&
        (filtro.tipo === "todos" || tipo === filtro.tipo)
    );
  }

  /** Dibuja una lista de eventos ordenada por el campo indicado. */
  function pintarEventos(contenedor, eventos, campo, maximo = 5) {
    if (!contenedor) return;

    const orden = eventos
      .map(([anio, tipo, fallecidos, afectados, dano, nombre]) => ({
        anio,
        tipo,
        nombre,
        valor:
          campo === "dano"
            ? dano || 0
            : (fallecidos || 0) + (afectados || 0),
        detalle:
          campo === "dano"
            ? Escalas.formatearValor(dano || 0, "moneda")
            : (fallecidos || 0) >= (afectados || 0)
            ? `${formatearNumeroPais(fallecidos || 0)} fallecidos`
            : `${formatearNumeroPais(afectados || 0)} afectados`,
      }))
      .filter((evento) => evento.valor > 0)
      .sort((a, b) => b.valor - a.valor)
      .slice(0, maximo);

    if (!orden.length) {
      contenedor.innerHTML = `<li class="vacio">Sin registros con los filtros actuales.</li>`;
      return;
    }

    contenedor.innerHTML = orden
      .map(
        (evento, indice) => `
        <li class="evento">
          <span class="evento__puesto">${indice + 1}</span>
          <span class="evento__detalle">
            <span class="evento__titulo">${traducirTipoDesastre(evento.tipo)}${
          evento.nombre ? ` · ${evento.nombre}` : ""
        }</span>
            <span class="evento__meta">${evento.anio}</span>
          </span>
          <span class="evento__valor">${evento.detalle}</span>
        </li>`
      )
      .join("");
  }

  /* --------------------- 9.5 Contexto OWID ---------------------------- */

  function contextoOwid(codigo, filtro) {
    const filas = (datosOwid && datosOwid.paises[codigo]) || [];
    const enPeriodo = filas.filter(([anio]) => anio >= filtro.a1 && anio <= filtro.a2);

    return enPeriodo.reduce(
      (acumulado, [, afectados, pequenos, medianos, grandes]) => ({
        afectados: acumulado.afectados + afectados,
        pequenos: acumulado.pequenos + pequenos,
        medianos: acumulado.medianos + medianos,
        grandes: acumulado.grandes + grandes,
      }),
      { afectados: 0, pequenos: 0, medianos: 0, grandes: 0 }
    );
  }

  /* -------------------- 9.6 Incendios de México ----------------------- */

  function incendiosEnPeriodo(filtro) {
    if (!datosIncendios) return null;

    const [inicio, fin] = datosIncendios.meta.periodo;
    const desde = Math.max(filtro.a1, inicio);
    const hasta = Math.min(filtro.a2, fin);
    if (hasta < desde) return { vacio: true, desde, hasta };

    const anual = datosIncendios.anual.filter(
      ([anio]) => anio >= desde && anio <= hasta
    );

    const estados = datosIncendios.estados_anual
      .map(([nombre, serie]) => {
        const delPeriodo = serie.filter(([anio]) => anio >= desde && anio <= hasta);
        return [
          nombre,
          delPeriodo.reduce((suma, fila) => suma + fila[2], 0),
        ];
      })
      .filter(([, hectareas]) => hectareas > 0)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 6);

    const causas = datosIncendios.causas_anual
      .map(([nombre, serie]) => {
        const delPeriodo = serie.filter(([anio]) => anio >= desde && anio <= hasta);
        return [nombre, delPeriodo.reduce((suma, fila) => suma + fila[1], 0)];
      })
      .filter(([, total]) => total > 0)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 6);

    return {
      vacio: false,
      desde,
      hasta,
      incendios: anual.reduce((suma, fila) => suma + fila[1], 0),
      hectareas: anual.reduce((suma, fila) => suma + fila[2], 0),
      estados,
      causas,
    };
  }

  function pintarBarras(contenedor, filas, formatear, clase = "") {
    if (!contenedor) return;
    if (!filas.length) {
      contenedor.innerHTML = `<p class="nota">Sin datos en el periodo.</p>`;
      return;
    }
    const maximo = Math.max(...filas.map(([, valor]) => valor), 1);
    contenedor.innerHTML = filas
      .map(
        ([nombre, valor]) => `
        <div class="barra">
          <span class="barra__nombre" title="${nombre}">${nombre}</span>
          <span class="barra__pista">
            <span class="barra__relleno ${clase}" style="width:${(
          (100 * valor) / maximo
        ).toFixed(1)}%"></span>
          </span>
          <span class="barra__valor">${formatear(valor)}</span>
        </div>`
      )
      .join("");
  }

  /* ---------------------- 9.7 Render del panel ------------------------ */

  function kpi(etiqueta, valor, nota, destacado = false) {
    return `
      <div class="kpi ${destacado ? "kpi--destacado" : ""}">
        <span class="kpi__etiqueta">${etiqueta}</span>
        <span class="kpi__valor">${valor}</span>
        ${nota ? `<span class="kpi__nota">${nota}</span>` : ""}
      </div>`;
  }

  function ranking(etiqueta, puesto, total, clase) {
    if (!puesto) return "";
    return `
      <div class="ranking ranking--${clase}">
        <span class="ranking__puesto">#${puesto}</span>
        <span>${etiqueta} <strong>de ${total}</strong></span>
      </div>`;
  }

  /** Pinta la ventana de detalle del país seleccionado. */
  function renderPanelPais() {
    const codigo = paisActual;
    if (!codigo) return;

    const territorio = CapaTematica.territorio(codigo);
    if (!territorio) return;

    const info = infoPaisFiltrada(codigo);
    const filtro = info.filtro;
    const socio = (datosSocio && datosSocio.paises[codigo]) || {};
    const rankings = calcularRankings();

    const setTxt = (id, texto) => {
      const el = document.getElementById(id);
      if (el) el.textContent = texto;
    };

    // --- cabecera -------------------------------------------------------
    setTxt("modal-nombre", territorio.nombre);
    setTxt(
      "modal-meta",
      `${codigo} · ${territorio.continente || "—"} · ${filtro.a1}–${filtro.a2}`
    );
    setTxt("modal-badge", territorio.disponibilidad);

    // --- tarjetas -------------------------------------------------------
    const t = info.totales;
    const anioSocio = socio.anio ? `Datos de ${Math.round(socio.anio)}` : "";
    const kpis = [
      kpi("Población", formatearNumeroPais(socio.poblacion), anioSocio, true),
      kpi("Superficie", formatearSuperficie(socio.superficie_km2), "Territorio"),
      kpi("PIB", formatearDanoPais(socio.pib_mxn), anioSocio),
      kpi("PIB por habitante", formatearDanoPais(socio.pib_pc_mxn), "Pesos mexicanos"),
      kpi(
        "Densidad",
        socio.densidad ? `${formatearDecimal(socio.densidad)}` : "—",
        "habitantes por km²"
      ),
      kpi(
        "Eventos",
        formatearNumeroPais(t.eventos),
        t.primer_anio ? `${t.primer_anio}–${t.ultimo_anio}` : "Sin registros",
        true
      ),
      kpi("Fallecidos", formatearNumeroPais(t.fallecidos), "Total del periodo"),
      kpi("Afectados", formatearNumeroPais(t.afectados), "Total del periodo"),
      kpi("Daño económico", formatearDanoPais(t.dano_mxn), "Pesos mexicanos", true),
    ];
    document.getElementById("modal-kpis").innerHTML = kpis.join("");

    // --- rankings -------------------------------------------------------
    const contenedorRankings = document.getElementById("modal-rankings");
    if (rankings) {
      contenedorRankings.innerHTML = [
        ranking("en eventos", rankings.eventos[codigo], rankings.n, "eventos"),
        ranking("en víctimas", rankings.victimas[codigo], rankings.n, "victimas"),
        ranking("en daño económico", rankings.dano[codigo], rankings.n, "dano"),
      ].join("");
      setTxt(
        "nota-ranking",
        `Posición entre los ${rankings.n} territorios con registros en ${filtro.a1}–${filtro.a2}.`
      );
    } else {
      contenedorRankings.innerHTML = "";
      setTxt("nota-ranking", "Sin datos suficientes para calcular la posición.");
    }

    // --- evolución temporal --------------------------------------------
    if (grafEvolucionChart) {
      grafEvolucionChart.destroy();
      grafEvolucionChart = null;
    }
    const ctxEvolucion = document.getElementById("graf-evolucion");
    if (ctxEvolucion && window.Chart && info.por_anio.length) {
      grafEvolucionChart = new Chart(ctxEvolucion, {
        type: "line",
        data: {
          labels: info.por_anio.map((x) => x.anio),
          datasets: [
            {
              label: "Eventos",
              data: info.por_anio.map((x) => x.eventos),
              borderColor: "#4c1d95",
              backgroundColor: "rgba(76, 29, 149, 0.12)",
              fill: true,
              tension: 0.3,
              pointRadius: 0,
              borderWidth: 2.2,
              yAxisID: "y",
            },
            {
              label: "Fallecidos",
              data: info.por_anio.map((x) => x.fallecidos),
              borderColor: "#ee3e29",
              backgroundColor: "#ee3e29",
              tension: 0.3,
              pointRadius: 0,
              borderWidth: 2,
              borderDash: [5, 4],
              yAxisID: "y1",
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: { mode: "index", intersect: false },
          plugins: {
            legend: { labels: { boxWidth: 10, font: { size: 10 }, color: "#3c3358" } },
          },
          scales: {
            x: { ticks: { font: { size: 10 }, color: "#7a7191" }, grid: { display: false } },
            y: {
              position: "left",
              ticks: { font: { size: 10 }, color: "#4c1d95" },
              grid: { color: "rgba(76,29,149,0.08)" },
              beginAtZero: true,
            },
            y1: {
              position: "right",
              ticks: { font: { size: 10 }, color: "#ee3e29" },
              grid: { display: false },
              beginAtZero: true,
            },
          },
        },
      });
    }
    setTxt(
      "nota-evolucion",
      info.por_anio.length
        ? `${info.por_anio.length} años con registros entre ${filtro.a1} y ${filtro.a2}. El eje derecho corresponde a fallecidos.`
        : "Sin registros anuales con los filtros actuales."
    );

    // --- impacto humano por año ----------------------------------------
    if (grafImpactoChart) {
      grafImpactoChart.destroy();
      grafImpactoChart = null;
    }
    const ctxImpacto = document.getElementById("graf-impacto");
    if (ctxImpacto && window.Chart && info.por_anio.length) {
      grafImpactoChart = new Chart(ctxImpacto, {
        type: "bar",
        data: {
          labels: info.por_anio.map((x) => x.anio),
          datasets: [
            {
              label: "Fallecidos",
              data: info.por_anio.map((x) => x.fallecidos),
              backgroundColor: "#ffb71b",
              borderRadius: 5,
              maxBarThickness: 22,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            x: { ticks: { font: { size: 10 }, color: "#7a7191" }, grid: { display: false } },
            y: {
              ticks: { font: { size: 10 }, color: "#7a7191" },
              grid: { color: "rgba(76,29,149,0.08)" },
              beginAtZero: true,
            },
          },
        },
      });
    }

    // --- distribución por tipo -----------------------------------------
    if (grafTiposChart) {
      grafTiposChart.destroy();
      grafTiposChart = null;
    }
    const ctxTipos = document.getElementById("graf-tipos");
    const tipos = info.por_tipo.slice(0, 7);
    if (ctxTipos && window.Chart && tipos.length) {
      grafTiposChart = new Chart(ctxTipos, {
        type: "doughnut",
        data: {
          labels: tipos.map((x) => traducirTipoDesastre(x.tipo)),
          datasets: [
            {
              data: tipos.map((x) => x.eventos),
              backgroundColor: PALETA_GRAFICAS,
              borderColor: "#ffffff",
              borderWidth: 2,
              hoverOffset: 6,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          cutout: "58%",
          plugins: {
            legend: {
              position: "bottom",
              labels: { boxWidth: 9, font: { size: 10 }, color: "#3c3358", padding: 10 },
            },
          },
        },
      });
    }
    setTxt(
      "nota-tipos",
      tipos.length
        ? `${tipos.length} tipos con registros. Total: ${formatearNumeroPais(t.eventos)} eventos.`
        : "Sin registros de tipos con los filtros actuales."
    );

    // --- comparación de periodos ---------------------------------------
    const comparacion = compararPeriodo(codigo, filtro);
    pintarComparativa(comparacion, filtro);

    // --- eventos destacados --------------------------------------------
    const eventos = eventosFiltrados(codigo, filtro);
    pintarEventos(document.getElementById("lista-victimas"), eventos, "victimas");
    pintarEventos(document.getElementById("lista-dano"), eventos, "dano");

    // --- bloque de México ----------------------------------------------
    renderBloqueMexico(codigo, filtro);

    // --- contexto OWID --------------------------------------------------
    renderBloqueOwid(codigo, filtro);
  }

  function pintarComparativa(comparacion, filtro) {
    const contenedor = document.getElementById("comparativa");
    const nota = document.getElementById("nota-comparacion");
    const titulo = document.getElementById("titulo-comparacion");
    if (!contenedor) return;

    if (titulo) {
      titulo.textContent =
        comparacion.modo === "anterior"
          ? "Periodo actual contra periodo anterior"
          : comparacion.modo === "mitades"
          ? "Primera mitad contra segunda mitad"
          : "Comparación de periodos";
    }

    const filas = [
      ["Eventos", comparacion.anterior.eventos, comparacion.actual.eventos, "entero"],
      ["Fallecidos", comparacion.anterior.fallecidos, comparacion.actual.fallecidos, "entero"],
      ["Afectados", comparacion.anterior.afectados, comparacion.actual.afectados, "entero"],
      ["Daño", comparacion.anterior.dano, comparacion.actual.dano, "moneda"],
    ];

    const formatear = (valor, formato) =>
      formato === "moneda"
        ? Escalas.formatearValor(valor, "moneda")
        : formatearNumeroPais(valor);

    const cambio = (antes, ahora) => {
      if (!antes && !ahora) return ["igual", "—"];
      if (!antes) return ["sube", "nuevo"];
      const porcentaje = ((ahora - antes) / antes) * 100;
      if (Math.abs(porcentaje) < 0.5) return ["igual", "0%"];
      return [
        porcentaje > 0 ? "sube" : "baja",
        `${porcentaje > 0 ? "+" : ""}${porcentaje.toFixed(1)}%`,
      ];
    };

    const encabezado = `
      <div class="comparativa__fila comparativa__cabecera">
        <span class="comparativa__etiqueta">Indicador</span>
        <span class="comparativa__valor">${comparacion.etiquetaAnterior}</span>
        <span class="comparativa__valor comparativa__valor--actual">${comparacion.etiquetaActual}</span>
        <span class="comparativa__cambio">Cambio</span>
      </div>`;

    const cuerpo = filas
      .map(([etiqueta, antes, ahora, formato]) => {
        const [clase, texto] = cambio(antes, ahora);
        return `
        <div class="comparativa__fila">
          <span class="comparativa__etiqueta">${etiqueta}</span>
          <span class="comparativa__valor">${formatear(antes, formato)}</span>
          <span class="comparativa__valor comparativa__valor--actual">${formatear(ahora, formato)}</span>
          <span class="comparativa__cambio ${clase}">${texto}</span>
        </div>`;
      })
      .join("");

    contenedor.innerHTML = encabezado + cuerpo;

    if (nota) {
      nota.textContent =
        comparacion.modo === "anterior"
          ? `Periodo ${comparacion.etiquetaActual} contra ${comparacion.etiquetaAnterior}, ambos del mismo tamaño.`
          : comparacion.modo === "mitades"
          ? `El periodo completo (${filtro.a1}–${filtro.a2}) no tiene un intervalo anterior dentro del dataset, así que se comparan sus dos mitades.`
          : "El periodo seleccionado es demasiado corto para compararlo.";
    }
  }

  function renderBloqueMexico(codigo, filtro) {
    const bloque = document.getElementById("bloque-mexico");
    if (!bloque) return;

    if (codigo !== "MEX" || !datosIncendios) {
      bloque.hidden = true;
      return;
    }

    const resumen = incendiosEnPeriodo(filtro);
    if (!resumen || resumen.vacio) {
      bloque.hidden = false;
      document.getElementById("mexico-resumen").innerHTML = "";
      document.getElementById("mexico-estados").innerHTML = "";
      document.getElementById("mexico-causas").innerHTML = "";
      document.getElementById("nota-mexico").textContent =
        "El periodo seleccionado no coincide con los datos de CONAFOR (2015–2025).";
      return;
    }

    bloque.hidden = false;
    document.getElementById("mexico-resumen").innerHTML = [
      kpi("Incendios", formatearNumeroPais(resumen.incendios), `${resumen.desde}–${resumen.hasta}`, true),
      kpi("Superficie afectada", `${formatearNumeroPais(resumen.hectareas)} ha`, "Hectáreas"),
      kpi(
        "Promedio por incendio",
        `${formatearDecimal(resumen.incendios ? resumen.hectareas / resumen.incendios : 0)} ha`,
        "Hectáreas"
      ),
      kpi(
        "Estado más afectado",
        resumen.estados.length ? resumen.estados[0][0] : "—",
        resumen.estados.length
          ? `${formatearNumeroPais(resumen.estados[0][1])} ha`
          : ""
      ),
    ].join("");

    pintarBarras(
      document.getElementById("mexico-estados"),
      resumen.estados,
      (valor) => `${formatearNumeroPais(valor)} ha`
    );
    pintarBarras(
      document.getElementById("mexico-causas"),
      resumen.causas,
      (valor) => formatearNumeroPais(valor),
      "barra__relleno--purpura"
    );

    document.getElementById("nota-mexico").textContent =
      `Fuente: CONAFOR. ${formatearNumeroPais(datosIncendios.total.incendios)} incendios ` +
      `y ${formatearNumeroPais(datosIncendios.total.hectareas)} hectáreas entre ` +
      `${datosIncendios.meta.periodo[0]} y ${datosIncendios.meta.periodo[1]}. ` +
      `Los atlas de riesgos se revisaron y se descartaron por no tener una fuente nacional reproducible.`;
  }

  function renderBloqueOwid(codigo, filtro) {
    const contenedor = document.getElementById("owid-resumen");
    const nota = document.getElementById("nota-owid");
    if (!contenedor) return;

    const contexto = contextoOwid(codigo, filtro);
    const totalEventos =
      contexto.pequenos + contexto.medianos + contexto.grandes;

    if (!totalEventos && !contexto.afectados) {
      contenedor.innerHTML = "";
      if (nota) nota.textContent = "OWID no reporta datos para este país en el periodo.";
      return;
    }

    contenedor.innerHTML = [
      kpi("Afectados (OWID)", formatearNumeroPais(contexto.afectados), "Referencia externa"),
      kpi("Eventos pequeños", formatearNumeroPais(contexto.pequenos), "Baja magnitud"),
      kpi("Eventos medianos", formatearNumeroPais(contexto.medianos), "Magnitud media"),
      kpi("Eventos grandes", formatearNumeroPais(contexto.grandes), "Alta magnitud"),
    ].join("");

    if (nota) {
      nota.textContent =
        "OWID agrega EM-DAT con otro criterio, así que sus cifras pueden diferir del panel; sirven como referencia de orden de magnitud.";
    }
  }

  /** Sincroniza la ficha lateral y, si está abierta, la ventana de detalle. */
  function actualizarPanelPais(codigo) {
    codigoSeleccionado = codigo || null;

    if (ui.btnAbrirPanel) {
      ui.btnAbrirPanel.disabled = !codigo;
      if (!codigo) ui.btnAbrirPanel.textContent = "Abrir panel detallado";
    }

    if (codigo && ui.modal && ui.modal.open && paisActual === codigo) {
      renderPanelPais();
    }
  }

  /* ------------------- 9.8 Capa de incendios -------------------------- */

  async function alternarIncendios(activo) {
    const nota = document.getElementById("nota-incendios");

    if (!activo) {
      if (mapa.getLayer("incendios-capa")) {
        mapa.setLayoutProperty("incendios-capa", "visibility", "none");
      }
      if (nota) nota.textContent = "Capa de incendios desactivada.";
      return;
    }

    try {
      if (!incendiosListos) {
        const datos = await cargarJSON(CONFIG.rutaPuntosIncendios);
        mapa.addSource("incendios", { type: "geojson", data: datos });
        mapa.addLayer({
          id: "incendios-capa",
          type: "circle",
          source: "incendios",
          paint: {
            "circle-radius": [
              "interpolate",
              ["linear"],
              ["get", "h"],
              50, 2.2,
              300, 3.8,
              1000, 6,
              3000, 9,
            ],
            "circle-color": [
              "interpolate",
              ["linear"],
              ["get", "h"],
              50, "#ffb71b",
              300, "#ff8a5f",
              1000, "#ee3e29",
              3000, "#8c1d12",
            ],
            "circle-opacity": 0.66,
            "circle-stroke-width": 0.5,
            "circle-stroke-color": "rgba(255, 255, 255, 0.55)",
          },
        });
        incendiosListos = true;
      } else {
        mapa.setLayoutProperty("incendios-capa", "visibility", "visible");
      }

      aplicarFiltroIncendios();

      if (nota) {
        nota.textContent = datosIncendios
          ? `${formatearNumeroPais(datosIncendios.total.incendios)} incendios registrados por CONAFOR (2015–2025). Se dibujan los de 50 ha o más.`
          : "Incendios de 50 hectáreas o más.";
      }
    } catch (error) {
      console.error(error);
      if (nota) nota.textContent = "No se pudo cargar la capa de incendios.";
    }
  }

  function aplicarFiltroIncendios() {
    if (!incendiosListos) return;
    const filtro = filtroEfectivo();
    const desde = Math.max(filtro.a1, 2015);
    const hasta = Math.min(filtro.a2, 2025);
    mapa.setFilter("incendios-capa", [
      "all",
      [">=", ["get", "a"], desde],
      ["<=", ["get", "a"], hasta],
    ]);
  }

  document.addEventListener("DOMContentLoaded", iniciar);
})();
