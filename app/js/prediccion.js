/* =========================================================================
   prediccion.js — Predicción de impacto con red neuronal y XGBoost
   -------------------------------------------------------------------------
   La inferencia ocurre en el navegador. No hay API ni peticiones externas:
   el archivo modelos/modelo_prediccion.json contiene el vocabulario, los
   pesos de la red, los árboles de XGBoost y el catálogo de países.
   ========================================================================= */

(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const NUMERO = new Intl.NumberFormat("es-MX", { maximumFractionDigits: 0 });
  const MONEDA = new Intl.NumberFormat("es-MX", {
    style: "currency",
    currency: "MXN",
    maximumFractionDigits: 0,
  });
  const MONEDA_COMPACTA = new Intl.NumberFormat("es-MX", {
    style: "currency",
    currency: "MXN",
    notation: "compact",
    compactDisplay: "long",
    maximumFractionDigits: 1,
  });

  const estado = {
    paquete: null,
    cargando: null,
    listo: false,
    indices: null,
    paises: new Map(),
    mediana: null,
    ultimo: null,
  };

  function escapar(texto) {
    return String(texto)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function sigmoide(valor) {
    return 1 / (1 + Math.exp(-Math.max(-30, Math.min(30, valor))));
  }

  function expm1(valor) {
    return Math.expm1(valor);
  }

  function limitar(valor, minimo, maximo) {
    return Math.max(minimo, Math.min(maximo, valor));
  }

  function mediana(valores) {
    const limpios = valores.filter((v) => Number.isFinite(v)).sort((a, b) => a - b);
    if (!limpios.length) return 0;
    const medio = Math.floor(limpios.length / 2);
    return limpios.length % 2
      ? limpios[medio]
      : (limpios[medio - 1] + limpios[medio]) / 2;
  }

  function formatoNumero(valor) {
    return NUMERO.format(Math.max(0, Math.round(valor)));
  }

  function formatoMoneda(valor) {
    if (!Number.isFinite(valor) || valor < 0) return "No disponible";
    return valor >= 1_000_000 ? MONEDA_COMPACTA.format(valor) : MONEDA.format(valor);
  }

  /* ------------------------------------------------------------------ *
   * 1. Carga del paquete de modelos                                     *
   * ------------------------------------------------------------------ */
  async function cargarModelo() {
    if (estado.listo) return estado.paquete;
    if (estado.cargando) return estado.cargando;

    const ruta =
      (window.CONFIG && window.CONFIG.rutaModeloPrediccion) ||
      "modelos/modelo_prediccion.json";

    estado.cargando = fetch(ruta)
      .then((respuesta) => {
        if (!respuesta.ok) throw new Error(`HTTP ${respuesta.status}`);
        return respuesta.json();
      })
      .then((paquete) => {
        estado.paquete = paquete;
        prepararIndices(paquete);
        poblarControles(paquete);
        estado.listo = true;
        estado.cargando = null;
        mostrarEstadoListo(paquete);
        return paquete;
      })
      .catch((error) => {
        estado.cargando = null;
        console.error(error);
        const caja = $("prediccion-estado");
        if (caja) {
          caja.className = "prediccion-estado prediccion-estado--error";
          caja.textContent =
            "No se pudieron cargar los modelos. Verifica que exista app/modelos/modelo_prediccion.json.";
        }
        throw error;
      });

    return estado.cargando;
  }

  function prepararIndices(paquete) {
    const esquema = paquete.esquema;
    const columnas = esquema.columnas_xgb;
    const posiciones = new Map(columnas.map((columna, i) => [columna, i]));

    const posNum = {};
    esquema.num_cols_modelo.forEach((columna) => {
      posNum[columna] = posiciones.get(`num__${columna}`);
    });

    const posCat = {};
    esquema.cat_cols.forEach((columna) => {
      posCat[columna] = esquema.cat_vocab[columna].map((categoria) =>
        posiciones.get(`cat__${columna}__${categoria}`)
      );
    });

    estado.indices = { columnas, posNum, posCat };
    estado.paises = new Map(
      paquete.catalogo.paises.map((pais) => [pais.iso, pais])
    );
    estado.mediana = {
      pib: mediana(paquete.catalogo.paises.map((p) => p.pib_pc_mxn)),
      poblacion: mediana(paquete.catalogo.paises.map((p) => p.poblacion)),
      densidad: mediana(paquete.catalogo.paises.map((p) => p.densidad)),
    };
  }

  function mostrarEstadoListo(paquete) {
    const caja = $("prediccion-estado");
    if (!caja) return;
    const metricas = paquete.metricas.clasificacion;
    const aucRed = metricas.red_neuronal.roc_auc.toFixed(2);
    const aucXgb = metricas.xgboost.roc_auc.toFixed(2);
    caja.className = "prediccion-estado prediccion-estado--listo";
    caja.textContent = `Modelos listos · ${formatoNumero(
      paquete.particiones.n_entrenamiento
    )} eventos de entrenamiento · ROC-AUC ${aucRed} (red) y ${aucXgb} (XGBoost)`;
  }

  /* ------------------------------------------------------------------ *
   * 2. Controles                                                        *
   * ------------------------------------------------------------------ */
  function agregarOpcion(select, valor, texto) {
    const opcion = document.createElement("option");
    opcion.value = valor;
    opcion.textContent = texto;
    select.appendChild(opcion);
  }

  function poblarControles(paquete) {
    const paises = paquete.catalogo.paises;
    const selectPais = $("pred-pais");
    if (selectPais) {
      selectPais.innerHTML = "";
      paises.forEach((pais) => agregarOpcion(selectPais, pais.iso, pais.nombre));
      selectPais.value = estado.paises.has("MEX") ? "MEX" : paises[0]?.iso || "";
    }

    const selectTipo = $("pred-tipo");
    if (selectTipo) {
      selectTipo.innerHTML = "";
      paquete.catalogo.tipos.forEach((tipo) =>
        agregarOpcion(selectTipo, tipo.valor, tipo.valor)
      );
      selectTipo.value = paquete.catalogo.tipos[0]?.valor || "";
    }

    const selectMes = $("pred-mes");
    if (selectMes) {
      selectMes.innerHTML = "";
      paquete.catalogo.meses.forEach((mes, i) => agregarOpcion(selectMes, i + 1, mes));
      selectMes.value = String(new Date().getMonth() + 1);
    }

    const selectEscala = $("pred-escala");
    if (selectEscala) {
      selectEscala.innerHTML = "";
      paquete.catalogo.escalas.forEach((escala) =>
        agregarOpcion(selectEscala, escala.valor, escala.etiqueta)
      );
      selectEscala.value = "Sin dato";
    }

    poblarSubtipos();
    actualizarEscalaPorTipo();
    actualizarContextoPais();
  }

  function poblarSubtipos() {
    if (!estado.paquete) return;
    const tipo = $("pred-tipo")?.value || "";
    const select = $("pred-subtipo");
    if (!select) return;
    const anterior = select.value;
    select.innerHTML = "";
    agregarOpcion(select, "", "Sin especificar");
    const lista = estado.paquete.catalogo.subtipos_por_tipo[tipo] || [];
    lista.forEach((subtipo) => agregarOpcion(select, subtipo.valor, subtipo.valor));
    if ([...select.options].some((opcion) => opcion.value === anterior)) {
      select.value = anterior;
    } else {
      select.value = "";
    }
  }

  function actualizarEscalaPorTipo() {
    const tipo = $("pred-tipo")?.value;
    const escala = $("pred-escala");
    if (!tipo || !escala) return;
    const preferida = {
      Earthquake: "Moment Magnitude",
      Storm: "Kph",
      "Extreme temperature": "°C",
      Flood: "Km2",
      Epidemic: "Vaccinated",
    }[tipo];
    if (preferida && [...escala.options].some((opcion) => opcion.value === preferida)) {
      escala.value = preferida;
    }
    actualizarPasoMagnitud();
  }

  function actualizarPasoMagnitud() {
    const escala = $("pred-escala")?.value || "Sin dato";
    const entrada = $("pred-magnitud");
    if (!entrada) return;
    const pasos = {
      "Moment Magnitude": { paso: "0.1", ejemplo: "Ej. 6.8" },
      Kph: { paso: "1", ejemplo: "Ej. 150" },
      "°C": { paso: "0.1", ejemplo: "Ej. 35" },
      Km2: { paso: "1", ejemplo: "Ej. 500" },
      Vaccinated: { paso: "1", ejemplo: "Ej. 1000000" },
    };
    const configuracion = pasos[escala] || { paso: "any", ejemplo: "Déjalo vacío si no la conoces" };
    entrada.step = configuracion.paso;
    entrada.placeholder = configuracion.ejemplo;
  }

  function actualizarContextoPais() {
    const pais = estado.paises.get($("pred-pais")?.value);
    const caja = $("pred-contexto");
    if (!caja || !pais) return;
    const partes = [
      pais.region || "Sin región",
      `PIB per cápita ${formatoMoneda(pais.pib_pc_mxn)}`,
      `Población ${formatoNumero(pais.poblacion)}`,
    ];
    if (pais.pib_faltante) partes.push("PIB estimado con la mediana regional");
    if (!pais.eventos) partes.push("sin eventos históricos: estimación menos confiable");
    caja.textContent = partes.join(" · ");
  }

  /* ------------------------------------------------------------------ *
   * 3. Construcción del escenario y transformación                      *
   * ------------------------------------------------------------------ */
  function construirEscenario(pais, tipo, subtipo, mes, magnitud, escala, duracion) {
    const esquema = estado.paquete.esquema;
    const catalogo = estado.paquete.catalogo;
    const paisBase = pais || {
      iso: "",
      region: "Sin dato",
      subregion: "Sin dato",
      pib_pc_mxn: estado.mediana.pib,
      poblacion: estado.mediana.poblacion,
      densidad: estado.mediana.densidad,
      pib_faltante: 0,
    };

    const tipoFinal = tipo || "Sin dato";
    const subtipoFinal = subtipo || "Sin dato";
    const escalaFinal = magnitud == null ? "Sin dato" : escala || "Sin dato";
    const valoresCat = {
      tipo: tipoFinal,
      subtipo: subtipoFinal,
      subgrupo: catalogo.subgrupo_por_tipo[tipoFinal] || "Sin dato",
      region: paisBase.region || "Sin dato",
      subregion: paisBase.subregion || "Sin dato",
      iso: paisBase.iso || "Sin dato",
      escala: escalaFinal,
    };

    const pib = Number.isFinite(paisBase.pib_pc_mxn)
      ? paisBase.pib_pc_mxn
      : estado.mediana.pib;
    const poblacion = Number.isFinite(paisBase.poblacion)
      ? paisBase.poblacion
      : estado.mediana.poblacion;
    const densidad = Number.isFinite(paisBase.densidad)
      ? paisBase.densidad
      : estado.mediana.densidad;
    const mesValido = Number.isInteger(mes) && mes >= 1 && mes <= 12;
    const duracionValida = Number.isFinite(duracion) && duracion >= 0;
    const magnitudValida = Number.isFinite(magnitud);

    const crudas = {
      pib_pc_log: Math.log1p(Math.max(0, pib)),
      poblacion_log: Math.log1p(Math.max(0, poblacion)),
      densidad_log: Math.log1p(Math.max(0, densidad)),
      mes_sin: mesValido ? Math.sin((2 * Math.PI * (mes - 1)) / 12) : 0,
      mes_cos: mesValido ? Math.cos((2 * Math.PI * (mes - 1)) / 12) : 0,
      duracion_log: duracionValida ? Math.log1p(duracion) : 0,
      magnitud_faltante: magnitudValida ? 0 : 1,
      mes_faltante: mesValido ? 0 : 1,
      duracion_faltante: duracionValida ? 0 : 1,
      pib_faltante: paisBase.pib_faltante ? 1 : 0,
      magnitud_z: 0,
    };

    if (magnitudValida) {
      const estadisticas =
        esquema.mag_por_escala[escalaFinal] || esquema.mag_global;
      const std = estadisticas.std || 1;
      crudas.magnitud_z = limitar(
        (magnitud - estadisticas.media) / std,
        -6,
        6
      );
    }

    const codigos = [];
    esquema.cat_cols.forEach((columna) => {
      const vocab = esquema.cat_vocab[columna];
      let indice = vocab.indexOf(valoresCat[columna]);
      if (indice < 0) indice = 0;
      codigos.push(indice);
    });

    const numericas = [];
    esquema.num_cols_modelo.forEach((columna) => {
      let valor = crudas[columna];
      if (!Number.isFinite(valor)) {
        valor = esquema.num_median[columna] || 0;
      }
      const media = esquema.num_mean[columna] || 0;
      const std = esquema.num_std[columna] || 1;
      numericas.push((valor - media) / std);
    });

    const vector = new Array(esquema.columnas_xgb.length).fill(0);
    esquema.num_cols_modelo.forEach((columna, i) => {
      const posicion = estado.indices.posNum[columna];
      if (posicion !== undefined) vector[posicion] = numericas[i];
    });
    esquema.cat_cols.forEach((columna, i) => {
      const posicion = estado.indices.posCat[columna][codigos[i]];
      if (posicion !== undefined) vector[posicion] = 1;
    });

    return {
      pais: paisBase,
      tipo: tipoFinal,
      subtipo: subtipoFinal,
      mes: mesValido ? mes : null,
      magnitud: magnitudValida ? magnitud : null,
      escala: escalaFinal,
      duracion: duracionValida ? duracion : null,
      valoresCat,
      crudas,
      codigos,
      numericas,
      vector,
    };
  }

  /* ------------------------------------------------------------------ *
   * 4. Inferencia                                                      *
   * ------------------------------------------------------------------ */
  function salidaRed(pesos, codigos, numericas) {
    if (!pesos || !pesos.modelos || !pesos.modelos.length) return 0;
    let total = 0;

    pesos.modelos.forEach((modelo) => {
      let entrada = [];
      codigos.forEach((codigo, i) => {
        const tabla = modelo.embeddings[i];
        const fila = tabla[codigo] || tabla[0];
        entrada = entrada.concat(fila);
      });
      entrada = entrada.concat(numericas);

      modelo.capas.forEach((capa, indiceCapa) => {
        const salida = new Array(capa.sesgo.length).fill(0);
        for (let j = 0; j < capa.sesgo.length; j += 1) {
          let valor = capa.sesgo[j];
          const fila = capa.pesos[j];
          for (let k = 0; k < fila.length; k += 1) {
            valor += fila[k] * entrada[k];
          }
          salida[j] =
            indiceCapa < modelo.capas.length - 1 ? Math.max(0, valor) : valor;
        }
        entrada = salida;
      });
      total += entrada[0];
    });

    return total / pesos.modelos.length;
  }

  function margenArboles(exportado, vector) {
    let margen = exportado.base_margen;
    exportado.arboles.forEach((arbol) => {
      let nodo = 0;
      let seguridad = 0;
      while (seguridad < 10000) {
        seguridad += 1;
        const actual = arbol[nodo];
        if (!actual) break;
        if (actual.f === -1) {
          margen += actual.v;
          break;
        }
        const valor = vector[actual.f];
        if (valor === null || valor === undefined || Number.isNaN(valor)) {
          nodo = actual.n ? actual.i : actual.d;
        } else if (valor < actual.u) {
          nodo = actual.i;
        } else {
          nodo = actual.d;
        }
      }
    });
    return margen;
  }

  function predecirClasificacion(escenario) {
    const modelo = estado.paquete.clasificacion;
    const logitRed = salidaRed(
      modelo.red_neuronal.pesos,
      escenario.codigos,
      escenario.numericas
    );
    const probabilidadRed = sigmoide(
      logitRed / (modelo.red_neuronal.temperatura || 1)
    );
    const logitXgb = margenArboles(modelo.xgboost.arboles, escenario.vector);
    const probabilidadXgb = sigmoide(
      logitXgb / (modelo.xgboost.temperatura || 1)
    );
    return {
      red: probabilidadRed,
      xgb: probabilidadXgb,
      promedio: (probabilidadRed + probabilidadXgb) / 2,
    };
  }

  function predecirRegresion(bloque, escenario) {
    const logRed =
      salidaRed(
        bloque.red_neuronal.pesos,
        escenario.codigos,
        escenario.numericas
      ) *
        bloque.red_neuronal.estadisticas.std +
      bloque.red_neuronal.estadisticas.media;
    const logXgb = margenArboles(bloque.xgboost.arboles, escenario.vector);
    return {
      logRed,
      logXgb,
      logMedio: (logRed + logXgb) / 2,
      red: expm1(logRed),
      xgb: expm1(logXgb),
      mediana: expm1((logRed + logXgb) / 2),
    };
  }

  function nivelRiesgo(probabilidad) {
    if (probabilidad < 0.35) {
      return {
        clase: "bajo",
        etiqueta: "Riesgo bajo",
        explicacion:
          "La mayoría de los eventos con estas características no alcanzaron el umbral de alto impacto.",
      };
    }
    if (probabilidad < 0.55) {
      return {
        clase: "medio",
        etiqueta: "Riesgo medio",
        explicacion:
          "El escenario se parece a eventos que quedaron cerca del umbral de alto impacto.",
      };
    }
    return {
      clase: "alto",
      etiqueta: "Riesgo alto",
      explicacion:
        "El escenario se parece a eventos que superaron el umbral de fallecimientos o de personas afectadas.",
    };
  }

  /* ------------------------------------------------------------------ *
   * 5. Explicación por perturbación                                     *
   * ------------------------------------------------------------------ */
  function probabilidadEscenario(escenario) {
    return predecirClasificacion(escenario).promedio;
  }

  function explicarFactores(escenario, probabilidadOriginal) {
    const perfil = estado.paquete.perfil_promedio.categoricas;
    const paisPromedio = {
      iso: perfil.iso || "",
      region: perfil.region || "Sin dato",
      subregion: perfil.subregion || "Sin dato",
      pib_pc_mxn: estado.mediana.pib,
      poblacion: estado.mediana.poblacion,
      densidad: estado.mediana.densidad,
      pib_faltante: 1,
    };
    const paisEconomico = {
      ...escenario.pais,
      pib_pc_mxn: estado.mediana.pib,
      pib_faltante: 1,
    };

    const variantes = [
      {
        nombre: "Tipo de desastre",
        escenario: construirEscenario(
          escenario.pais,
          perfil.tipo,
          perfil.subtipo,
          escenario.mes,
          escenario.magnitud,
          escenario.escala,
          escenario.duracion
        ),
      },
      {
        nombre: "País y región",
        escenario: construirEscenario(
          paisPromedio,
          escenario.tipo,
          escenario.subtipo,
          escenario.mes,
          escenario.magnitud,
          escenario.escala,
          escenario.duracion
        ),
      },
      {
        nombre: "Nivel económico",
        escenario: construirEscenario(
          paisEconomico,
          escenario.tipo,
          escenario.subtipo,
          escenario.mes,
          escenario.magnitud,
          escenario.escala,
          escenario.duracion
        ),
      },
      {
        nombre: "Mes del año",
        escenario: construirEscenario(
          escenario.pais,
          escenario.tipo,
          escenario.subtipo,
          null,
          escenario.magnitud,
          escenario.escala,
          escenario.duracion
        ),
      },
      {
        nombre: "Magnitud",
        escenario: construirEscenario(
          escenario.pais,
          escenario.tipo,
          escenario.subtipo,
          escenario.mes,
          null,
          "Sin dato",
          escenario.duracion
        ),
      },
      {
        nombre: "Duración",
        escenario: construirEscenario(
          escenario.pais,
          escenario.tipo,
          escenario.subtipo,
          escenario.mes,
          escenario.magnitud,
          escenario.escala,
          1
        ),
      },
    ];

    return variantes
      .map((variante) => ({
        nombre: variante.nombre,
        delta: probabilidadOriginal - probabilidadEscenario(variante.escenario),
      }))
      .filter((factor) => Math.abs(factor.delta) >= 0.005)
      .sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta))
      .slice(0, 4);
  }

  /* ------------------------------------------------------------------ *
   * 6. Cálculo y presentación                                           *
   * ------------------------------------------------------------------ */
  async function calcular() {
    if (!estado.listo) {
      await cargarModelo();
    }
    const pais = estado.paises.get($("pred-pais")?.value);
    const tipo = $("pred-tipo")?.value || "";
    if (!pais || !tipo) return;

    const subtipo = $("pred-subtipo")?.value || "";
    const mes = Number($("pred-mes")?.value);
    const magnitudTexto = $("pred-magnitud")?.value;
    const magnitud =
      magnitudTexto === "" || magnitudTexto == null ? null : Number(magnitudTexto);
    const escala = $("pred-escala")?.value || "Sin dato";
    const duracionTexto = $("pred-duracion")?.value;
    const duracion =
      duracionTexto === "" || duracionTexto == null ? null : Number(duracionTexto);

    if (magnitud != null && !Number.isFinite(magnitud)) {
      anunciar("La magnitud debe ser un número.");
      return;
    }

    const escenario = construirEscenario(
      pais,
      tipo,
      subtipo,
      mes,
      magnitud,
      escala,
      duracion
    );
    const clasificacion = predecirClasificacion(escenario);
    const afectados = predecirRegresion(
      estado.paquete.regresion.afectados,
      escenario
    );
    const dano = predecirRegresion(estado.paquete.regresion.dano, escenario);

    const q10Afectados =
      estado.paquete.regresion.afectados.xgboost.q10_residual;
    const q90Afectados =
      estado.paquete.regresion.afectados.xgboost.q90_residual;
    const q10Dano = estado.paquete.regresion.dano.xgboost.q10_residual;
    const q90Dano = estado.paquete.regresion.dano.xgboost.q90_residual;

    const limiteAfectados = [
      expm1(afectados.logMedio + q10Afectados),
      expm1(afectados.logMedio + q90Afectados),
    ].sort((a, b) => a - b);
    const limiteDano = [
      expm1(dano.logMedio + q10Dano) * 1000,
      expm1(dano.logMedio + q90Dano) * 1000,
    ].sort((a, b) => a - b);

    const factores = explicarFactores(escenario, clasificacion.promedio);
    const nivel = nivelRiesgo(clasificacion.promedio);

    estado.ultimo = {
      pais,
      tipo,
      subtipo,
      mes,
      magnitud,
      escala,
      clasificacion,
      afectados,
      dano,
      nivel,
      factores,
    };

    renderResultado({
      pais,
      tipo,
      subtipo,
      mes,
      magnitud,
      clasificacion,
      afectados,
      dano,
      nivel,
      factores,
      limiteAfectados,
      limiteDano,
    });
  }

  function renderResultado(datos) {
    const caja = $("pred-resultados");
    if (!caja) return;
    const probabilidad = Math.round(datos.clasificacion.promedio * 100);
    const acuerdo = Math.abs(datos.clasificacion.red - datos.clasificacion.xgb);
    const nivelAcuerdo = acuerdo < 0.08 ? "Alto" : acuerdo < 0.18 ? "Medio" : "Bajo";
    const metrica = estado.paquete.metricas.clasificacion;

    const filasFactores = datos.factores.length
      ? datos.factores
          .map((factor) => {
            const puntos = Math.round(factor.delta * 100);
            const sube = puntos > 0;
            const etiqueta = puntos === 0 ? "0 pts" : `${sube ? "+" : ""}${puntos} pts`;
            return `<li>
              <span class="prediccion-factor__icono ${
                sube ? "prediccion-factor__icono--sube" : "prediccion-factor__icono--baja"
              }" aria-hidden="true">${sube ? "↑" : "↓"}</span>
              <span>${escapar(factor.nombre)}</span>
              <strong>${etiqueta}</strong>
            </li>`;
          })
          .join("")
      : `<li><span class="prediccion-factor__icono" aria-hidden="true">·</span><span>Sin factores dominantes</span><strong>0 pts</strong></li>`;

    caja.innerHTML = `
      <div class="prediccion-veredicto prediccion-veredicto--${datos.nivel.clase}">
        <div>
          <p class="prediccion-etiqueta">Probabilidad de alto impacto</p>
          <p class="prediccion-nivel">${datos.nivel.etiqueta}</p>
        </div>
        <strong class="prediccion-porcentaje">${probabilidad}%</strong>
      </div>
      <div class="prediccion-barra" aria-hidden="true"><span style="width:${probabilidad}%"></span></div>
      <p class="prediccion-explicacion">
        ${datos.nivel.explicacion} Aproximadamente ${probabilidad} de cada 100
        eventos con estas características serían de alto impacto.
      </p>

      <div class="prediccion-kpis">
        <article class="prediccion-kpi">
          <span>Personas afectadas</span>
          <strong>${formatoNumero(datos.afectados.mediana)}</strong>
          <small>Intervalo 80 %: ${formatoNumero(datos.limiteAfectados[0])} – ${formatoNumero(
            datos.limiteAfectados[1]
          )}</small>
        </article>
        <article class="prediccion-kpi">
          <span>Daño económico</span>
          <strong>${formatoMoneda(datos.dano.mediana * 1000)}</strong>
          <small>Intervalo 80 %: ${formatoMoneda(
            datos.limiteDano[0]
          )} – ${formatoMoneda(datos.limiteDano[1])} · modelo exploratorio</small>
        </article>
      </div>

      <div class="prediccion-modelos" aria-label="Comparación de modelos">
        <div><span>Red neuronal</span><strong>${Math.round(
          datos.clasificacion.red * 100
        )}%</strong></div>
        <div><span>XGBoost</span><strong>${Math.round(
          datos.clasificacion.xgb * 100
        )}%</strong></div>
        <div><span>Acuerdo</span><strong>${nivelAcuerdo}</strong></div>
      </div>

      <h3 class="prediccion-subtitulo">¿Qué mueve la estimación?</h3>
      <ul class="prediccion-factores">${filasFactores}</ul>
      <p class="prediccion-nota">
        Comparación aproximada contra un escenario promedio. Una flecha hacia
        arriba indica que el dato aumenta la probabilidad; no implica causalidad.
      </p>

      <p class="prediccion-metricas">
        Prueba 2024–2025 · ROC-AUC ${metrica.red_neuronal.roc_auc.toFixed(2)} (red)
        y ${metrica.xgboost.roc_auc.toFixed(2)} (XGBoost) · F1
        ${metrica.red_neuronal.f1.toFixed(2)} y ${metrica.xgboost.f1.toFixed(2)} ·
        ${formatoNumero(metrica.red_neuronal.n)} eventos.
      </p>
    `;
    caja.hidden = false;
    anunciar(
      `${datos.nivel.etiqueta}: ${probabilidad} % de probabilidad de alto impacto. ` +
        `Personas afectadas estimadas: ${formatoNumero(datos.afectados.mediana)}.`
    );
    if (window.innerWidth <= 900) {
      caja.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  function anunciar(texto) {
    const region = $("anuncio-lector");
    if (region) region.textContent = texto;
  }

  /* ------------------------------------------------------------------ *
   * 7. Arranque                                                         *
   * ------------------------------------------------------------------ */
  function conectar() {
    const boton = $("btn-predecir");
    if (boton) {
      boton.addEventListener("click", () => {
        boton.disabled = true;
        calcular()
          .catch((error) => console.error(error))
          .finally(() => {
            boton.disabled = false;
          });
      });
    }

    $("pred-pais")?.addEventListener("change", actualizarContextoPais);
    $("pred-tipo")?.addEventListener("change", () => {
      poblarSubtipos();
      actualizarEscalaPorTipo();
    });
    $("pred-escala")?.addEventListener("change", actualizarPasoMagnitud);

    document.addEventListener("atlas:pestana", (evento) => {
      if (evento.detail && evento.detail.pestana === "prediccion") {
        cargarModelo().catch(() => {});
      }
    });

    const activa = document.querySelector(".pestana.activo");
    if (activa && activa.dataset.pestana === "prediccion") {
      cargarModelo().catch(() => {});
    }

    window.Prediccion = {
      iniciar: () => cargarModelo(),
      calcular,
      estado,
    };
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", conectar);
  } else {
    conectar();
  }
})();
