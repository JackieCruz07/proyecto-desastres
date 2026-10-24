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
        ? "#fb7185"
        : tipo === "ok"
        ? "#2dd4bf"
        : "#94a3b8";
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
