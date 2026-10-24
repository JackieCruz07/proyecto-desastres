# Carpeta de reportes

Contiene los reportes de cada actividad del proyecto, en formato LaTeX
(según lo solicitado en el enunciado) y sus recursos asociados.

```
reportes/
└── actividad3/
    ├── DOCUMENTACION_TECNICA.md   Guía técnica de la capa temática
    ├── reporte_actividad3.tex     Reporte formal (en preparación)
    └── imagenes/                  Capturas usadas por el reporte
```

Las capturas se generan automáticamente con:

```bash
python -m src.capturas
```

y se almacenan en `resultados/graficas/capa_tematica/`, desde donde se
copian a `reportes/actividad3/imagenes/` para incluirlas en el `.tex`.
