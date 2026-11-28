# Ejecutar el Atlas Global de Desastres con Docker

Esta entrega incluye todo lo necesario para ejecutar la aplicación sin instalar
Python, Node.js ni dependencias adicionales. Solo se necesita **Docker**.

## Requisito

- Docker Desktop (Windows o macOS) o Docker Engine (Linux).
- Verificar la instalación:

  ```bash
  docker --version
  ```

## Inicio rápido

Desde la carpeta del proyecto (donde está `docker-compose.yml`):

```bash
docker compose up --build -d
```

Abrir en el navegador:

```text
http://localhost:8080
```

Para detener la aplicación:

```bash
docker compose down
```

## Opción sin Docker Compose

```bash
docker build -t atlas-desastres .
docker run --rm -d -p 8080:80 --name atlas-desastres atlas-desastres
```

Abrir `http://localhost:8080`. Para detenerla:

```bash
docker stop atlas-desastres
```

## Abrir desde otro dispositivo de la misma red

1. Inicia la aplicación con Docker.
2. Obtén la dirección IP del equipo servidor:
   - Windows: `ipconfig`
   - macOS/Linux: `ifconfig` o `ip addr`
3. Desde el otro dispositivo abre:

   ```text
   http://IP_DEL_EQUIPO:8080
   ```

Si no responde, permite el puerto 8080 en el firewall del equipo servidor.

## Cambiar el puerto

Edita `docker-compose.yml` y cambia el lado izquierdo del mapeo:

```yaml
ports:
  - "9000:80"
```

Después ejecuta de nuevo:

```bash
docker compose up -d
```

La aplicación quedará en `http://localhost:9000`.

## Qué incluye la imagen

- La aplicación completa de `app/`.
- Los datos en `app/datos/` (GeoJSON, JSON y metadatos).
- El paquete de modelos en `app/modelos/modelo_prediccion.json`, que permite
  usar la pestaña **Predecir** (red neuronal + XGBoost) sin servidor de ML.
- MapLibre GL, Chart.js y las tipografías **dentro del proyecto**, por lo que la
  aplicación funciona sin conexión a internet.
- Nginx configurado con compresión, tipos MIME correctos para `.geojson` y
  caché de archivos estáticos.

## Comprobaciones realizadas

- La imagen construye correctamente con `docker build`.
- El contenedor responde en el puerto 8080.
- La aplicación carga el mapa, los datos, la vista de México y la pestaña
  **Predecir** sin errores.
- La inferencia de la red neuronal y XGBoost se ejecuta en el navegador, sin
  peticiones externas.
- La página se sirve sin depender de CDN externos.

## Archivos de la entrega

| Archivo | Función |
|---------|---------|
| `Dockerfile` | Construye la imagen con Nginx y la aplicación. |
| `docker-compose.yml` | Levanta el contenedor en el puerto 8080. |
| `docker/nginx.conf` | Configuración del servidor web. |
| `.dockerignore` | Excluye notebooks, datos de trabajo y documentos pesados del contexto de construcción. |
