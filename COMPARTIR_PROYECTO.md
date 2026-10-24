# Cómo compartir el proyecto con un enlace

Guía para publicar el proyecto en GitHub y dejar la aplicación funcionando en
un enlace que se pueda abrir desde cualquier navegador.

Con esto se comparten **dos cosas con dos enlaces** (una sola vez):

1. El **repositorio** con todos los archivos del proyecto.
2. La **aplicación en vivo** (GitHub Pages).

Cuando hagas cambios, basta con subirlos y el enlace se actualiza solo.

---

## Paso 1. Crear la cuenta de GitHub

Entra a <https://github.com> y crea una cuenta si aún no tienes.
Es gratis.

---

## Paso 2. Crear el repositorio vacío

1. En GitHub, arriba a la derecha: **+ → New repository**.
2. Nombre: `proyecto-desastres`
3. Visibilidad: **Public** (necesario para que Pages sea gratis).
4. **No** marques "Add a README file" ni ninguna otra casilla.
5. **Create repository**.

GitHub te mostrará una página con comandos. Los que necesitas son los del
paso siguiente (cambia `TU-USUARIO` por tu nombre de usuario).

---

## Paso 3. Subir el proyecto

Abre una terminal en la carpeta del proyecto y ejecuta:

```bash
cd "C:\Users\itzel\PROYECTO_DESASTRES"

git remote add origin https://github.com/TU-USUARIO/proyecto-desastres.git
git push -u origin main
```

La primera vez te pedirá iniciar sesión en GitHub (se abre el navegador).

> El commit inicial ya está hecho. Solo falta conectarlo a tu repositorio.

---

## Paso 4. Activar la publicación de la app

1. En el repositorio: **Settings** (arriba).
2. Menú izquierdo: **Pages**.
3. En "Build and deployment" → **Source: GitHub Actions**.

No hay que configurar nada más: ya existe el archivo
`.github/workflows/pages.yml`, que publica la carpeta `app/` cada vez que
subes cambios.

---

## Paso 5. Obtener el enlace

1. Ve a la pestaña **Actions**.
2. Espera a que termine el trabajo "Publicar app en GitHub Pages" (1–2 min).
3. El enlace queda como:

```
https://TU-USUARIO.github.io/proyecto-desastres/
```

Ese es el enlace que le mandas a tu compañera. Se abre en celular y
computadora, y puede usar el mapa 3D sin instalar nada.

El enlace a los archivos es:

```
https://github.com/TU-USUARIO/proyecto-desastres
```

---

## Cómo actualizar más adelante

Cada vez que cambies algo:

```bash
cd "C:\Users\itzel\PROYECTO_DESASTRES"
git add -A
git commit -m "Descripción breve del cambio"
git push
```

En uno o dos minutos el enlace de la app ya muestra los cambios.
No hay que volver a mandar nada.

---

## Notas

- **Qué se sube:** todo el proyecto excepto las versiones intermedias del
  dataset (`EMDAT_integrado_WDI.csv`, `EMDAT_procesado.csv`, etc.). El
  pipeline solo usa `EMDAT_integrado_WDI_validado.csv`, que sí se sube. Esos
  archivos siguen en tu disco, solo no viajan al repositorio. Así el
  repositorio pesa ~63 MB en vez de ~157 MB.
- **Repositorio público:** cualquier persona con el enlace puede ver los
  archivos. Los datos son de fuentes públicas (EM-DAT, Banco Mundial), así
  que no hay información sensible.
- **Si algún día quieres el repositorio privado:** la app en vivo requiere
  GitHub Pro. Con el repositorio público funciona gratis.
