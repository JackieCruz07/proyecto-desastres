/* =========================================================================
   estado.js — Barra de estado y tarjetas de resumen
   -------------------------------------------------------------------------
   Muestra mensajes de progreso, error y las métricas generales de la capa.
   ========================================================================= */

const Estado = (() => {
  const texto = document.getElementById("estado-texto");

  /** Escribe un mensaje en la barra inferior. */
  function mensaje(contenido, tipo = "info") {
    texto.textContent = contenido;
    texto.style.color =
      tipo === "error"
        ? "#f9a8b2"
        : tipo === "ok"
        ? "#ffc14c"
        : "#d9d0ee";
  }

  /**
   * Construye las tarjetas de resumen del panel.
   * @param {Array<{titulo:string, valor:string, nota:string}>} tarjetas
   */
  function tarjetas(lista) {
    const contenedor = document.getElementById("tarjetas-resumen");
    contenedor.innerHTML = "";

    lista.forEach((item) => {
      const tarjeta = document.createElement("div");
      tarjeta.className = "tarjeta";
      tarjeta.innerHTML = `
        <div class="tarjeta__titulo">${item.titulo}</div>
        <div class="tarjeta__valor">${item.valor}</div>
        <div class="tarjeta__nota">${item.nota}</div>
      `;
      contenedor.appendChild(tarjeta);
    });
  }

  return { mensaje, tarjetas };
})();

window.Estado = Estado;
