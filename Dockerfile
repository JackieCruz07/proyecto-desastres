# Atlas Global de Desastres — imagen de producción
# Sirve la aplicación web estática con Nginx.
FROM nginx:1.27-alpine

LABEL org.opencontainers.image.title="Atlas Global de Desastres" \
      org.opencontainers.image.description="Aplicación web interactiva de desastres naturales (EM-DAT, CENAPRED, WDI y OWID)" \
      org.opencontainers.image.source="https://github.com/JackieCruz07/proyecto-desastres"

# Configuración del servidor: compresión, tipos MIME y caché.
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf

# Solo se copia la aplicación: HTML, CSS, JS, datos y librerías locales.
COPY app/ /usr/share/nginx/html/

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -qO- http://127.0.0.1/ >/dev/null 2>&1 || exit 1

CMD ["nginx", "-g", "daemon off;"]
