# Delivery status — OpenCV AI Competition 2026

Submissions close **2026-10-26 23:45 -07:00** (2026-10-27 03:45 -03:00). Judging runs 2026-10-27
00:00 -07:00 → 2026-11-09 23:45 -08:00; winners are announced 2026-11-10 09:00 -08:00. Event:
<https://opencv26.devpost.com/> · Entry: <https://devpost.com/software/afterimage-ibp376>.

The product is complete (U1–U20 of [PLAN.md](PLAN.md) done): 380 tests green at 92.62% coverage
(`make test`, 2026-10-05), the video re-recorded and the entry refreshed on 4 October.

## Surfaces

Each one checked from outside, without a session.

| Surface | Where | State | Checked |
|---|---|---|---|
| Repo and CI | `gmassello/afterimage`, `main` | clean and in sync with `origin`; `ci` and Pages green; `ci` runs on pushes to `main` and on pull requests | 2026-10-05 |
| Site | https://jgmzrkpa344jwixw7nbulgh2ju0mojcb.lambda-url.us-east-1.on.aws/ | serves `f6176fe` (deploy run 37247899968; later commits are docs only); `/`, `/app`, `/activity`, `/queue`, `/health` and the 55 assets of `/` and `/app` answer 200; calibration `aligned` at 0.9975 | 2026-10-05 |
| Field manual | https://gmassello.github.io/afterimage/ | serves the content of `main` | 2026-10-05 |
| Devpost entry | https://devpost.com/software/afterimage-ibp376 | `SUBMITTED`; text of [submission.md](submission.md), six current captures, 14 tags, video `_fJo29SdoaU` on the project and on the submission, testing instructions walking the sample sets | 2026-10-05 |
| Gallery card | https://opencv26.devpost.com/project-gallery | not accessible: Devpost does not publish the gallery while the contest is open | 2026-10-05 |
| Video | https://youtu.be/_fJo29SdoaU (3:06.6, public) | same ID in README, entry, deck and field manual; rendered after `results.json`; every four-decimal figure in its captions is in `results.json` or on screen in the take | 2026-10-05 |
| Deck | [deck.pdf](deck.pdf) (not required by the event) | the published PDF matches the repository copy and links the current video | 2026-10-05 |

## Known limits

Published in [EVALUATION.md](EVALUATION.md) and the entry: the effectiveness figures apply to the
committed dataset, not to field accuracy; five scenarios fail, each with its root cause; the
trace's hash chain is not a signed audit log; the public endpoint has no login; there is no
external figure for the cost of a manual inspection, only the measured $0.0005 per run.

## Do not break on return

- Do not recreate `SUBMISSION.md`: on macOS that name overwrites `docs/submission.md`.
- `app.css` must start with the CSS block of [DESIGN.md](DESIGN.md) §3; a new token goes in both
  (`test_the_stylesheet_carries_the_design_system_tokens_verbatim`).
- Evaluation figures change only through `make eval`; `test_published_numbers` and the CI `eval`
  job fail on hand-written numbers.
- `make test` and `make dev` need the Docker daemon (`colima start`); `make test` stops the dev
  server when it finishes.

## Outside our control

Risks, not tasks, each with its fallback.

- **The endpoint stays up through judging (27 Oct → 9 Nov)** — the `Uptime` workflow probes
  `/health` calibration and the landing title every six hours and a failed run is the alarm;
  fallback: a live screen-share, which the rules accept.
- **The video stays public** — fallback: upload the same render to a second host and list both.
- **Edits after 26 Oct 23:45 PDT do not reach the judges** — the entry is already submitted.
- **Zoom check-in 7–14 Oct, only with a compute grant** — no fallback; confirm whether it applies.
