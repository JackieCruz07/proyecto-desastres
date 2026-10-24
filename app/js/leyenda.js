/* =========================================================================
   leyenda.js — Leyenda temática dinámica
   -------------------------------------------------------------------------
   Dibuja la barra de gradiente, los extremos de la escala y los distintivos
   de los recursos visuales activos (color, elevación, deformación).
   ========================================================================= */

const Leyenda = (() => {
  const barra = document.getElementById("leyenda-barra");
  const titulo = document.getElementById("leyenda-titulo");
  const unidad = document.getElementById("leyenda-unidad");
  const minEtiqueta = document.getElementById("leyenda-min");
  const maxEtiqueta = document.getElementById("leyenda-max");
  const chips = document.querySelectorAll(".chip[data-recurso]");

  /**
   * Actualiza la leyenda completa para una variable temática.
   *
   * @param {object} opciones
   * @param {string} opciones.titulo      Etiqueta de la variable.
   * @param {string} opciones.unidad      Unidad de medida.
   * @param {string} opciones.formato     Formato numérico.
   * @param {string} opciones.rampa       Nombre de la rampa.
   * @param {string[]} opciones.colores   Colores de la rampa.
   * @param {number} opciones.min         Valor mínimo de la escala.
   * @param {number} opciones.max         Valor máximo de la escala.
   */
  function actualizar(opciones) {
    titulo.textContent = opciones.titulo;
    unidad.textContent = opciones.unidad;

    barra.style.background = `linear-gradient(90deg, ${opciones.colores.join(
      ", "
    )})`;

    minEtiqueta.textContent = Escalas.formatearValor(
      opciones.min,
      opciones.formato,
      opciones.formato === "moneda" ? { mostrarMXN: true } : {}
    );
    maxEtiqueta.textContent = Escalas.formatearValor(
      opciones.max,
      opciones.formato,
      opciones.formato === "moneda" ? { mostrarMXN: true } : {}
    );
  }

  /**
   * Marca como activos los recursos visuales en uso.
   * @param {{color:boolean, elevacion:boolean, deformacion:boolean}} recursos
   */
  function marcarRecursos(recursos) {
    chips.forEach((chip) => {
      const activo = recursos[chip.dataset.recurso] === true;
      chip.classList.toggle("activo", activo);
      chip.setAttribute("aria-pressed", String(activo));
    });
  }

  /**
   * Pinta la muestra de paleta del panel lateral.
   */
  function pintarPaleta(colores) {
    const contenedor = document.getElementById("paleta");
    contenedor.innerHTML = "";
    colores.forEach((color) => {
      const muestra = document.createElement("div");
      muestra.className = "paleta__muestra";
      muestra.style.background = color;
      muestra.title = color;
      contenedor.appendChild(muestra);
    });
  }

  return { actualizar, marcarRecursos, pintarPaleta };
})();

window.Leyenda = Leyenda;
