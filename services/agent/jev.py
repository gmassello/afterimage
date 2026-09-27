import os

import httpx

ENDPOINT = "https://ai-gateway.vercel.sh/v1/evaluate"
MODEL = "typesafe-ai/jev"
PROVIDER = "typesafe-ai"
TIMEOUT_S = 2.0

OVERSTATES = "overstates"
OVERSTATES_INSTRUCTIONS = (
    "The state is a message an inspection agent wrote for an operator, followed by the verdict the "
    "inspection policy computed in code. Does the message claim something the verdict does not "
    "support? That covers a more severe finding than the verdict, a different outcome than its "
    "branch, a defect where the verdict found no change, or certainty the numbers do not give."
)
OVERSTATES_CRITERIA = {
    "true": (
        "the message states a finding, severity, outcome or certainty that goes beyond the branch "
        "and the number in the verdict"
    ),
    "false": (
        "the message restates the verdict in plain words, or says less than it, without adding a "
        "finding, a severity or an outcome the verdict does not carry"
    ),
}

CAPTURE_ARTEFACT = "capture_artefact"
CAPTURE_ARTEFACT_INSTRUCTIONS = (
    "The state is the reason a human reviewer gave for rejecting a change an inspection agent found "
    "on a solar panel photo. Does the reviewer attribute the finding to how the photo was taken - "
    "glare, reflection, shadow, lighting, framing, focus, dirt on the lens - rather than to a real "
    "change in the panel itself?"
)
CAPTURE_ARTEFACT_CRITERIA = {
    "true": (
        "the reviewer says the finding comes from the capture: glare, reflection, shadow, lighting, "
        "framing, focus or something on the lens"
    ),
    "false": (
        "anything else: the reviewer disputes the defect class or its severity, says the change is "
        "real but acceptable, gives no reason, or blames something on the panel itself"
    ),
}

# ponytail: what crosses the boundary is one operator-facing sentence or one reviewer sentence,
# never an image or an asset id, and the request pins the provider that may serve it. Zero data
# retention is a paid gateway tier that answers 403 on every call otherwise, so it is a knob that
# defaults off; a BYOK key is the upgrade if more than one sentence per decision ever leaves.


def configured() -> bool:
    return bool(os.environ.get("AI_GATEWAY_API_KEY"))


def payload(state: str, key: str, instructions: str, criteria: dict) -> dict:
    gateway: dict = {"only": [PROVIDER]}
    if os.environ.get("AFTERIMAGE_JEV_ZERO_RETENTION") == "1":
        gateway["zeroDataRetention"] = True
    return {
        "model": MODEL,
        "state": state,
        "questions": {key: {"type": "boolean", "instructions": instructions, "criteria": criteria}},
        "providerOptions": {"gateway": gateway},
    }


def ask(state: str, key: str, instructions: str, criteria: dict) -> tuple[float | None, str | None]:
    # ponytail: any failure is a None and the caller carries on as if the key were unset - no retry,
    # because a second attempt is a second stall inside the request and the answer only ever adds a
    # check. The reason comes back with it so the trace shows a 403 instead of a silent skip.
    api_key = os.environ.get("AI_GATEWAY_API_KEY")
    if not api_key:
        return None, None
    try:
        response = httpx.post(
            ENDPOINT,
            json=payload(state, key, instructions, criteria),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=TIMEOUT_S,
        )
        response.raise_for_status()
        probability = response.json()["answers"][key]["probability"]
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
        return None, repr(error)
    if not isinstance(probability, int | float) or not 0.0 <= probability <= 1.0:
        return None, f"probability out of range: {probability!r}"
    return float(probability), None


def overstates(message: str, verdict: dict) -> tuple[float | None, str | None]:
    state = (
        f"Message: {message}\nVerdict: branch {verdict['branch']}, "
        f"{verdict['input_metric']} {verdict['value']} against threshold {verdict['threshold']}."
    )
    return ask(state, OVERSTATES, OVERSTATES_INSTRUCTIONS, OVERSTATES_CRITERIA)


def capture_artefact(reason: str) -> tuple[float | None, str | None]:
    return ask(reason, CAPTURE_ARTEFACT, CAPTURE_ARTEFACT_INSTRUCTIONS, CAPTURE_ARTEFACT_CRITERIA)
