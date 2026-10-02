# Pendiente — cierre OpenCV AI Competition 2026

Cierre: **2026-10-26 23:45 -07:00** (2026-10-27 03:45 -03:00). Competencia:
<https://opencv26.devpost.com/> · Submission: <https://devpost.com/software/afterimage-ibp376> · PR: no aplica.

Etapas (de la pagina de fechas del evento; en Devpost, `/details/dates`): submissions hasta 2026-10-26 23:45 -07:00, judging 2026-10-27 00:00 -07:00 → 2026-11-09 23:45 -08:00,
ganadores 2026-11-10 09:00 -08:00.

Estado del codigo en una linea: <N tests verdes, que esta hecho, que falta>.

---

## Superficies

| Superficie | Donde | Estado | Verificado |
|---|---|---|---|
| Repo y CI | `<owner>/<repo>` @ `<sha>` | | |
| Sitio | <URL> | | |
| Submission | <URL publica, no /edit> | | |
| Tarjeta en la galeria | <URL de la galeria> | | |
| PR upstream | #<n> | | |
| Segundo checkout | `~/<ruta>` rama `<rama>` | | |
| Video | `<id>` | | |
| Deck | `docs/deck.pdf` sha256 `<hash>` | | |

## Hechos duplicados

| Hecho | Valor real | Comando que lo produce | Copias |
|---|---|---|---|
| Cantidad de tests | | `uv run pytest -q \| tail -1` | |
| Archivos del PR | | `gh pr view <n> --json files --jq '.files\|length'` | |
| Version | | | |

## Lo que no cierra

Lo que no funciona, con el motivo. Esto es lo que evita prometer de mas en el formulario, y en una
competencia donde todos prometen, decirlo es diferencial.

- **<Cosa>** — <por que no cierra, y que haria falta para cerrarla>.

## No romper esto al volver

Las trampas del repo, para el que lo toque dentro de tres dias (que sos vos, sin contexto).

- `<script>` borra `<directorio gitignoreado>`: si se corre, se pierde <que>.
- `<archivo generado>` tiene que copiarse tambien a `<segundo lugar>`.
- `<test>` fija el output de `<comando>`: cambiar el formato obliga a reconciliarlo a mano.

## Fuera de mi control

No son tareas: son riesgos. Cada uno con su fallback.

- **Envio del formulario de Devpost antes de las 23:45 PDT** (no 23:59 como dice el overview) — fallback: enviarlo el 24-25 Oct y editar despues; Devpost permite editar hasta el cierre.
- **Video publico o unlisted, accesible sin login** — fallback: subir la misma toma a un segundo host y poner ambos links.
- **Endpoint vivo durante todo el judging (27 Oct → 9 Nov)** — fallback: ofrecer screen-share en vivo, que la regla acepta.
- **Check-in de Zoom 7-14 Oct, solo si hay compute grant** — fallback: ninguno; confirmar si aplica.
