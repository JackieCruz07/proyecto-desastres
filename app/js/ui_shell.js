/* =========================================================================
   ui_shell.js — Capa de integración de la interfaz (Actividad 6)
   -------------------------------------------------------------------------
   Une el mapa 3D, la capa temática, los filtros, los controles y el panel
   por país en una sola experiencia. Aporta:

   • Estado de interfaz sincronizado mediante los eventos que emite app.js
     (`atlas:filtros`, `atlas:seleccion`, `atlas:modal`, `atlas:proyeccion`,
     `atlas:pestana`, `atlas:mexico`, `atlas:listo`).
   • Chips de filtros activos y barra de sincronización.
   • Buscador de países con navegación por teclado.
   • Enlaces profundos en la dirección (#pais=MEX&pestana=filtros…).
   • Persistencia ligera de la pestaña y la proyección en localStorage.
   • Atajos de teclado, ayuda y anuncios para lectores de pantalla.
   • Panel colapsable en pantallas pequeñas.

   No rediseña la interfaz: solo la coordina.
   ========================================================================= */

(() => {
  "use strict";

  const CLAVE_ESTADO = "atlas.ui.v1";
  const MAX_RESULTADOS = 8;

  const $ = (id) => document.getElementById(id);

  const ui = {
    panel: $("panel"),
    tabs: Array.from(document.querySelectorAll(".pestana[data-pestana]")),
    buscador: $("buscador-pais"),
    resultados: $("buscador-resultados"),
    chips: $("filtros-activos"),
    sincronizacion: $("sincronizacion-texto"),
    anuncio: $("anuncio-lector"),
    btnAyuda: $("btn-ayuda"),
    modalAyuda: $("modal-ayuda"),
    ayudaCerrar: $("ayuda-cerrar"),
    btnPanelMovil: $("btn-panel-movil"),
    btnMexico: $("btn-abrir-mexico"),
    vistaMexico: $("vista-mexico"),
    mexicoCerrar: $("mexico-cerrar"),
    modalPais: $("modal-pais"),
  };

  const estado = {
    listo: false,
    seleccion: null,
    paisPanel: null,
    proyeccion: "globo",
    pestana: "resumen",
    filtros: null,
    mexico: false,
    resultados: [],
    indice: -1,
  };

  let focoAnterior = null;
  let temporizadorAnuncio = null;
  let aplicandoHash = false;

  /* ---------------------------------------------------------------------- *
   * 1. Utilidades                                                          *
   * ---------------------------------------------------------------------- */

  /** Quita acentos y unifica mayúsculas para buscar sin exigir tildes. */
  function normalizar(texto) {
    return String(texto || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .trim();
  }

  function traducirTipo(tipo) {
    if (!tipo || tipo === "todos") return "todos los tipos";
    return typeof window.traducirTipoDesastre === "function"
      ? window.traducirTipoDesastre(tipo)
      : tipo;
  }

  function formatearNumero(valor) {
    return Number(valor).toLocaleString("es-MX");
  }

  /** Anuncia un mensaje a lectores de pantalla sin recargar la región viva. */
  function anunciar(texto) {
    if (!ui.anuncio || !texto) return;
    ui.anuncio.textContent = "";
    window.setTimeout(() => {
      ui.anuncio.textContent = texto;
    }, 40);
  }

  /** Evita que un control deslizante sature de anuncios al moverse. */
  function anunciarDiferido(texto, espera = 650) {
    window.clearTimeout(temporizadorAnuncio);
    temporizadorAnuncio = window.setTimeout(() => anunciar(texto), espera);
  }

  /* ---------------------------------------------------------------------- *
   * 2. Persistencia y enlaces profundos                                    *
   * ---------------------------------------------------------------------- */

  function guardarEstado() {
    try {
      window.localStorage.setItem(
        CLAVE_ESTADO,
        JSON.stringify({
          pestana: estado.pestana,
          proyeccion: estado.proyeccion,
        })
      );
    } catch (error) {
      /* El modo privado puede bloquear localStorage: no es un fallo grave. */
    }
  }

  function leerEstadoGuardado() {
    try {
      const crudo = window.localStorage.getItem(CLAVE_ESTADO);
      return crudo ? JSON.parse(crudo) : {};
    } catch (error) {
      return {};
    }
  }

  function leerHash() {
    const crudo = window.location.hash.replace(/^#\/?/, "");
    const parametros = new URLSearchParams(crudo);
    return {
      pais: parametros.get("pais"),
      pestana: parametros.get("pestana"),
      proyeccion: parametros.get("proyeccion"),
      mexico: parametros.get("mexico"),
    };
  }

  function escribirHash() {
    if (!estado.listo || aplicandoHash) return;

    const parametros = new URLSearchParams();
    if (estado.pestana && estado.pestana !== "resumen") {
      parametros.set("pestana", estado.pestana);
    }
    if (estado.proyeccion === "plano") {
      parametros.set("proyeccion", "plano");
    }
    if (estado.seleccion) {
      parametros.set("pais", estado.seleccion);
    }
    if (estado.mexico) {
      parametros.set("mexico", "1");
    }

    const nuevo = parametros.toString() ? `#${parametros.toString()}` : "#";
    if (window.location.hash === nuevo) return;

    try {
      window.history.replaceState(
        null,
        "",
        `${window.location.pathname}${window.location.search}${nuevo}`
      );
    } catch (error) {
      /* replaceState puede fallar en algunos contextos embebidos. */
    }
  }

  function aplicarHash() {
    if (!estado.listo) return;
    const parametros = leerHash();

    aplicandoHash = true;
    try {
      if (parametros.pais && parametros.pais !== estado.seleccion) {
        seleccionar(parametros.pais, { volar: true });
      } else if (!parametros.pais && estado.seleccion) {
        if (window.AtlasApp && typeof window.AtlasApp.seleccionar === "function") {
          window.AtlasApp.seleccionar(null);
        }
      }
      if (parametros.pestana && parametros.pestana !== estado.pestana) {
        irAPestana(parametros.pestana, false);
      }
      if (parametros.proyeccion && parametros.proyeccion !== estado.proyeccion) {
        irAProyeccion(parametros.proyeccion, false);
      }
      if (parametros.mexico === "1" && !estado.mexico) {
        abrirMexico(false);
      } else if (parametros.mexico !== "1" && estado.mexico) {
        cerrarMexico(false);
      }
    } finally {
      aplicandoHash = false;
    }
  }

  /* ---------------------------------------------------------------------- *
   * 3. Sincronización de filtros                                           *
   * ---------------------------------------------------------------------- */

  function llamarAplicarFiltros() {
    if (window.AtlasApp && typeof window.AtlasApp.aplicarFiltros === "function") {
      window.AtlasApp.aplicarFiltros();
    }
  }

  function actualizarSincronizacion() {
    if (!ui.sincronizacion) return;
    const filtro = estado.filtros;

    if (!filtro) {
      ui.sincronizacion.textContent = "Vista mundial · cargando filtros…";
      return;
    }

    const partes = ["Vista mundial", `${filtro.desde}–${filtro.hasta}`, traducirTipo(filtro.tipo)];

    if (typeof filtro.eventos === "number") {
      partes.push(`${formatearNumero(filtro.eventos)} eventos`);
    }
    if (!filtro.activo) {
      partes.push("filtros no aplicados");
    }

    ui.sincronizacion.textContent = partes.join(" · ");
  }

  function crearChip(texto, etiqueta, accion, clase) {
    const envoltura = document.createElement("span");
    envoltura.setAttribute("role", "listitem");

    const boton = document.createElement("button");
    boton.type = "button";
    boton.className = `chip chip--filtro${clase ? ` ${clase}` : ""}`;
    boton.setAttribute("aria-label", etiqueta);

    const etiquetaTexto = document.createElement("span");
    etiquetaTexto.textContent = texto;
    const quitar = document.createElement("span");
    quitar.className = "chip__quitar";
    quitar.setAttribute("aria-hidden", "true");
    quitar.textContent = "×";

    boton.append(etiquetaTexto, quitar);
    boton.addEventListener("click", accion);
    envoltura.appendChild(boton);
    return envoltura;
  }

  function pintarChips() {
    if (!ui.chips) return;
    ui.chips.innerHTML = "";

    const filtro = estado.filtros;
    if (!filtro) return;

    const inicio = filtro.periodo ? filtro.periodo.inicio : filtro.desde;
    const fin = filtro.periodo ? filtro.periodo.fin : filtro.hasta;

    if (filtro.desde !== inicio || filtro.hasta !== fin) {
      ui.chips.appendChild(
        crearChip(
          `${filtro.desde}–${filtro.hasta}`,
          `Quitar el filtro de periodo y volver a ${inicio}–${fin}`,
          () => {
            const minimo = $("filtro-anio-min");
            const maximo = $("filtro-anio-max");
            if (minimo) minimo.value = inicio;
            if (maximo) maximo.value = fin;
            llamarAplicarFiltros();
            anunciar("Periodo restablecido al rango completo.");
          },
          "chip--periodo"
        )
      );
    }

    if (filtro.tipo && filtro.tipo !== "todos") {
      ui.chips.appendChild(
        crearChip(
          traducirTipo(filtro.tipo),
          `Quitar el filtro de tipo ${traducirTipo(filtro.tipo)}`,
          () => {
            const selector = $("selector-tipo");
            if (selector) selector.value = "todos";
            llamarAplicarFiltros();
            anunciar("Filtro de tipo restablecido: todos los tipos.");
          },
          "chip--tipo"
        )
      );
    }

    if (!filtro.activo) {
      ui.chips.appendChild(
        crearChip(
          "Filtros desactivados",
          "Volver a aplicar los filtros al mapa",
          () => {
            const casilla = $("chk-aplicar-filtros");
            if (casilla) casilla.checked = true;
            llamarAplicarFiltros();
            anunciar("Filtros aplicados de nuevo al mapa.");
          },
          "chip--aviso"
        )
      );
    }

    if (!ui.chips.children.length) {
      const completo = document.createElement("span");
      completo.className = "chip chip--completo";
      completo.setAttribute("role", "listitem");
      completo.textContent = "Periodo completo · todos los tipos";
      ui.chips.appendChild(completo);
    }
  }

  /* ---------------------------------------------------------------------- *
   * 4. Navegación entre pestañas, proyecciones y México                    *
   * ---------------------------------------------------------------------- */

  function irAPestana(nombre, avisar = true) {
    if (!nombre) return;
    if (window.AtlasApp && typeof window.AtlasApp.activarPestana === "function") {
      window.AtlasApp.activarPestana(nombre);
    } else {
      const boton = document.querySelector(`.pestana[data-pestana="${nombre}"]`);
      if (boton) boton.click();
    }
    if (avisar) anunciar(`Pestaña ${nombre} activada.`);
  }

  function irAProyeccion(tipo, avisar = true) {
    if (!tipo) return;
    if (window.AtlasApp && typeof window.AtlasApp.cambiarProyeccion === "function") {
      window.AtlasApp.cambiarProyeccion(tipo);
    } else {
      const boton = $(tipo === "plano" ? "btn-plano" : "btn-globo");
      if (boton) boton.click();
    }
    if (avisar) {
      anunciar(tipo === "plano" ? "Vista plana activada." : "Vista de globo 3D activada.");
    }
  }

  function abrirMexico(avisar = true) {
    if (ui.btnMexico) {
      ui.btnMexico.click();
    } else if (ui.vistaMexico) {
      ui.vistaMexico.hidden = false;
      document.body.classList.add("mexico-abierto");
    }
    if (avisar) anunciar("Mapa de México por estados abierto.");
  }

  function cerrarMexico(avisar = true) {
    if (ui.mexicoCerrar) {
      ui.mexicoCerrar.click();
    } else if (ui.vistaMexico) {
      ui.vistaMexico.hidden = true;
      document.body.classList.remove("mexico-abierto");
    }
    if (avisar) anunciar("Mapa de México cerrado. Volviste al atlas mundial.");
  }

  /* ---------------------------------------------------------------------- *
   * 5. Buscador de países                                                  *
   * ---------------------------------------------------------------------- */

  function territorios() {
    const capa = window.CapaTematica;
    return (capa && capa.estado && capa.estado.territorios) || [];
  }

  function buscar(termino) {
    const consulta = normalizar(termino);
    if (!consulta) return [];

    return territorios()
      .filter((territorio) => {
        const nombre = normalizar(territorio.nombre);
        const codigo = normalizar(territorio.codigo);
        return nombre.includes(consulta) || codigo.includes(consulta);
      })
      .sort((a, b) => {
        const nombreA = normalizar(a.nombre);
        const nombreB = normalizar(b.nombre);
        const posicionA = nombreA.indexOf(consulta);
        const posicionB = nombreB.indexOf(consulta);
        if (posicionA !== posicionB) return posicionA - posicionB;
        return nombreA.localeCompare(nombreB, "es");
      })
      .slice(0, MAX_RESULTADOS);
  }

  function cerrarResultados() {
    if (ui.resultados) {
      ui.resultados.hidden = true;
      ui.resultados.innerHTML = "";
    }
    if (ui.buscador) {
      ui.buscador.setAttribute("aria-expanded", "false");
      ui.buscador.removeAttribute("aria-activedescendant");
    }
    estado.resultados = [];
    estado.indice = -1;
  }

  function resaltarResultado(indice) {
    if (!ui.resultados) return;
    const opciones = Array.from(ui.resultados.querySelectorAll(".buscador__opcion"));
    if (!opciones.length) return;

    const total = opciones.length;
    const siguiente = ((indice % total) + total) % total;
    estado.indice = siguiente;

    opciones.forEach((opcion, posicion) => {
      const activa = posicion === siguiente;
      opcion.classList.toggle("activo", activa);
      opcion.setAttribute("aria-selected", String(activa));
      if (activa) {
        if (ui.buscador) ui.buscador.setAttribute("aria-activedescendant", opcion.id);
        opcion.scrollIntoView({ block: "nearest" });
      }
    });
  }

  function elegirResultado(indice) {
    const territorio = estado.resultados[indice];
    if (!territorio) return;

    if (ui.buscador) ui.buscador.value = territorio.nombre;
    cerrarResultados();
    seleccionar(territorio.codigo);
    anunciar(`Territorio seleccionado: ${territorio.nombre}.`);
  }

  function pintarResultados(lista) {
    if (!ui.resultados || !ui.buscador) return;

    estado.resultados = lista;
    estado.indice = -1;
    ui.resultados.innerHTML = "";

    if (!lista.length) {
      const vacio = document.createElement("li");
      vacio.className = "buscador__vacio";
      vacio.textContent =
        "Sin coincidencias. Revisa la ortografía o prueba con el código ISO del país.";
      ui.resultados.appendChild(vacio);
      ui.resultados.hidden = false;
      ui.buscador.setAttribute("aria-expanded", "true");
      return;
    }

    lista.forEach((territorio) => {
      const opcion = document.createElement("li");
      opcion.id = `resultado-${territorio.codigo}`;
      opcion.className = "buscador__opcion";
      opcion.setAttribute("role", "option");
      opcion.setAttribute("aria-selected", "false");
      opcion.dataset.codigo = territorio.codigo;

      const nombre = document.createElement("span");
      nombre.className = "buscador__nombre";
      nombre.textContent = territorio.nombre;

      const meta = document.createElement("span");
      meta.className = "buscador__meta";
      meta.textContent = `${territorio.codigo}${territorio.continente ? ` · ${territorio.continente}` : ""}`;

      opcion.append(nombre, meta);
      opcion.addEventListener("mousedown", (evento) => {
        evento.preventDefault();
        const posicion = estado.resultados.indexOf(territorio);
        elegirResultado(posicion);
      });
      ui.resultados.appendChild(opcion);
    });

    ui.resultados.hidden = false;
    ui.buscador.setAttribute("aria-expanded", "true");
  }

  function buscarYpintar() {
    if (!ui.buscador) return;
    const termino = ui.buscador.value;
    if (!termino.trim()) {
      cerrarResultados();
      return;
    }
    pintarResultados(buscar(termino));
  }

  /* ---------------------------------------------------------------------- *
   * 6. Selección de territorio y vuelo del mapa                            *
   * ---------------------------------------------------------------------- */

  function seleccionar(codigo, opciones = {}) {
    if (!codigo || !window.AtlasApp) return;

    window.AtlasApp.seleccionar(codigo);

    if (opciones.volar !== false) volarA(codigo);
    cerrarPanelMovil();
  }

  function featureDe(codigo) {
    const capa = window.CapaTematica;
    const geojson = capa && capa.estado && capa.estado.geojson;
    if (!geojson || !Array.isArray(geojson.features)) return null;

    return (
      geojson.features.find(
        (feature) => feature.properties && feature.properties.codigo === codigo
      ) || null
    );
  }

  function acumularCoordenadas(coordenadas, caja) {
    if (!Array.isArray(coordenadas)) return;

    if (typeof coordenadas[0] === "number" && typeof coordenadas[1] === "number") {
      caja[0] = Math.min(caja[0], coordenadas[0]);
      caja[1] = Math.min(caja[1], coordenadas[1]);
      caja[2] = Math.max(caja[2], coordenadas[0]);
      caja[3] = Math.max(caja[3], coordenadas[1]);
      return;
    }

    coordenadas.forEach((hijo) => acumularCoordenadas(hijo, caja));
  }

  function volarA(codigo) {
    const mapa = typeof window.__mapa === "function" ? window.__mapa() : null;
    const feature = featureDe(codigo);
    if (!mapa || !feature || !feature.geometry) return;

    const caja = [Infinity, Infinity, -Infinity, -Infinity];
    acumularCoordenadas(feature.geometry.coordinates, caja);
    if (!Number.isFinite(caja[0])) return;

    try {
      mapa.fitBounds(
        [
          [caja[0], caja[1]],
          [caja[2], caja[3]],
        ],
        { padding: 90, maxZoom: 5, duration: 950 }
      );
    } catch (error) {
      /* Algunas geometrías mínimas no admiten fitBounds; se ignora. */
    }
  }

  /* ---------------------------------------------------------------------- *
   * 7. Panel móvil                                                         *
   * ---------------------------------------------------------------------- */

  function abrirPanelMovil() {
    document.body.classList.add("panel-abierto");
    if (ui.btnPanelMovil) {
      ui.btnPanelMovil.setAttribute("aria-expanded", "true");
      ui.btnPanelMovil.setAttribute("aria-label", "Ocultar panel de controles");
    }
    const activa = ui.panel && ui.panel.querySelector(".pestana.activo");
    if (activa) activa.focus({ preventScroll: true });
  }

  function cerrarPanelMovil() {
    if (!document.body.classList.contains("panel-abierto")) return;
    document.body.classList.remove("panel-abierto");
    if (ui.btnPanelMovil) {
      ui.btnPanelMovil.setAttribute("aria-expanded", "false");
      ui.btnPanelMovil.setAttribute("aria-label", "Mostrar panel de controles");
    }
  }

  function alternarPanelMovil() {
    if (document.body.classList.contains("panel-abierto")) {
      cerrarPanelMovil();
    } else {
      abrirPanelMovil();
    }
  }

  /* ---------------------------------------------------------------------- *
   * 8. Ayuda y atajos                                                      *
   * ---------------------------------------------------------------------- */

  function abrirAyuda() {
    if (!ui.modalAyuda) return;
    focoAnterior = document.activeElement;
    if (typeof ui.modalAyuda.showModal === "function") {
      if (!ui.modalAyuda.open) ui.modalAyuda.showModal();
    } else {
      ui.modalAyuda.setAttribute("open", "");
    }
    if (ui.ayudaCerrar) ui.ayudaCerrar.focus({ preventScroll: true });
    anunciar("Guía rápida abierta.");
  }

  function cerrarAyuda() {
    if (!ui.modalAyuda) return;
    if (typeof ui.modalAyuda.close === "function" && ui.modalAyuda.open) {
      ui.modalAyuda.close();
    } else {
      ui.modalAyuda.removeAttribute("open");
    }
  }

  function hayDialogoAbierto() {
    return Boolean(document.querySelector("dialog[open]"));
  }

  function conectarTeclado() {
    document.addEventListener("keydown", (evento) => {
      const objetivo = evento.target;
      const escribiendo =
        objetivo &&
        (objetivo.tagName === "INPUT" ||
          objetivo.tagName === "SELECT" ||
          objetivo.tagName === "TEXTAREA" ||
          objetivo.isContentEditable);

      if (evento.key === "Escape") {
        if (ui.resultados && !ui.resultados.hidden) {
          cerrarResultados();
          return;
        }
        if (hayDialogoAbierto()) return;
        if (document.body.classList.contains("panel-abierto")) {
          cerrarPanelMovil();
          if (ui.btnPanelMovil) ui.btnPanelMovil.focus({ preventScroll: true });
        }
        return;
      }

      if (escribiendo || evento.ctrlKey || evento.metaKey || evento.altKey) return;
      if (hayDialogoAbierto()) return;

      if (evento.key === "/") {
        evento.preventDefault();
        irAPestana("resumen", false);
        if (window.innerWidth <= 900) abrirPanelMovil();
        window.requestAnimationFrame(() => {
          if (ui.buscador) ui.buscador.focus();
        });
        return;
      }

      if (evento.key === "?") {
        evento.preventDefault();
        abrirAyuda();
        return;
      }

      if (["1", "2", "3", "4", "5"].includes(evento.key)) {
        const nombres = ["resumen", "filtros", "capa", "mexico", "prediccion"];
        evento.preventDefault();
        irAPestana(nombres[Number(evento.key) - 1]);
        return;
      }

      const tecla = evento.key.toLowerCase();
      if (tecla === "g") {
        evento.preventDefault();
        irAProyeccion("globo");
      } else if (tecla === "p") {
        evento.preventDefault();
        irAProyeccion("plano");
      } else if (tecla === "m") {
        evento.preventDefault();
        abrirMexico();
      }
    });
  }

  /* ---------------------------------------------------------------------- *
   * 9. Conexión de eventos de la aplicación                                *
   * ---------------------------------------------------------------------- */

  function conectarEventosAtlas() {
    document.addEventListener("atlas:filtros", (evento) => {
      estado.filtros = evento.detail || null;
      pintarChips();
      actualizarSincronizacion();

      const filtro = evento.detail || {};
      if (!estado.listo) return;

      const resumen = `${filtro.desde} a ${filtro.hasta}, ${traducirTipo(filtro.tipo)}${
        typeof filtro.eventos === "number"
          ? `, ${formatearNumero(filtro.eventos)} eventos`
          : ""
      }${filtro.activo === false ? ", filtros no aplicados" : ""}`;
      anunciarDiferido(`Mapa actualizado: ${resumen}.`);
    });

    document.addEventListener("atlas:seleccion", (evento) => {
      const detalle = evento.detail || {};
      estado.seleccion = detalle.codigo || null;

      if (detalle.codigo) {
        cerrarPanelMovil();
        if (estado.listo && !hayDialogoAbierto()) {
          irAPestana("resumen", false);
        }
        anunciar(
          `Territorio seleccionado: ${detalle.nombre || detalle.codigo}. Ficha actualizada.`
        );
      } else if (estado.listo && estado.seleccion === null) {
        anunciar("Selección borrada. Se muestra el resumen general.");
      }

      escribirHash();
    });

    document.addEventListener("atlas:modal", (evento) => {
      const detalle = evento.detail || {};
      estado.paisPanel = detalle.abierto ? detalle.codigo : null;

      if (detalle.abierto) {
        anunciar(`Panel detallado abierto${detalle.codigo ? ` para ${detalle.codigo}` : ""}.`);
      } else {
        anunciar("Panel detallado cerrado.");
      }
    });

    document.addEventListener("atlas:proyeccion", (evento) => {
      const detalle = evento.detail || {};
      estado.proyeccion = detalle.proyeccion === "plano" ? "plano" : "globo";
      guardarEstado();
      escribirHash();
    });

    document.addEventListener("atlas:pestana", (evento) => {
      const detalle = evento.detail || {};
      estado.pestana = detalle.pestana || "resumen";
      guardarEstado();
      escribirHash();
    });

    document.addEventListener("atlas:mexico", (evento) => {
      estado.mexico = Boolean(evento.detail && evento.detail.abierto);
      escribirHash();
    });

    document.addEventListener("atlas:listo", (evento) => {
      estado.listo = true;

      const parametros = leerHash();
      const guardado = leerEstadoGuardado();

      if (parametros.pais) seleccionar(parametros.pais, { volar: true });

      if (parametros.pestana) {
        irAPestana(parametros.pestana, false);
      } else if (!parametros.pais && guardado.pestana) {
        irAPestana(guardado.pestana, false);
      }

      if (parametros.proyeccion) {
        irAProyeccion(parametros.proyeccion, false);
      } else if (guardado.proyeccion === "plano") {
        irAProyeccion("plano", false);
      }

      if (parametros.mexico === "1") abrirMexico(false);

      escribirHash();

      const detalle = evento.detail || {};
      const partes = ["Atlas listo"];
      if (detalle.eventos) partes.push(`${formatearNumero(detalle.eventos)} eventos`);
      if (detalle.territorios) partes.push(`${detalle.territorios} territorios`);
      anunciar(`${partes.join(". ")}.`);
    });
  }

  /* ---------------------------------------------------------------------- *
   * 10. Arranque                                                           *
   * ---------------------------------------------------------------------- */

  function iniciar() {
    conectarEventosAtlas();
    conectarTeclado();

    if (ui.btnAyuda) ui.btnAyuda.addEventListener("click", abrirAyuda);
    if (ui.ayudaCerrar) ui.ayudaCerrar.addEventListener("click", cerrarAyuda);
    if (ui.modalAyuda) {
      ui.modalAyuda.addEventListener("click", (evento) => {
        if (evento.target === ui.modalAyuda) cerrarAyuda();
      });
      ui.modalAyuda.addEventListener("close", () => {
        if (focoAnterior && typeof focoAnterior.focus === "function") {
          focoAnterior.focus({ preventScroll: true });
        }
      });
    }

    if (ui.btnPanelMovil) {
      ui.btnPanelMovil.addEventListener("click", alternarPanelMovil);
    }
    const btnCerrarPanel = $("btn-cerrar-panel-movil");
    if (btnCerrarPanel) {
      btnCerrarPanel.addEventListener("click", () => {
        cerrarPanelMovil();
        if (ui.btnPanelMovil) ui.btnPanelMovil.focus({ preventScroll: true });
      });
    }

    if (ui.buscador) {
      ui.buscador.addEventListener("input", buscarYpintar);
      ui.buscador.addEventListener("focus", () => {
        if (ui.buscador.value.trim()) buscarYpintar();
      });
      ui.buscador.addEventListener("keydown", (evento) => {
        if (evento.key === "ArrowDown") {
          evento.preventDefault();
          if (!estado.resultados.length) buscarYpintar();
          if (estado.resultados.length) resaltarResultado(estado.indice + 1);
        } else if (evento.key === "ArrowUp") {
          evento.preventDefault();
          if (estado.resultados.length) resaltarResultado(estado.indice - 1);
        } else if (evento.key === "Enter") {
          if (estado.resultados.length) {
            evento.preventDefault();
            elegirResultado(estado.indice >= 0 ? estado.indice : 0);
          }
        } else if (evento.key === "Escape") {
          cerrarResultados();
        } else if (evento.key === "Tab") {
          cerrarResultados();
        }
      });
      ui.buscador.addEventListener("blur", () => {
        window.setTimeout(cerrarResultados, 120);
      });
    }

    window.addEventListener("hashchange", aplicarHash);

    window.addEventListener("resize", () => {
      if (window.innerWidth > 900) cerrarPanelMovil();
    });

    window.addEventListener("beforeunload", guardarEstado);

    try {
      const reducido = window.matchMedia("(prefers-reduced-motion: reduce)");
      document.documentElement.classList.toggle("movimiento-reducido", reducido.matches);
      if (typeof reducido.addEventListener === "function") {
        reducido.addEventListener("change", (evento) => {
          document.documentElement.classList.toggle(
            "movimiento-reducido",
            evento.matches
          );
        });
      }
    } catch (error) {
      /* matchMedia no está disponible en navegadores muy antiguos. */
    }

    pintarChips();
    actualizarSincronizacion();
  }

  window.AtlasUI = {
    estado,
    irAPestana,
    irAProyeccion,
    seleccionar,
    buscar,
    abrirMexico,
    cerrarMexico,
    abrirAyuda,
    version: "6.0",
  };

  iniciar();
})();
