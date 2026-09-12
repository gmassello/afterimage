# Revision de usabilidad y diseno — afterimage (endpoint publico)

Probado en Chrome contra el Function URL desplegado (build del commit `b50a747`), en tema claro y
oscuro, a `innerWidth` **1374**, **1309** y **533** px — 533 es lo mas angosto que permite Chrome en
macOS, asi que los anchos de telefono se derivan restringiendo el ancho del contenedor y quedan
marcados como derivados. Cada hallazgo abre con la medicion que lo sostiene.

> El arbol de trabajo local tiene cambios sin commitear sobre estos mismos archivos. Todo lo medido
> aca es la version que hoy sirve el endpoint, no el arbol local.

La base esta sana: el HTML pesa 6 KB, responde en 206 ms, no hay desbordes horizontales, el CLS es 0
y el foco tiene outline propio. Lo que falla no es el diseno visual, que es bueno: es que la pagina
que se mueve sola no le avisa a nadie, y que el formulario de entrada no tiene una sola etiqueta.

## Lo que ya esta bien

| Verificado | Medicion |
|---|---|
| Peso del documento y latencia | HTML 6 KB, TTFB 206 ms, `loadEventEnd` 224 ms |
| Estabilidad visual | CLS **0** sobre carga limpia (`uptimeMs` 6309), cero shifts > 0.005 |
| Sin desborde horizontal | a `innerWidth` 533: `scrollWidth` 520 |
| Indicador de foco | `:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px }` |
| Tamano de objetivo (2.5.8 AA) | nav 84 px entre centros, filas 45 px: los circulos de 24 px no se intersecan, pasa por excepcion de espaciado |
| Foco obscurecido (2.4.11 AA) | no aplica: `header.top` es `position: static` |
| Toggle de tema | 69x32 px, conserva el foco tras el click (`activeElement === boton`), persiste en `localStorage` |
| Alt de las figuras del trace | `alt='baseline in memory'` / `alt='capture under inspection'` |
| Barra metrica-vs-umbral | usa longitud y posicion con marca de umbral, no gauge ni angulo — es la forma correcta de mostrar el par ([NN/g](https://www.nngroup.com/articles/dashboards-preattentive/)) |
| Indicador de trabajo | el punto pulsa (`animation: pulse 1.1s infinite`): distingue "trabajando" de "colgado" |

## P0 — la demo se mueve sola y nadie se entera

### 1. El bloque en vivo se reemplaza entero y tira el foco al `<body>` cada 1,5 segundos

```
trace 02fb84c00e01, carga limpia (uptimeMs 4469, runState done)
tabbables dentro de .live: 7
foco en .live .tip  → activeElement === tip : true
current.replaceWith(fresh)  (la linea exacta de app.js)
+150ms              → activeElement : BODY   perdioElFoco: true

/queue, misma prueba con el enlace del estado vacio
antes: activeElement === enlace : true   → despues: BODY   cadencia: 5000 ms
```

`app.js` hace `current.replaceWith(fresh)` sobre todo el `[data-poll]` en cada vuelta. El unico
guard es `busy()`, que solo mira si hay un `<details>` abierto — no mira donde esta el foco. Mientras
el run trabaja, quien navega con teclado es devuelto al principio del documento cada 1,5 s, y en la
cola de aprobacion cada 5 s, justo sobre los botones Approve / Reject.

**Fix:** en `services/ui/static/app.js`, antes de reemplazar, comprobar
`document.activeElement` y saltear la vuelta si esta dentro del nodo (igual que `busy()`), o
reemplazar solo los hijos que cambiaron. Dos lineas, y resuelve tambien la mitad del hallazgo 2.

[WCAG 2.4.3 Focus Order](https://www.w3.org/WAI/WCAG22/Understanding/focus-order.html)

### 2. Trece segundos de trabajo que no existen para quien no ve la pantalla, y un fallo que no se dice

```
censo de regiones vivas, las cuatro vistas
[aria-live],[role=status],[role=alert] : 0     (index, asset, queue, trace)
duracion real de un run, leida del propio trace: 13.45 s
app.js: fetch(page.dataset.executeUrl, { method: 'POST' }).catch(() => {})
app.js: if (live && runState !== 'done' && ++attempts < 400) setTimeout(poll, next)
```

El trace se va llenando solo, pero el cambio no se anuncia: con lector de pantalla la pagina queda
muda los 13 s y despues tampoco avisa que termino. Peor: si el POST que arranca el run falla, el
`catch` vacio se lo come, y el poller reintenta 400 veces (10 minutos) y se apaga en silencio
dejando "working…" en pantalla para siempre. Nadie sabe si sigue trabajando o si se colgo.

**Fix:** en `services/ui/templates/trace.html`, poner `role='status' aria-live='polite'` en un
contenedor chico presente desde el primer render (no en todo el `.live`: anunciar el bloque entero
en cada poll es spam) con el paso actual y los segundos transcurridos; y en `app.js`, en el `catch`
del execute y al agotar los intentos, escribir ahi mismo un estado terminal de error con que hacer.

[WCAG 4.1.3 Status Messages](https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html) ·
[live regions, MDN](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Guides/Live_regions) ·
[NN/g: pasados 10 s hace falta avance y estimacion](https://www.nngroup.com/articles/response-times-3-important-limits/)

### 3. El formulario principal no tiene una sola etiqueta, y la regla de formato vive solo en un tooltip

```
<label> en la pagina : 0        aria-label en la pagina : 0
input[name=asset_id] : nombre accesible = placeholder 'asset-id'
  placeholder rgb(117,117,117) sobre el fondo del campo : 3.74:1 claro / 3.82:1 oscuro (minimo 4.5)
input[type=file]     : sin nombre accesible; el lector solo dice "Choose File"
title='Lowercase letters, digits and hyphens, up to 64 characters. For example: panel-a7-north'
  + pattern='[a-z0-9-]{1,64}'  → unica fuente de la regla
```

El `asset-id` desaparece apenas se escribe la primera letra, porque el placeholder es la etiqueta.
Y la unica explicacion de que se puede escribir esta en un `title`: no llega al teclado, no llega al
telefono, y su lectura por lector de pantalla es inconsistente. Quien escribe `Panel A7` recibe el
globo nativo "coincida con el formato solicitado" sin ver nunca la regla — en la unica accion que la
demo le pide a un jurado.

**Fix:** en `services/ui/templates/index.html`, dos `<label>` visibles (`asset id`, `capture`) y
mover el texto del `title` a la `<p class='hint'>` que ya esta debajo del formulario, que ademas
queda leida para todos. Borra el `title` y el problema de contraste del placeholder de una vez.

[MDN sobre `title`](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Global_attributes/title) ·
[Roselli: ponerlo en el texto visible](https://adrianroselli.com/2024/01/using-abbr-element-with-title-attribute.html) ·
[WebAIM: `title` es ultimo recurso](https://webaim.org/techniques/forms/advanced)

## P1 — accesibilidad verificada en el navegador

### 4. Cuatro colores de texto por debajo de 4.5:1, en los dos temas

```
                          claro    oscuro   px   minimo
.kicker (titulos)          3.50     4.08    11     4.5
table th                   3.50     4.08    11     4.5
.hint (prosa chica)        3.96     3.52    13     4.5
::placeholder              3.74     3.82    14     4.5
(pasan: .brand 11.49 · nav 5.50 · enlaces de tabla 5.50 · .btn.ok 6.23)
```

Los `.kicker` son los titulos de seccion de todas las vistas y los `.hint` son casi toda la prosa
del sitio: el texto que explica que hace cada cosa es el que menos se lee. A 11 px y 3.5:1, en una
sala con proyector o con luz de ventana, desaparece.

**Fix:** en `services/ui/static/app.css`, subir el token `--dim` hasta 4.5:1 en ambos temas (ajusta
las cuatro de una) y llevar `.kicker` de 11 px a 12.

[WCAG 1.4.3 Contrast (Minimum)](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html)

### 5. El documento no tiene encabezados ni `main`

```
index  : h1..h6 = 0   landmarks = HEADER,NAV        skip link: no   <main>: 0
asset  : h1..h6 = 0   landmarks = HEADER,NAV        <main>: 0
queue  : h1..h6 = 0   landmarks = HEADER,NAV        <main>: 0
trace  : h1..h6 = [H2] landmarks = HEADER,NAV,FOOTER <main>: 0
los titulos de seccion son <div class='kicker'>
```

Quien navega por encabezados —la forma normal de recorrer una pagina con lector de pantalla— no
tiene por donde entrar: en tres de las cuatro vistas no hay ni uno, y en la cuarta el documento
empieza en nivel 2. El titulo del `<title>` es lo unico que orienta.

**Fix:** en `services/ui/templates/base.html`, envolver `{% block body %}` en `<main>`, y en
`index.html`, `asset.html`, `queue.html` convertir el primer `.kicker` de cada vista en `<h1>` (con
la misma clase, el CSS no cambia); en `trace.html` el `h2` del titular pasa a `h1`.

### 6. El tooltip propio no se puede cerrar, y su etiqueta cuelga de un `<span>` sin rol

```
7 de los 12 elementos tabulables del trace son .tip (58%)
<span class='tip' tabindex='0' data-tip='…' aria-label='…'>   role: null
.tip::after { display:none } → .tip:hover::after, .tip:focus-visible::after { display:block }
app.js: ningun listener de keydown en todo el archivo → Escape no cierra nada
bottom: calc(100% + 6px) → 6 px de hueco entre el disparador y el globo
```

El `title` nativo esta exento de 1.4.13 por ser del navegador; este tooltip propio no lo esta, y no
cumple "dismissible": no hay forma de sacarlo sin mover el foco. Ademas `aria-label` sobre un `span`
sin rol es lo que ARIA no garantiza exponer, asi que la explicacion puede no llegar igual. Y mas de
la mitad de las paradas de tabulacion del trace son estos spans, que no hacen nada al pulsarlos.

**Fix:** en `services/ui/templates/partials/components.html`, cambiar el macro `tip` por un
`<abbr>`/`<span>` **sin** `tabindex` con la explicacion en texto visible una vez por metrica (una
linea de leyenda arriba de las tarjetas), y borrar el `aria-label`. Si se quiere conservar el globo,
agregar un `keydown` de Escape en `app.js` y cerrar el hueco de 6 px.

[WCAG 1.4.13](https://www.w3.org/WAI/WCAG22/Understanding/content-on-hover-or-focus.html) ·
[Higley: la UI tiene que entenderse sin leer ningun tooltip](https://sarahmhigley.com/writing/tooltips-in-wcag-21/)

### 7. Subir el tamano de letra del navegador no cambia nada, y las preferencias del sistema se ignoran

```
document.documentElement.style.fontSize = '32px'  →  .hint sigue en 13px, body sigue en 15px
declaraciones font-size en app.css : 43    en rem : 0    en em : 0
reglas @media de prefers-color-scheme o prefers-reduced-motion : 0
medido en esta maquina: OS en dark, localStorage vacio → la pagina abrio en light
```

Quien subio el tamano de letra por defecto porque lo necesita ve la pagina identica (el zoom sigue
funcionando, que es la otra via, pero no la reemplaza). Y quien tiene el sistema en oscuro recibe
una pantalla blanca en la primera visita, aunque la app tenga tema oscuro completo.

**Fix:** en `app.css`, pasar los `font-size` a `rem`; y en `base.html`, que el script inline
respete `matchMedia('(prefers-color-scheme: dark)')` cuando no hay nada en `localStorage`. Agregar
un bloque `@media (prefers-reduced-motion: reduce) { .dot { animation: none } }`.

[F94, unidades que no escalan](https://www.w3.org/WAI/WCAG21/Techniques/failures/F94.html)

### 8. El nombre accesible del toggle incluye el dibujito

```
<button class='toggle' id='theme'>◐<span id='theme-label'>Dark</span></button>
nombre accesible : "◐Dark"    (◐ = U+25D0)    aria-pressed : null
```

El lector de pantalla lee el nombre del caracter antes de la palabra. Y "Dark" nombra el destino,
no el estado, sin `aria-pressed` que lo desambigue.

**Fix:** en `services/ui/templates/partials/header.html`, `<span aria-hidden='true'>&#9680;</span>`
y etiqueta `Switch to dark` / `Switch to light`.

## P2 — lo que cuesta comprension en los primeros diez segundos

### 9. La portada no dice que es esto

```
palabras visibles en toda la vista index : 40
unica prosa : "JPEG, PNG, WebP, TIFF or BMP, up to 6 MB. The trace opens immediately and fills in
               as the agent works."  (21 palabras, sobre formatos de archivo)
enlaces a otro dominio (repo, informe, video) : 0
```

Un jurado que llega del README ve una marca, seis identificadores de panel y un formulario. Ninguna
linea dice que el agente inspecciona, recuerda y decide, ni invita a abrir un asset para ver una
decision ya tomada — que es lo unico que se puede hacer sin tener una foto a mano. Y desde aca no
hay forma de volver al repositorio ni al informe.

**Fix:** en `index.html`, una linea bajo el `<h1>` con que hace y que mirar ("cada asset guarda lo
que el agente decidio y con que numero"), y en `partials/header.html` un enlace `repo` a la derecha
del nav. Dos cambios de una linea.

[NN/g: la decision se toma en los primeros 10 segundos](https://www.nngroup.com/articles/how-long-do-users-stay-on-web-pages/)

### 10. La cola de aprobacion vacia no muestra de que se trata

```
innerWidth 1374 x innerHeight 597 → ultimo contenido en y=148, 75% de la primera pantalla vacia
texto : "nothing awaiting approval · 6 assets in memory, all of them settled"  a 13 px y 3.96:1
```

La aprobacion humana es la tesis del proyecto, y es el segundo de los dos enlaces del nav. Hoy el
jurado que lo toca se encuentra una pantalla en blanco con una linea gris: no ve nunca como se ve
una aprobacion pendiente, ni sabe que el trace `02fb84c00e01` tiene una ya aprobada para mirar.

**Fix:** en `services/ui/templates/queue.html`, en la rama vacia, ademas del recuento, enlazar un
run aprobado como ejemplo ("asi se ve una que ya paso por aca") y describir en una linea que gatilla
una entrada (`score >= 0.4`), que ya esta calculado en el kicker.

[NN/g: estado vacio = estado + que lo llenaria + camino a la tarea](https://www.nngroup.com/articles/empty-state-interface-design/)

### 11. En pantalla angosta el par baseline/capture nunca esta junto

```
innerWidth 533 : .shots queda en 1 columna de 475 px (auto-fit, minmax(280px,1fr))
figura baseline : top 2404, alto 339      figura capture : top 2760, alto 375
alto del par : 731 px   contra innerHeight 652  → nunca coexisten en pantalla
y ademas: el par arranca a 3.69 pantallas del tope; el documento mide 5.06 pantallas
```

El producto es una comparacion visual, y en un telefono deja de ser una comparacion: hay que
recordar la primera foto mientras se scrollea a la segunda. Las imagenes son apaisadas (800x533), a
media columna entrarian las dos juntas sin problema.

**Fix:** en `app.css:79`, bajar el `minmax(280px,1fr)` de `.shots` a `minmax(140px,1fr)` para que el
par se mantenga en dos columnas en angosto. Una linea.

### 12. Un rechazo en la subida borra el `asset-id` ya tecleado

```
POST /inspections rechazado → index_page(store.list_assets(), error=...)   (services/api/app.py)
index.html no recibe ni repone asset_id → el campo vuelve vacio
el aviso dice: "Pick the file again before retrying — the browser cannot keep it for you."
```

El archivo no se puede reponer por seguridad y el aviso lo explica bien, pero el identificador si se
puede: hoy hay que volver a tipearlo junto con volver a elegir la foto, despues de un error.

**Fix:** pasar `asset_id` al render de error en `services/api/app.py` y ponerlo como `value` en
`index.html`.

[WCAG 3.3.7 Redundant Entry](https://www.w3.org/WAI/WCAG22/Understanding/redundant-entry.html)

### 13. El `input[type=file]` desborda su contenedor por debajo de ~360 px de ancho

```
el campo mide 322 px fijos (ancho intrinseco del control nativo, no encoge: .input no tiene max-width)
derivado restringiendo el ancho del contenedor, no medido a ese viewport:
  contenido 346 px (≈ viewport 390) : entra, el formulario pasa a 3 filas
  contenido 316 px (≈ viewport 360) : el campo sobresale 29 px del contenedor
  contenido 276 px (≈ viewport 320) : sobresale 46 px
```

En un Android comun el selector de archivo se sale del recuadro del panel. macOS no deja achicar
Chrome por debajo de 533 px, asi que esto esta derivado del ancho del contenedor, no medido a 360.

**Fix:** `.input { max-width: 100% }` en `app.css:175`. Una linea.

### 14. Las fechas se muestran como el ISO crudo

```
"2026-09-10T00:33:34.227+00:00"   (timeline y kicker del trace)
```

Los milisegundos y el offset no aportan nada al lector y hacen que dos entradas del mismo dia se
distingan recien en el caracter 12. La idea de "memoria longitudinal" se lee mejor con "hace 6
dias · 10 sep 2026".

**Fix:** un filtro Jinja de formato en `services/ui/views.py`, usado en `asset.html` y `trace.html`.

## P3 — distribucion y peso

### 15. 1,5 MB de PNG para pintar cuatro miniaturas de 90x60

```
/assets/panel-b3-east a innerWidth 533
  4 <img> renderizados a 90x60 css, naturales 800x533  → 8.9x el ancho que se ve
  descargas de imagen: 2 (las otras dos, cache) = 1533 KB     documento HTML: 6 KB
  ninguna con loading='lazy' ni width/height
/assets/panel-a7-north a 1374: 3 descargas = 2263 KB de un total de 2281 KB de pagina
```

El HTML tarda 224 ms y despues la pagina se pasa un minuto trayendo fotos de 800 px para mostrarlas
del tamano de una estampilla. En el wifi de una feria, la vista de historial es lo que no carga.

**Fix:** servir una miniatura desde `/images/` (un `?w=180` que `services/api/app.py` resuelva con
`cv2.resize`, que ya esta en el stack), y mientras tanto `loading='lazy'` con `width`/`height` en
`asset.html`. El CLS hoy es 0 y hay que dejarlo asi: por eso van las dimensiones explicitas.

[web.dev: lazy loading a nivel navegador](https://web.dev/articles/browser-level-image-lazy-loading)

### 16. El link compartido llega pelado

```
meta og:* : 0    twitter:* : 0    meta description : 0    link rel=icon : 0    theme-color : 0
```

El enlace que el jurado recibe por Slack, Discord o Devpost aparece sin titulo util, sin imagen y
sin icono en la pestana, al lado de otros proyectos que si lo tienen. Es el arreglo mas barato del
reporte: cuatro etiquetas en un archivo.

**Fix:** `og:title`, `og:description`, `og:image` (sirve `docs/img/trace.png`) y un `rel='icon'` en
`services/ui/templates/base.html`.

### 17. La hoja de Google Fonts bloquea el render

```
<link rel=stylesheet href=fonts.googleapis.com/css2>  1 KB, 30 ms en esta conexion
pesos pedidos: 400;500;600;700
```

Hoy cuesta 30 ms, asi que no es urgente; en la red de una conferencia es el recurso de tercero que
retrasa el primer pintado y el unico que puede fallar entero. Autohospedar los `.woff2` que se usan
de verdad lo elimina.

**Fix:** bajar los cuatro pesos a `services/ui/static/` y servirlos desde el mismo origen, en
`base.html`.

## Lo que revise y decidi no reportar

- **Tamano de objetivo 24x24 (2.5.8 AA).** Los enlaces del nav miden 40x20 y los de la tabla 100x17,
  por debajo de 24 de alto, pero pasan por la **excepcion de espaciado**: 84 px entre centros en el
  nav y 45 px entre filas, asi que los circulos de 24 px no se intersecan. Queda como ergonomia
  tactil (la fila entera podria ser el objetivo), no como incumplimiento. Y el minimo AA es 24x24,
  no 44x44: 44 es 2.5.5, que es **AAA**.
- **2.4.11 Focus Not Obscured.** No aplica: `header.top` es `position: static`, nada tapa al
  componente enfocado.
- **CLS.** 0 sobre carga limpia pese a que las imagenes no traen `width`/`height`: el CSS les fija
  la caja. Por eso el fix del hallazgo 15 pide dimensiones explicitas, para no romper lo que hoy
  esta bien.
- **Desborde horizontal a 533 px.** `scrollWidth` 520 contra `innerWidth` 533: no hay. El desborde
  del hallazgo 13 es del contenedor interno y solo por debajo de ~360.
- **Costo del polling.** 3 fetch en 11 s en `/queue`, documento de 6 KB: no llega a ser un problema
  de INP ni de bateria. Lo que importa del poller es el foco (hallazgo 1), no su costo.
- **`alt=''` en las miniaturas del historial.** Es la decision correcta: cada fila ya lleva fecha,
  id y veredicto en texto, la imagen no agrega informacion que no este escrita.
- **3.2.6 Consistent Help.** No se dispara: el sitio no ofrece ningun mecanismo de ayuda. Si se
  agrega el enlace al repo del hallazgo 9, tiene que quedar en el mismo lugar del `header.html`
  compartido por las cuatro vistas, y entonces cumple sola.
- **4.1.1 Parsing.** Quedo obsoleta y removida en WCAG 2.2; no la evalue.
- **Los numeros del trace.** `score 0.6798 >= 0.4 -> human_approval` cierra contra
  `severity_score_approve = 0.40` de `services/agent/policy.py`, y los 13.45 s contra las duraciones
  por herramienta (245.8 + 13184.5 + 11.6 + 3.2 ms). No hay ninguna cifra inventada en pantalla.
- **La subida real de una foto.** No la ejecute: habria escrito un asset nuevo en la demo publica
  que hoy miran los jurados. Todo lo del run en vivo esta medido sobre el codigo que corre el poller
  y reproducido con su misma linea de reemplazo, sobre cargas limpias.

## Orden sugerido, por retorno sobre esfuerzo

| | Cambio | Toca | Por que |
|---|---|---|---|
| 1 | `og:*`, `description` y favicon | `templates/base.html` | cuatro lineas, y cambia como se ve el proyecto en cada link compartido |
| 2 | No reemplazar el bloque si el foco esta adentro | `static/app.js` | dos lineas, y devuelve el teclado durante todo el run y toda la cola |
| 3 | `role='status'` con paso y segundos + estado de error al agotar intentos | `templates/trace.html`, `static/app.js` | hace visible el trabajo y el fallo; hoy los 13 s son mudos y el error no se dice |
| 4 | `<label>` en el formulario y el `title` movido a la `.hint` | `templates/index.html` | arregla la unica accion que la demo pide, y borra el contraste del placeholder |
| 5 | `--dim` a 4.5:1 y `.kicker` a 12 px | `static/app.css` | un token, cuatro estilos de texto que hoy no se leen |
| 6 | `<main>` y el primer `.kicker` de cada vista como `<h1>` | `base.html`, `index.html`, `asset.html`, `queue.html` | el CSS no cambia; da la estructura que hoy no existe |
| 7 | Una linea que diga que es, y enlace al repo | `index.html`, `partials/header.html` | los primeros diez segundos del jurado |
| 8 | `.input { max-width:100% }` y `.shots` a `minmax(140px,1fr)` | `static/app.css` | dos lineas: arregla el desborde en Android y devuelve la comparacion lado a lado |
| 9 | Ejemplo enlazado en la cola vacia | `templates/queue.html` | la tesis del proyecto deja de ser una pantalla en blanco |
| 10 | Miniaturas servidas al tamano que se ven | `services/api/app.py`, `templates/asset.html` | 1,5 MB menos por vista de historial |
| 11 | `font-size` en `rem`, `prefers-color-scheme`, `prefers-reduced-motion` | `static/app.css`, `base.html` | preferencias del sistema que hoy no hacen nada |
| 12 | Fechas legibles y `asset_id` repuesto tras un error | `services/ui/views.py`, `services/api/app.py` | pulido, con el trabajo ya hecho arriba |
