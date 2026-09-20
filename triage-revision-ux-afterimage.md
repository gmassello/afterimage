# Triage del reporte `revision-ux-afterimage.md`

## Procedencia

- **Fecha del escaneo:** 19 de septiembre de 2026.
- **Commit declarado:** ninguno; el reporte se midió contra el working tree local.
- **HEAD actual:** `3cc7d21b551d4d61b2e34e478329acd9e067f810` (`Refine UI elements and add a confirmation step for approving writes.`).
- **Estado posterior:** no hay commits posteriores al escaneo. El working tree contiene cambios
  previos del usuario en los mismos archivos de UI, por lo que cualquier implementación debe ser
  quirúrgica y preservar esos cambios.

## Veredictos

| ID | Hallazgo | Veredicto | Evidencia verificada | Alcance propuesto |
|---|---|---|---|---|
| 1 | La traza desborda 22 px a 320 px | **Real** | `services/ui/static/app.css:196` impone un mínimo de 320 px dentro de una página con padding lateral; `box-sizing` ya es global, por lo que el origen es el track mínimo de `.cards`, no el padding de `.card` sugerido por el reporte | Hacer que el mínimo de la grilla no supere el ancho disponible y agregar regresión CSS |
| 2 | El botón de tema anuncia inglés en español | **Real** | `services/ui/static/app.js:22` construye el `aria-label` con una frase inglesa fija, aunque el texto visible ya está localizado | Eliminar el override redundante para que el nombre accesible sea el texto visible localizado |
| 3 | La acción principal queda hasta 2,62 pantallas debajo del inicio | **Real** | `services/ui/templates/index.html:6` agrega `open` cuando la galería está vacía y ubica la guía antes del formulario; `services/ui/tests/test_language.py:85-87` fija la apertura | Mover la guía después del formulario dentro del panel, preservando su apertura y contenido |

## Evidencia que recalibra las recomendaciones

### Hallazgo 1

La premisa se sostiene, pero la causa sugerida en el reporte es imprecisa. `.card` ya participa del
`box-sizing: border-box` global en `services/ui/static/app.css:28`. El ancho de 320 px nace de
`grid-template-columns: repeat(auto-fit, minmax(320px,1fr))` en
`services/ui/static/app.css:196`. El cambio debe aplicarse a la grilla, no compensar padding o borde
en cada tarjeta.

### Hallazgo 2

El texto visible ya sale localizado de `services/ui/text.py:23-24` y
`services/ui/text.py:236-237`, y el icono está excluido con `aria-hidden`. Sin el override inglés,
el algoritmo de nombre accesible usa directamente `Dark`/`Light` o `Oscuro`/`Claro`. No hacen falta
nuevas cadenas ni concatenación por idioma.

### Hallazgo 3

CSS no puede quitar semánticamente el atributo HTML `open` sólo para un breakpoint. Ocultar el
contenido visualmente dejaría un estado expandido falso para tecnología asistiva. La alternativa
más pequeña que conserva el onboarding actual es mover la guía después del formulario dentro del
panel: la acción principal aparece primero y la ayuda sigue abierta en una galería vacía.

## Alcance aprobado

1. Corregir el track mínimo de `.cards` sin alterar tarjetas, métricas ni layout de escritorio.
2. Quitar el `aria-label` inglés redundante para usar el nombre visible ya localizado.
3. Mover la guía de primera visita después del formulario sin cambiar cuándo aparece abierta.
4. Agregar o actualizar tests unitarios enfocados en los tres contratos.
5. Ejecutar lint, type-check, suite completa y repetir en Chrome las mediciones a 320 px y en español.

No se incluye ningún refactor, cambio de copy ni modificación de documentación ajena al reporte.

## Resultado de la implementación

- `.cards` usa una única columna reducible en viewports de hasta 620 px.
- El botón de tema conserva como nombre accesible su texto visible localizado.
- El formulario precede a la guía, que sigue abierta cuando todavía no hay activos.
- Chrome a 320×700 confirmó `overflowX=false`, nombre accesible `Oscuro` y el botón de inspección
  en `y=828,90` (1,18 pantallas, contra 2,62 antes del cambio).
- Verificación automatizada: `197 passed`, `0 skipped`, cobertura `92,79%`, lint y type-check sin
  errores.
