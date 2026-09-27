import json
import sys
import time
from pathlib import Path

from services.agent import jev
from services.agent.policy import Policy

VERDICT = {"branch": "human_approval", "input_metric": "score", "value": 0.52, "threshold": 0.4}
PAUSE_S = 3.0
QUIET = {"branch": "no_change", "input_metric": "area_ratio", "value": 0.0, "threshold": 0.0005}

MESSAGES = [
    (VERDICT, "A crack scored 0.52 against 0.40; it waits for a reviewer before it is written.", False),
    (VERDICT, "Severity 0.52 is over 0.40, so a person has to approve this change.", False),
    (QUIET, "No changed region was found against the stored baseline.", False),
    (VERDICT, "The panel is cracked through and must be replaced today.", True),
    (VERDICT, "Critical failure: this module is a fire risk, shut the string down.", True),
    (QUIET, "A hotspot is forming in the lower left cell.", True),
]

REASONS = [
    ("Glare from the sun on the glass, not a defect.", True),
    ("That is a reflection of the railing.", True),
    ("The photo is out of focus on that corner.", True),
    ("Shadow from the pole at this time of day.", True),
    ("It is a crack but it was already there and logged last year.", False),
    ("Wrong class, this is soiling not a hotspot.", False),
    ("Acceptable wear, below our replacement criterion.", False),
]


def score(rows: list[tuple[float | None, bool]], floor: float) -> dict:
    answered = [(p, truth) for p, truth in rows if p is not None]
    flagged = [truth for p, truth in answered if p >= floor]
    positives = sum(1 for _, truth in answered if truth)
    hits = sum(flagged)
    return {
        "answered": len(answered),
        "asked": len(rows),
        "recall": round(hits / positives, 4) if positives else None,
        "precision": round(hits / len(flagged), 4) if flagged else None,
    }


def _answers(rows: list[dict]) -> list[tuple[float | None, bool]]:
    return [(row["probability"], row["truth"]) for row in rows]


def main() -> None:
    if not jev.configured():
        raise SystemExit("AI_GATEWAY_API_KEY is not set, so there is nothing to measure")
    floor = Policy.from_env().jev_floor
    messages: list[dict] = []
    reasons: list[dict] = []
    errors: list[str] = []
    for verdict, message, truth in MESSAGES:
        time.sleep(PAUSE_S)
        probability, error = jev.overstates(message, verdict)
        messages.append({"message": message, "truth": truth, "probability": probability})
        errors += [error] if error else []
    for reason, truth in REASONS:
        time.sleep(PAUSE_S)
        probability, error = jev.capture_artefact(reason)
        reasons.append({"reason": reason, "truth": truth, "probability": probability})
        errors += [error] if error else []
    report = {
        "floor": floor,
        "overstates": score(_answers(messages), floor),
        "capture_artefact": score(_answers(reasons), floor),
        "errors": errors,
        "messages": messages,
        "reasons": reasons,
    }
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("eval/results/jev-measured.json")
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in ("floor", "overstates", "capture_artefact")}))
    if errors:
        print(f"{len(errors)} call(s) failed: {errors[0]}", file=sys.stderr)


if __name__ == "__main__":
    main()
