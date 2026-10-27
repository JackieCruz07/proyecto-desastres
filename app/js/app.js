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
      const props = e.features[0].properties || {};
      const codigo = props.codigo || props.iso_a3 || props.ISO_A3 || props.adm0_a3 || props.iso3 || props.ISO3 || props.sov_a3;
      CapaTematica.setSeleccionado(codigo);
      mostrarFicha(codigo);
      if (typeof actualizarPanelPais === "function") {
        actualizarPanelPais(codigo, props);
      }
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
      dano_ajustado: "dano_usd",
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

    const minEl = document.getElementById("filtro-anio-min");
    const maxEl = document.getElementById("filtro-anio-max");
    if (minEl) minEl.value = filtro.a1;
    if (maxEl) maxEl.value = filtro.a2;
    if (etiqueta) etiqueta.textContent = `${filtro.a1} – ${filtro.a2}`;

    const sinCambios =
      filtro.a1 === periodoFiltros.inicio &&
      filtro.a2 === periodoFiltros.fin &&
      filtro.tipo === "todos";

    if (!filtro.activo || sinCambios) {
      CapaTematica.quitarFiltro();
      actualizarTarjetas();
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
          dano_usd: dano,
        };
        totalEventos += eventos;
      }
    });

    CapaTematica.setFiltro(valores, calcularEstadisticos(valores));
    actualizarTarjetas();

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
        cargarDatosFiltros(),
      ]);

      await crearMapa();

      CapaTematica.iniciar(mapa, geojson, metadatos);

      poblarSelectores(metadatos);
      conectarControles();
      conectarInteraccion();
      actualizarTarjetas();
      fichaInicial();
      poblarFiltroTipos();

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
   * 8. Panel de información por país (Actividad 5)                         *
   * ---------------------------------------------------------------------- */

  let grafEvolucionChart = null;
  let grafTiposChart = null;
  let grafImpactoChart = null;

  function formatearNumeroPais(n) {
    if (n === null || n === undefined || isNaN(n)) return '—';
    return Number(n).toLocaleString('es-MX');
  }

  function formatearDanoPais(n) {
    if (!n) return '—';
    if (n >= 1e12) return '$' + (n/1e12).toFixed(2) + ' T USD';
    if (n >= 1e9) return '$' + (n/1e9).toFixed(2) + ' MM USD';
    if (n >= 1e6) return '$' + (n/1e6).toFixed(2) + ' M USD';
    return '$' + formatearNumeroPais(Math.round(n)) + ' USD';
  }

  /** Resumen de un país aplicando el periodo y el tipo seleccionados. */
  function infoPaisFiltrada(codigo) {
    const filtro = leerFiltros();
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

      if (filtro.activo) {
        if (anio < filtro.a1 || anio > filtro.a2) return;
        if (filtro.tipo !== "todos" && tipoFila !== filtro.tipo) return;
      }

      totalEventos += fila[2];
      totalFallecidos += fila[3];
      totalAfectados += fila[4];
      totalDano += fila[5];

      if (!porAnio[anio]) {
        porAnio[anio] = { anio, eventos: 0, fallecidos: 0, afectados: 0, dano_usd: 0 };
      }
      porAnio[anio].eventos += fila[2];
      porAnio[anio].fallecidos += fila[3];
      porAnio[anio].afectados += fila[4];
      porAnio[anio].dano_usd += fila[5];

      if (!porTipo[tipoFila]) {
        porTipo[tipoFila] = { tipo: tipoFila, eventos: 0, fallecidos: 0, dano_usd: 0 };
      }
      porTipo[tipoFila].eventos += fila[2];
      porTipo[tipoFila].fallecidos += fila[3];
      porTipo[tipoFila].dano_usd += fila[5];
    });

    if (!totalEventos) return null;

    const anios = Object.keys(porAnio)
      .map((k) => porAnio[k])
      .sort((a, b) => a.anio - b.anio);
    const tipos = Object.keys(porTipo)
      .map((k) => porTipo[k])
      .sort((a, b) => b.eventos - a.eventos);

    return {
      totales: {
        eventos: totalEventos,
        fallecidos: totalFallecidos,
        afectados: totalAfectados,
        dano_usd: totalDano,
        primer_anio: anios.length ? anios[0].anio : null,
        ultimo_anio: anios.length ? anios[anios.length - 1].anio : null,
      },
      por_anio: anios,
      por_tipo: tipos,
    };
  }

  /** Pinta el panel detallado con los datos del país seleccionado. */
  function actualizarPanelPais(codigo) {
    codigoSeleccionado = codigo || null;

    const setTxt = (id, txt) => {
      const el = document.getElementById(id);
      if (el) el.textContent = txt;
    };

    const limpiar = () => {
      if (grafEvolucionChart) { try { grafEvolucionChart.destroy(); } catch (e) {} grafEvolucionChart = null; }
      if (grafTiposChart) { try { grafTiposChart.destroy(); } catch (e) {} grafTiposChart = null; }
      if (grafImpactoChart) { try { grafImpactoChart.destroy(); } catch (e) {} grafImpactoChart = null; }
    };

    const vaciar = (mensaje) => {
      setTxt("det-eventos", "—");
      setTxt("det-fallecidos", "—");
      setTxt("det-afectados", "—");
      setTxt("det-dano", "—");
      setTxt("det-periodo", "—");
      setTxt("det-max-fallecidos", "—");
      setTxt("det-max-eventos", "—");
      setTxt("nota-evolucion", mensaje);
      setTxt("nota-tipos", mensaje);
      const ul = document.getElementById("lista-tipos-top");
      if (ul) ul.innerHTML = codigo ? "<li>Sin datos</li>" : "";
      limpiar();
    };

    if (!codigo) {
      vaciar("Sin datos.");
      return;
    }

    const info = infoPaisFiltrada(codigo);
    if (!info) {
      vaciar("Sin datos para este territorio con los filtros actuales.");
      return;
    }

    const t = info.totales;
    setTxt("det-eventos", formatearNumeroPais(t.eventos));
    setTxt("det-fallecidos", formatearNumeroPais(t.fallecidos));
    setTxt("det-afectados", formatearNumeroPais(t.afectados));
    setTxt("det-dano", formatearDanoPais(t.dano_usd));
    setTxt("det-periodo", t.primer_anio ? `${t.primer_anio} – ${t.ultimo_anio}` : "—");

    if (info.por_anio.length) {
      const maxF = info.por_anio.reduce(
        (m, x) => (x.fallecidos > m.v ? { v: x.fallecidos, a: x.anio } : m),
        { v: -1, a: null }
      );
      const maxE = info.por_anio.reduce(
        (m, x) => (x.eventos > m.v ? { v: x.eventos, a: x.anio } : m),
        { v: -1, a: null }
      );
      setTxt("det-max-fallecidos", maxF.v >= 0 ? `${formatearNumeroPais(maxF.v)} (${maxF.a})` : "—");
      setTxt("det-max-eventos", maxE.v >= 0 ? `${formatearNumeroPais(maxE.v)} (${maxE.a})` : "—");

      const ctxE = document.getElementById("graf-evolucion");
      if (ctxE && window.Chart) {
        if (grafEvolucionChart) grafEvolucionChart.destroy();
        grafEvolucionChart = new Chart(ctxE, {
          type: "line",
          data: {
            labels: info.por_anio.map((x) => x.anio),
            datasets: [
              {
                label: "Eventos",
                data: info.por_anio.map((x) => x.eventos),
                borderColor: "#2563eb",
                backgroundColor: "#2563eb",
                tension: 0.25,
              },
              {
                label: "Fallecidos",
                data: info.por_anio.map((x) => x.fallecidos),
                borderColor: "#dc2626",
                backgroundColor: "#dc2626",
                tension: 0.25,
              },
            ],
          },
          options: {
            responsive: true,
            plugins: { legend: { labels: { boxWidth: 12, font: { size: 10 } } } },
            scales: {
              x: { ticks: { font: { size: 9 } } },
              y: { ticks: { font: { size: 9 } } },
            },
          },
        });
      }
      setTxt("nota-evolucion", `${info.por_anio.length} años con registros.`);

      const ctxI = document.getElementById("graf-impacto");
      if (ctxI && window.Chart) {
        if (grafImpactoChart) grafImpactoChart.destroy();
        grafImpactoChart = new Chart(ctxI, {
          type: "bar",
          data: {
            labels: info.por_anio.map((x) => x.anio),
            datasets: [
              {
                label: "Fallecidos",
                data: info.por_anio.map((x) => x.fallecidos),
                backgroundColor: "#f59e0b",
              },
            ],
          },
          options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: {
              x: { ticks: { font: { size: 9 } } },
              y: { ticks: { font: { size: 9 } } },
            },
          },
        });
      }
    } else {
      limpiar();
      setTxt("nota-evolucion", "Sin registros anuales con los filtros actuales.");
    }

    if (info.por_tipo.length) {
      const top = info.por_tipo.slice(0, 6);
      const ctxT = document.getElementById("graf-tipos");
      if (ctxT && window.Chart) {
        if (grafTiposChart) grafTiposChart.destroy();
        grafTiposChart = new Chart(ctxT, {
          type: "doughnut",
          data: {
            labels: top.map((x) => traducirTipoDesastre(x.tipo)),
            datasets: [
              {
                data: top.map((x) => x.eventos),
                backgroundColor: [
                  "#2563eb",
                  "#22c55e",
                  "#f59e0b",
                  "#ef4444",
                  "#8b5cf6",
                  "#06b6d4",
                ],
              },
            ],
          },
          options: {
            responsive: true,
            plugins: { legend: { position: "bottom", labels: { boxWidth: 10, font: { size: 9 } } } },
          },
        });
      }
      setTxt("nota-tipos", `${top.length} tipos principales mostrados.`);

      const ul = document.getElementById("lista-tipos-top");
      if (ul) {
        ul.innerHTML = "";
        top.forEach((x) => {
          const li = document.createElement("li");
          li.textContent = `${traducirTipoDesastre(x.tipo)}: ${formatearNumeroPais(x.eventos)} eventos`;
          ul.appendChild(li);
        });
      }
    } else {
      if (grafTiposChart) { try { grafTiposChart.destroy(); } catch (e) {} grafTiposChart = null; }
      setTxt("nota-tipos", "Sin registros de tipos con los filtros actuales.");
      const ul = document.getElementById("lista-tipos-top");
      if (ul) ul.innerHTML = "<li>Sin datos</li>";
    }
  }

  document.addEventListener("DOMContentLoaded", iniciar);
})();
