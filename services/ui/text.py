from functools import lru_cache

from markupsafe import Markup

LANGS = ("en", "es")
DEFAULT_LANG = "en"

REGISTERS = ("plain", "tech")
DEFAULT_REGISTER = "plain"

MONTHS = {
    "en": ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"),
    "es": ("ene", "feb", "mar", "abr", "may", "jun",
           "jul", "ago", "sep", "oct", "nov", "dic"),
}

_EN = {
    "nav_assets": "assets",
    "nav_activity": "activity",
    "nav_queue": "approval queue",
    "nav_how": "how it works",
    "nav_memory": "memory",
    "nav_system": "system",
    "nav_open_app": "open app",
    "nav_trace": "trace",
    "title_trace": "inspection trace",
    "theme_dark": "Dark",
    "theme_light": "Light",
    "lang_label": "Language",
    "register_label": "Detail",
    "views_label": "Views",
    "skip_to_content": "Skip to content",
    "plain_name": "plain",
    "tech_name": "technical",

    "upload_rejected": "That capture was not accepted.",
    "upload_retry": Markup(
        "Pick the file again &mdash; the browser cannot keep it for you."
    ),
    "new_inspection": "new inspection",
    "upload_hint_tech": Markup(
        "The asset id takes lowercase letters, digits and hyphens, up to 64 characters "
        "&mdash; an id memory already holds adds to that asset&rsquo;s history, a new one "
        "starts its own. JPEG or PNG, up to 6&nbsp;MB. The trace opens "
        "immediately and fills in as the agent works."
    ),
    "upload_hint_plain": Markup(
        "Give the thing you are watching a name, and send a photo of it. Use the same name next "
        "time and this becomes its history; a new name starts a new one. Lowercase letters, "
        "numbers and hyphens, up to 64 characters, and a JPEG or PNG photo up to 6&nbsp;MB. The result opens "
        "straight away and fills in while the agent looks."
    ),
    "label_asset_id": "asset id",
    "asset_id_placeholder": "e.g. panel-a7-north",
    "label_capture": "capture",
    "drop_hint": "or drop one here",
    "inspect": "inspect",
    "gallery_title": "assets in memory",
    "gallery_lede_tech": "Each asset keeps every inspection the agent ran on it, the branch it took "
                    "and the number that decided it. Open one, or send a new capture above.",
    "gallery_lede_plain": "Each thing you watch keeps every check the agent ran on it, what it "
                          "decided, and the number behind the decision. Open one, or send a new "
                          "photo above.",
    "no_summary": "no inspection summary yet",
    "empty_gallery": "Nothing in memory yet. Send the first capture above and the agent will "
                     "keep every inspection it runs on it.",
    "asset_search": "Search assets",
    "asset_search_placeholder": "asset id or result",
    "asset_filter_all": "all results",
    "asset_filter_empty": "No assets match those filters.",

    "landing_hero_kicker": "VISUAL INSPECTION · LONGITUDINAL MEMORY",
    "landing_hero_title": "The inspection that remembers what it saw.",
    "landing_hero_lede": "Upload a capture. Afterimage checks its quality, anchors it to the stored "
                         "baseline, measures the change and stops when a person must decide.",
    "landing_primary_cta": "Open the application",
    "landing_secondary_cta": "See how it works",
    "landing_demo_kicker": "HOW THE LOOP BRANCHES",
    "landing_demo_title": "Four captures, four different answers.",
    "landing_demo_hint": "An illustration of the path each capture takes. Run one in the "
                         "app to see the measured numbers behind it.",
    "landing_demo_result": "result",
    "landing_demo_scenario": "demo capture",
    "landing_demo_previous": "Previous",
    "landing_demo_pause": "Pause",
    "landing_demo_replay": "Replay",
    "landing_demo_next": "Next",
    "landing_stage_quality": "Quality",
    "landing_stage_align": "Align",
    "landing_stage_diff": "Compare",
    "landing_stage_rescan": "Rescan",
    "landing_stage_severity": "Decide",
    "landing_state_done": "done",
    "landing_state_skipped": "skipped",
    "landing_state_waiting": "waiting",
    "landing_state_stopped": "stopped here",
    "landing_metrics_label": "Measured on the reproducible evaluation set",
    "landing_metric_real": "real photographs",
    "landing_metric_real_note": "most scenarios use licensed field imagery",
    "landing_metric_branch": "branch accuracy",
    "landing_metric_branch_note": "the final action selected by deterministic policy",
    "landing_metric_defect": "defect macro F1",
    "landing_metric_defect_note": "across crack, delamination, hotspot and soiling",
    "landing_metric_iou": "mean IoU",
    "landing_metric_iou_note": "localisation over scenarios with a detected region",
    "landing_flow_kicker": "HOW IT WORKS",
    "landing_flow_title": "The model describes. The policy decides.",
    "landing_flow_lede": "Five perception tools produce measurements; one policy module owns every threshold.",
    "landing_flow_1_title": "Capture",
    "landing_flow_1_text": "Reject unusable images before they can contaminate memory.",
    "landing_flow_2_title": "Compare",
    "landing_flow_2_text": "Align the same asset, isolate the changed region and measure it.",
    "landing_flow_3_title": "Act",
    "landing_flow_3_text": "Record mild changes, refuse uncertain matches or ask a person to approve.",
    "landing_memory_kicker": "MEMORY",
    "landing_memory_title": "A baseline is superseded, never overwritten.",
    "landing_memory_lede": "Every asset keeps its inspections, the reference in force and the exact trace behind each result.",
    "landing_memory_current": "current baseline",
    "landing_memory_history": "complete history",
    "landing_stack_kicker": "THE SYSTEM",
    "landing_stack_title": "One inspectable pipeline, end to end.",
    "landing_stack_items": ("OpenCV 5 perception", "FastAPI application", "DynamoDB memory", "S3 images and traces", "arm64 Lambda delivery"),
    "landing_limits_title": "Honest limits",
    "landing_limits_items": ("29 evaluation scenarios are still a small sample.", "One global frame-coverage threshold does not generalise.", "A severe finding still requires a human decision."),
    "landing_final_title": "Inspect the next capture. Keep the reason.",
    "landing_final_lede": "Run the real pipeline with the bundled examples or your own image.",
    "landing_final_cta": "Start an inspection",
    "landing_scenario_1_outcome": "first_baseline",
    "landing_scenario_2_outcome": "recapture",
    "landing_scenario_3_outcome": "human_approval",
    "landing_scenario_4_outcome": "unrecognized_asset",

    "activity_title": "recent activity",
    "activity_lede": "Every run stays discoverable, including failures and outcomes that were not written to asset memory.",
    "activity_search": "Search activity",
    "activity_search_placeholder": "asset id or run id",
    "activity_status": "Status",
    "activity_all": "all statuses",
    "activity_apply": "Apply filters",
    "activity_empty": "No runs match those filters.",
    "activity_retry": "Retry run",
    "activity_open": "Open trace",

    "error_title": "Something interrupted the path",
    "error_code": "error code",
    "error_back_app": "Back to the application",
    "error_activity": "Open activity",

    "help_summary": "New here? Start with this",
    "help_what": "This is an inspection agent with a memory. You send it a photo of something "
                 "you want watched — a solar panel, a wall, a machine — and it tells "
                 "you what changed since the last time it saw that same thing.",
    "help_baseline": "The first photo of an asset becomes its baseline: the reference every "
                     "later photo is measured against. There is nothing to compare it to yet, "
                     "so the agent just files it away.",
    "help_decides": "From then on each photo ends in one of five answers: the photo is too poor "
                    "to judge, this is not the asset I remember, nothing changed, the change is "
                    "mild enough to record on its own, or the change is severe enough that a "
                    "person has to look.",
    "help_human": "That last one stops in the approval queue and nothing is written to memory "
                  "until you approve it. Every answer carries the measurement that produced it, "
                  "so you can always see why.",

    "samples_title": "no photo at hand?",
    "samples_hint": "Four captures of the same demo panel, in order. Each one lands on a "
                    "different answer. Pick one, then press inspect.",
    "sample_1_label": "1 · the reference photo",
    "sample_1_note": "nothing to compare against yet, so it becomes the baseline",
    "sample_2_label": "2 · the same panel, out of focus",
    "sample_2_note": "too soft to score — the agent asks for another photo",
    "sample_3_label": "3 · the same panel, now cracked",
    "sample_3_note": "severe enough that a person has to approve it",
    "sample_4_label": "4 · a different panel altogether",
    "sample_4_note": "too few matches — the agent refuses rather than guess",

    "queue_kicker_tech": "runs the policy would not write unattended",
    "queue_kicker_plain": "changes the agent will not record on its own",
    "approval_threshold": "approval threshold",
    "unit_severity": "severity",
    "queue_empty": "nothing awaiting approval",
    "all_settled": ", all of them settled",
    "assets_in_memory_one": "{n} asset in memory",
    "assets_in_memory_many": "{n} assets in memory",
    "awaiting_one": "{n} awaiting approval",
    "awaiting_many": "{n} awaiting approval",
    "queue_explainer_tech": "A run stops here when the severity score reaches {threshold}: nothing "
                       "is written to memory until a human approves it. Open any asset to see "
                       "the runs that already passed through, and the one capture each asset is "
                       "measured against.",
    "queue_explainer_plain": "A check stops here when the damage score reaches {threshold}: "
                             "nothing is saved until a person says yes. Open any asset to see the "
                             "checks that already went through, and the one photo each of them is "
                             "compared against.",

    "asset_kicker": "everything memory holds about this asset",
    "spark_label": "severity of every inspection, oldest first",
    "spark_caption_tail": "the dashed line is the approval threshold",
    "superseded_by": "superseded by",
    "no_history": "no history yet",
    "current_baseline": "current baseline",
    "pill_baseline": "baseline",
    "pill_inspection": "inspection",

    "hero_inspected": "inspected",
    "hero_policy_tech": Markup(
        "Every branch below was decided in <span class='mono'>services/agent/policy.py</span> "
        "from the number beside it."
    ),
    "hero_policy_plain": "Every step below was decided by a fixed rule, never a guess, and each "
                         "one shows the number that triggered it.",
    "decider_kicker": "the number that decided it",
    "in_progress": "inspection in progress",
    "trace_start_run": "start the inspection",
    "not_taken_kicker_tech": "branches not taken",
    "not_taken_kicker_plain": "what it ruled out",
    "ghost_not": "not",
    "compared_kicker": "what it compared",
    "cta_title": "Waiting on a human",
    "cta_nothing_written": "Nothing has been written to memory.",
    "raw_json": "raw json",
    "asset_history": "asset history",
    "footer_thresholds_tech": "thresholds from services/agent/policy.py",
    "footer_thresholds_plain": "every limit used here is fixed in code",
    "calls_one": "{n} tool call",
    "calls_many": "{n} tool calls",
    "thresholds_one": "{n} threshold",
    "thresholds_many": "{n} thresholds",

    "alt_baseline": "baseline in memory",
    "alt_capture": "capture under inspection",
    "fig_baseline": "baseline",
    "fig_capture": "capture",
    "warped_note_tech": Markup(
        "warped onto the baseline&rsquo;s perspective &mdash; the grey corners are outside "
        "what this photo covered"
    ),
    "warped_note_plain": Markup(
        "tilted to line up with the reference photo &mdash; the grey corners are parts this photo "
        "never covered"
    ),
    "compare_label": "Wipe between the baseline and the capture",
    "approve_write": "Approve write",
    "reject": "Reject",
    "what_it_measured": "what it measured",
    "every_number_raw": "every number, as raw json",
    "tries": "tries",

    "state_done": "done",
    "state_working": "working",
    "state_finished": "finished",
    "state_waiting": "waiting",
    "state_in_progress": "working…",
    "state_not_run": "not run",
    "no_verdict": "no verdict",
    "unknown_asset": "unknown asset",
    "trace_headline": "Inspection trace",
    "path_taken": "the path this run took",
    "path_so_far": "the path so far",
    "status_unstarted": "unstarted",
    "status_running": "running",
    "status_completed": "completed",
    "status_failed": "failed",
    "status_awaiting_approval": "awaiting approval",
    "status_approved": "approved",
    "status_rejected": "rejected",
    "chain_intact_tech": "sha256 chain intact over {n} events",
    "chain_intact_plain": "the {n} steps of this run close over each other: none was edited on "
                          "its own",
    "chain_broken_tech": "sha256 chain broken at event {at} of {n}",
    "chain_broken_plain": "step {at} of {n} was changed after it was written",

    "q_assess_quality": "Is this capture worth scoring at all?",
    "q_align_to_baseline": "Is this the same asset as the one in memory?",
    "q_diff_against_memory": "Has anything changed since the baseline — enough to be sure?",
    "q_crop_and_rescan": "Is the changed region large enough to be real?",
    "q_classify_severity": "What kind of defect, and can it be written unattended?",

    "tip_blur_variance_tech": "How sharp the capture is. Low means the photo is too soft to score.",
    "tip_blur_variance_plain": "How sharp the photo is. Low means it is too blurry to judge.",
    "tip_inlier_ratio_tech": "Share of matched keypoints that agree on one geometry. Low means this "
                        "is not the asset memory holds.",
    "tip_inlier_ratio_plain": "How much of this photo lines up with the reference one. Low means "
                              "it is not the same thing.",
    "tip_mean_delta_tech": "Average pixel difference against the baseline, inside the changed region.",
    "tip_mean_delta_plain": "How different the changed part looks from the reference photo.",
    "tip_area_ratio_tech": "How much of the frame the changed region covers.",
    "tip_area_ratio_plain": "How big the changed part is next to the whole photo.",
    "tip_zoom_area_ratio_tech": "How much of the enlarged crop the changed region covers.",
    "tip_zoom_area_ratio_plain": "How much of the zoomed-in area changed.",
    "tip_changed_ratio_tech": "Share of the aligned frame whose pixels moved at all since the "
                         "baseline.",
    "tip_changed_ratio_plain": "How much of the photo looks different from the reference at all.",
    "tip_score_tech": "Severity of the change, 0 to 1. Above the threshold nothing is written "
                 "without a human.",
    "tip_score_plain": "How bad the change is, from 0 to 1. Above the limit a person has to look "
                       "before anything is saved.",
    "tip_recapture": "The capture was not good enough to score. The agent asked for another "
                     "photo.",
    "tip_quality_ok": "The capture was sharp and well exposed enough to score.",
    "tip_retry_classic": "Modern features failed to match, so the agent retried with the "
                         "classic detector.",
    "tip_unrecognized_asset": "Too few matches to believe this is the same asset. The agent "
                              "refused rather than guess.",
    "tip_aligned": "The capture was anchored to the stored baseline of the same asset.",
    "tip_no_change": "Nothing changed enough since the baseline to be worth reporting.",
    "tip_crop_and_rescan": "The change was borderline, so the agent zoomed in and measured "
                           "again.",
    "tip_change_confirmed": "The change survived a closer look and is real.",
    "tip_human_approval": "Severe enough that nothing is written to memory until a person "
                          "approves it.",
    "tip_auto_write": "Mild enough for the agent to write to memory on its own.",
    "tip_first_baseline": "The first capture of this asset. There was nothing to compare it "
                          "against.",

    "js_confirm": "Confirm?",
    "js_arm": "Click Confirm? again to {action}, or move away to cancel.",
    "js_too_large": "image larger than 6 MB",
    "js_not_an_image": "not a decodable image",
    "js_sample_failed": "the example could not be loaded — pick a file instead",
    "js_run_start_failed": "the run could not be started",
    "js_poll_timeout": "the run did not answer in time — open activity to check it",
    "js_queue_timeout": "the queue stopped refreshing — reload the page to see it up to date",

    "err_asset_id_tech": "asset_id must match [a-z0-9-]{1,64}",
    "err_asset_id_plain": "the name can only use lowercase letters, numbers and hyphens, up to 64 "
                          "characters",
    "err_image_required": "an image file is required",
}

_ES = {
    "nav_assets": "activos",
    "nav_activity": "actividad",
    "nav_queue": "cola de aprobación",
    "nav_how": "cómo funciona",
    "nav_memory": "memoria",
    "nav_system": "sistema",
    "nav_open_app": "abrir app",
    "nav_trace": "traza",
    "title_trace": "traza de inspección",
    "theme_dark": "Oscuro",
    "theme_light": "Claro",
    "lang_label": "Idioma",
    "register_label": "Detalle",
    "views_label": "Vistas",
    "skip_to_content": "Saltar al contenido",
    "plain_name": "llano",
    "tech_name": "técnico",

    "upload_rejected": "Esa captura no fue aceptada.",
    "upload_retry": Markup(
        "Elegí el archivo otra vez &mdash; el navegador no puede guardártelo."
    ),
    "new_inspection": "nueva inspección",
    "upload_hint_tech": Markup(
        "El id del activo admite minúsculas, dígitos y guiones, hasta 64 caracteres "
        "&mdash; un id que la memoria ya tiene suma a la historia de ese activo, uno nuevo "
        "empieza la suya. JPEG o PNG, hasta 6&nbsp;MB. La traza se abre "
        "enseguida y se completa a medida que el agente trabaja."
    ),
    "upload_hint_plain": Markup(
        "Poné un nombre para la cosa que querés vigilar y mandá una foto. Usá el mismo nombre la "
        "próxima vez y esto se vuelve su historia; un nombre nuevo empieza otra. Minúsculas, "
        "números y guiones, hasta 64 caracteres, y una foto JPEG o PNG de hasta 6&nbsp;MB. El resultado se "
        "abre enseguida y se completa mientras el agente mira."
    ),
    "label_asset_id": "id del activo",
    "asset_id_placeholder": "ej. panel-a7-norte",
    "label_capture": "captura",
    "drop_hint": "o soltá una acá",
    "inspect": "inspeccionar",
    "gallery_title": "activos en memoria",
    "gallery_lede_tech": "Cada activo guarda todas las inspecciones que el agente le corrió, la "
                    "rama que tomó y el número que la decidió. Abrí uno, o "
                    "mandá una captura nueva arriba.",
    "gallery_lede_plain": "Cada cosa que vigilás guarda todas las revisiones que el agente le "
                          "hizo, qué decidió y el número detrás de esa decisión. Abrí una, o "
                          "mandá una foto nueva arriba.",
    "no_summary": "todavía sin resumen de inspección",
    "empty_gallery": "Todavía no hay nada en memoria. Mandá la primera captura arriba "
                     "y el agente va a guardar cada inspección que le corra.",
    "asset_search": "Buscar activos",
    "asset_search_placeholder": "id del activo o resultado",
    "asset_filter_all": "todos los resultados",
    "asset_filter_empty": "Ningún activo coincide con esos filtros.",

    "landing_hero_kicker": "INSPECCIÓN VISUAL · MEMORIA LONGITUDINAL",
    "landing_hero_title": "La inspección que recuerda lo que vio.",
    "landing_hero_lede": "Mandá una captura. Afterimage revisa su calidad, la alinea con el baseline, "
                         "mide el cambio y se detiene cuando tiene que decidir una persona.",
    "landing_primary_cta": "Abrir la aplicación",
    "landing_secondary_cta": "Ver cómo funciona",
    "landing_demo_kicker": "CÓMO SE RAMIFICA EL CICLO",
    "landing_demo_title": "Cuatro capturas, cuatro respuestas distintas.",
    "landing_demo_hint": "Una ilustración del recorrido de cada captura. Corré una en la aplicación "
                         "para ver los números medidos que hay detrás.",
    "landing_demo_result": "resultado",
    "landing_demo_scenario": "captura de demo",
    "landing_demo_previous": "Anterior",
    "landing_demo_pause": "Pausar",
    "landing_demo_replay": "Repetir",
    "landing_demo_next": "Siguiente",
    "landing_stage_quality": "Calidad",
    "landing_stage_align": "Alinear",
    "landing_stage_diff": "Comparar",
    "landing_stage_rescan": "Revisar",
    "landing_stage_severity": "Decidir",
    "landing_state_done": "listo",
    "landing_state_skipped": "omitido",
    "landing_state_waiting": "esperando",
    "landing_state_stopped": "se detuvo acá",
    "landing_metrics_label": "Medido sobre la evaluación reproducible",
    "landing_metric_real": "fotografías reales",
    "landing_metric_real_note": "la mayoría de los escenarios usa imágenes de campo con licencia",
    "landing_metric_branch": "exactitud de rama",
    "landing_metric_branch_note": "la acción final elegida por la política determinista",
    "landing_metric_defect": "F1 macro de defecto",
    "landing_metric_defect_note": "entre fisura, delaminación, hotspot y suciedad",
    "landing_metric_iou": "IoU promedio",
    "landing_metric_iou_note": "localización sobre escenarios con una región detectada",
    "landing_flow_kicker": "CÓMO FUNCIONA",
    "landing_flow_title": "El modelo redacta. La política decide.",
    "landing_flow_lede": "Cinco herramientas producen mediciones; un único módulo concentra todos los umbrales.",
    "landing_flow_1_title": "Capturar",
    "landing_flow_1_text": "Descarta imágenes inútiles antes de que contaminen la memoria.",
    "landing_flow_2_title": "Comparar",
    "landing_flow_2_text": "Alinea el mismo activo, aísla la región cambiada y la mide.",
    "landing_flow_3_title": "Actuar",
    "landing_flow_3_text": "Guarda cambios leves, rechaza coincidencias dudosas o pide aprobación humana.",
    "landing_memory_kicker": "MEMORIA",
    "landing_memory_title": "Un baseline se reemplaza, nunca se pisa.",
    "landing_memory_lede": "Cada activo conserva sus inspecciones, la referencia vigente y la traza exacta detrás de cada resultado.",
    "landing_memory_current": "baseline vigente",
    "landing_memory_history": "historial completo",
    "landing_stack_kicker": "EL SISTEMA",
    "landing_stack_title": "Un pipeline inspeccionable de punta a punta.",
    "landing_stack_items": ("Percepción con OpenCV 5", "Aplicación FastAPI", "Memoria en DynamoDB", "Imágenes y trazas en S3", "Despliegue Lambda arm64"),
    "landing_limits_title": "Límites honestos",
    "landing_limits_items": ("29 escenarios de evaluación siguen siendo una muestra pequeña.", "Un único umbral de cobertura no generaliza.", "Un hallazgo grave todavía requiere una decisión humana."),
    "landing_final_title": "Inspeccioná la próxima captura. Conservá el porqué.",
    "landing_final_lede": "Corré el pipeline real con los ejemplos incluidos o con tu propia imagen.",
    "landing_final_cta": "Iniciar una inspección",
    "landing_scenario_1_outcome": "first_baseline",
    "landing_scenario_2_outcome": "recapture",
    "landing_scenario_3_outcome": "human_approval",
    "landing_scenario_4_outcome": "unrecognized_asset",

    "activity_title": "actividad reciente",
    "activity_lede": "Cada corrida sigue siendo visible, incluso fallos y resultados que no se escribieron en la memoria del activo.",
    "activity_search": "Buscar actividad",
    "activity_search_placeholder": "id del activo o de la corrida",
    "activity_status": "Estado",
    "activity_all": "todos los estados",
    "activity_apply": "Aplicar filtros",
    "activity_empty": "Ninguna corrida coincide con esos filtros.",
    "activity_retry": "Reintentar corrida",
    "activity_open": "Abrir traza",

    "error_title": "Algo interrumpió el recorrido",
    "error_code": "código de error",
    "error_back_app": "Volver a la aplicación",
    "error_activity": "Abrir actividad",

    "help_summary": "¿Primera vez? Empezá por acá",
    "help_what": "Esto es un agente de inspección con memoria. Le mandás una foto de "
                 "algo que querés vigilar — un panel solar, una pared, una "
                 "máquina — y te dice qué cambió desde la última vez "
                 "que vio esa misma cosa.",
    "help_baseline": "La primera foto de un activo pasa a ser su baseline: la referencia contra "
                     "la que se mide cada foto posterior. Todavía no hay con qué "
                     "compararla, así que el agente simplemente la guarda.",
    "help_decides": "De ahí en más cada foto termina en una de cinco respuestas: la "
                    "foto es demasiado mala para juzgarla, este no es el activo que recuerdo, "
                    "no cambió nada, el cambio es leve y lo anoto solo, o el cambio es "
                    "grave y lo tiene que mirar una persona.",
    "help_human": "Esa última frena en la cola de aprobación y no se escribe nada en "
                  "memoria hasta que vos la apruebes. Cada respuesta viene con la medición "
                  "que la produjo, así siempre podés ver por qué.",

    "samples_title": "¿no tenés una foto a mano?",
    "samples_hint": "Cuatro capturas del mismo panel de demo, en orden. Cada una cae en una "
                    "respuesta distinta. Elegí una y apretá inspeccionar.",
    "sample_1_label": "1 · la foto de referencia",
    "sample_1_note": "todavía no hay con qué comparar, así que pasa a ser el "
                     "baseline",
    "sample_2_label": "2 · el mismo panel, fuera de foco",
    "sample_2_note": "demasiado borrosa para puntuar — el agente pide otra foto",
    "sample_3_label": "3 · el mismo panel, ahora con una fisura",
    "sample_3_note": "grave como para que lo apruebe una persona",
    "sample_4_label": "4 · otro panel completamente distinto",
    "sample_4_note": "muy pocas coincidencias — el agente se niega en vez de adivinar",

    "queue_kicker_tech": "corridas que la política no escribiría sin supervisión",
    "queue_kicker_plain": "cambios que el agente no va a anotar por su cuenta",
    "approval_threshold": "umbral de aprobación",
    "unit_severity": "severidad",
    "queue_empty": "no hay nada esperando aprobación",
    "all_settled": ", todos resueltos",
    "assets_in_memory_one": "{n} activo en memoria",
    "assets_in_memory_many": "{n} activos en memoria",
    "awaiting_one": "{n} esperando aprobación",
    "awaiting_many": "{n} esperando aprobación",
    "queue_explainer_tech": "Una corrida frena acá cuando el puntaje de severidad llega a "
                       "{threshold}: no se escribe nada en memoria hasta que una persona lo "
                       "apruebe. Abrí cualquier activo para ver las corridas que ya "
                       "pasaron, y la única captura contra la que se mide cada activo.",
    "queue_explainer_plain": "Una revisión frena acá cuando el puntaje de daño llega a "
                             "{threshold}: no se guarda nada hasta que una persona diga que sí. "
                             "Abrí cualquier activo para ver las revisiones que ya pasaron, y la "
                             "única foto contra la que se compara cada uno.",

    "asset_kicker": "todo lo que la memoria guarda de este activo",
    "spark_label": "severidad de cada inspección, de la más vieja a la más nueva",
    "spark_caption_tail": "la línea punteada es el umbral de aprobación",
    "superseded_by": "reemplazado por",
    "no_history": "todavía sin historia",
    "current_baseline": "baseline en vigencia",
    "pill_baseline": "baseline",
    "pill_inspection": "inspección",

    "hero_inspected": "inspeccionado",
    "hero_policy_tech": Markup(
        "Cada rama de abajo se decidió en <span class='mono'>services/agent/policy.py</span> "
        "a partir del número que tiene al lado."
    ),
    "hero_policy_plain": "Cada paso de abajo lo decidió una regla fija, nunca una corazonada, y "
                         "cada uno muestra el número que lo disparó.",
    "decider_kicker": "el número que lo decidió",
    "in_progress": "inspección en curso",
    "trace_start_run": "iniciar la inspección",
    "not_taken_kicker_tech": "ramas no tomadas",
    "not_taken_kicker_plain": "qué descartó",
    "ghost_not": "no",
    "compared_kicker": "qué comparó",
    "cta_title": "Esperando a una persona",
    "cta_nothing_written": "No se escribió nada en memoria.",
    "raw_json": "json crudo",
    "asset_history": "historia del activo",
    "footer_thresholds_tech": "umbrales de services/agent/policy.py",
    "footer_thresholds_plain": "todos los límites que se usan acá están fijos en el código",
    "calls_one": "{n} llamada a herramienta",
    "calls_many": "{n} llamadas a herramientas",
    "thresholds_one": "{n} umbral",
    "thresholds_many": "{n} umbrales",

    "alt_baseline": "baseline en memoria",
    "alt_capture": "captura bajo inspección",
    "fig_baseline": "baseline",
    "fig_capture": "captura",
    "warped_note_tech": Markup(
        "deformada a la perspectiva del baseline &mdash; las esquinas grises quedan fuera de "
        "lo que cubría esta foto"
    ),
    "warped_note_plain": Markup(
        "inclinada para que coincida con la foto de referencia &mdash; las esquinas grises son "
        "partes que esta foto nunca cubrió"
    ),
    "compare_label": "Desplazá entre el baseline y la captura",
    "approve_write": "Aprobar escritura",
    "reject": "Rechazar",
    "what_it_measured": "qué midió",
    "every_number_raw": "todos los números, en json crudo",
    "tries": "intentos",

    "state_done": "listo",
    "state_working": "trabajando",
    "state_finished": "terminado",
    "state_waiting": "en espera",
    "state_in_progress": "trabajando…",
    "state_not_run": "no corrió",
    "no_verdict": "sin veredicto",
    "unknown_asset": "activo desconocido",
    "trace_headline": "Traza de inspección",
    "path_taken": "el camino que tomó esta corrida",
    "path_so_far": "el camino hasta acá",
    "status_unstarted": "sin iniciar",
    "status_running": "en curso",
    "status_completed": "completada",
    "status_failed": "fallida",
    "status_awaiting_approval": "esperando aprobación",
    "status_approved": "aprobada",
    "status_rejected": "rechazada",
    "chain_intact_tech": "cadena sha256 intacta sobre {n} eventos",
    "chain_intact_plain": "los {n} pasos de esta corrida cierran entre sí: ninguno se editó por "
                          "separado",
    "chain_broken_tech": "cadena sha256 rota en el evento {at} de {n}",
    "chain_broken_plain": "el paso {at} de {n} se cambió después de escribirse",

    "q_assess_quality": "¿Esta captura vale la pena puntuarla siquiera?",
    "q_align_to_baseline": "¿Es este el mismo activo que el que tiene la memoria?",
    "q_diff_against_memory": "¿Cambió algo desde el baseline — lo suficiente "
                             "como para estar seguro?",
    "q_crop_and_rescan": "¿La región que cambió es lo bastante grande como para "
                         "ser real?",
    "q_classify_severity": "¿Qué tipo de defecto es, y se puede escribir sin "
                           "supervisión?",

    "tip_blur_variance_tech": "Qué tan nítida es la captura. Bajo significa que la foto "
                         "está demasiado blanda para puntuarla.",
    "tip_blur_variance_plain": "Qué tan nítida es la foto. Bajo significa que está demasiado "
                               "borrosa para juzgarla.",
    "tip_inlier_ratio_tech": "Proporción de puntos clave emparejados que coinciden en una sola "
                        "geometría. Bajo significa que este no es el activo que tiene la "
                        "memoria.",
    "tip_inlier_ratio_plain": "Cuánto de esta foto coincide con la de referencia. Bajo significa "
                              "que no es la misma cosa.",
    "tip_mean_delta_tech": "Diferencia promedio de píxeles contra el baseline, dentro de la "
                      "región que cambió.",
    "tip_mean_delta_plain": "Qué tan distinta se ve la parte que cambió respecto de la foto de "
                            "referencia.",
    "tip_area_ratio_tech": "Cuánto del cuadro ocupa la región que cambió.",
    "tip_area_ratio_plain": "Qué tan grande es la parte que cambió al lado de toda la foto.",
    "tip_zoom_area_ratio_tech": "Cuánto del recorte ampliado ocupa la región que cambió.",
    "tip_zoom_area_ratio_plain": "Qué tanto cambió dentro del área ampliada.",
    "tip_changed_ratio_tech": "Proporción del cuadro alineado cuyos píxeles se movieron "
                         "algo desde el baseline.",
    "tip_changed_ratio_plain": "Cuánto de la foto se ve distinto de la referencia, aunque sea un "
                               "poco.",
    "tip_score_tech": "Severidad del cambio, de 0 a 1. Por encima del umbral no se escribe nada sin "
                 "una persona.",
    "tip_score_plain": "Qué tan grave es el cambio, de 0 a 1. Por encima del límite tiene que "
                       "mirarlo una persona antes de guardar nada.",
    "tip_recapture": "La captura no era lo bastante buena para puntuarla. El agente pidió "
                     "otra foto.",
    "tip_quality_ok": "La captura estaba lo bastante nítida y bien expuesta para puntuarla.",
    "tip_retry_classic": "Las features modernas no lograron emparejar, así que el agente "
                         "reintentó con el detector clásico.",
    "tip_unrecognized_asset": "Muy pocas coincidencias para creer que es el mismo activo. El "
                              "agente se negó en vez de adivinar.",
    "tip_aligned": "La captura quedó anclada al baseline guardado del mismo activo.",
    "tip_no_change": "Nada cambió lo suficiente desde el baseline como para reportarlo.",
    "tip_crop_and_rescan": "El cambio estaba en el límite, así que el agente se "
                           "acercó y midió de nuevo.",
    "tip_change_confirmed": "El cambio sobrevivió a una mirada más cercana y es real.",
    "tip_human_approval": "Lo bastante grave como para que no se escriba nada en memoria hasta "
                          "que una persona lo apruebe.",
    "tip_auto_write": "Lo bastante leve como para que el agente lo escriba en memoria por su "
                      "cuenta.",
    "tip_first_baseline": "La primera captura de este activo. No había nada contra "
                          "qué compararla.",

    "js_confirm": "¿Confirmar?",
    "js_arm": "Apretá ¿Confirmar? de nuevo para {action}, o salí del botón "
              "para cancelar.",
    "js_too_large": "imagen de más de 6 MB",
    "js_not_an_image": "no es una imagen decodificable",
    "js_sample_failed": "no se pudo cargar el ejemplo — elegí un archivo",
    "js_run_start_failed": "no se pudo iniciar la corrida",
    "js_poll_timeout": "la corrida no respondió a tiempo — abrí actividad para revisarla",
    "js_queue_timeout": "la cola dejó de actualizarse — recargá la página para verla al día",

    "err_asset_id_tech": "el id del activo tiene que coincidir con [a-z0-9-]{1,64}",
    "err_asset_id_plain": "el nombre solo admite minúsculas, números y guiones, hasta 64 "
                          "caracteres",
    "err_image_required": "hace falta un archivo de imagen",
}

TEXT = {"en": _EN, "es": _ES}


class Copy(dict):
    def __missing__(self, key):
        raise RuntimeError(f"no copy for {key!r}")


@lru_cache(maxsize=len(LANGS) * len(REGISTERS))
def strings(lang: str = DEFAULT_LANG, register: str = DEFAULT_REGISTER) -> Copy:
    table = _EN | TEXT.get(lang, {})
    kind = register if register in REGISTERS else DEFAULT_REGISTER
    voiced = Copy((key, value) for key, value in table.items()
                  if not key.endswith(("_tech", "_plain")))
    voiced.update({key.rsplit("_", 1)[0]: value for key, value in table.items()
                   if key.endswith(f"_{kind}")})
    return voiced


def months(lang: str = DEFAULT_LANG) -> tuple[str, ...]:
    return MONTHS.get(lang, MONTHS[DEFAULT_LANG])


def counted(t: dict, key: str, n: int, **extra) -> str:
    return t[f"{key}_one" if n == 1 else f"{key}_many"].format(n=n, **extra)
