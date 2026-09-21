from services.agent import policy
from services.agent.loop import WRONG_TOOL
from services.agent.scripted import PolicyFollowingLLM

CAPTURE = "assets/panel/insp1/capture.png"
BASELINE = "assets/panel/insp0/capture.png"
ALIGNED = "assets/panel/insp1/aligned.png"
VALID_MASK = "assets/panel/insp1/valid_mask.png"


def driver():
    return PolicyFollowingLLM(CAPTURE, BASELINE, "neural")


def tool_turn(*responses):
    return {"role": "tool", "responses": list(responses)}


def only_call(turn):
    assert len(turn.calls) == 1
    return turn.calls[0]


def test_an_error_response_replays_the_call_the_last_verdict_mandates():
    verdict = policy.decision("blur_variance", 300.0, 100.0, policy.QUALITY_OK)
    history = [
        {"role": "user", "text": "inspect panel"},
        tool_turn(("assess_quality", {"metrics": {}, "policy": verdict})),
        tool_turn(("submit", {"error": WRONG_TOOL.format(expected="align_to_baseline")})),
    ]
    call = only_call(driver().generate("", history, []))
    assert call.name == "align_to_baseline"
    assert call.args["image_key"] == CAPTURE
    assert call.args["baseline_key"] == BASELINE


def test_the_diff_call_reuses_the_keys_of_the_alignment_payload():
    verdict = policy.decision("inlier_ratio", 0.8, 0.3, policy.ALIGNED)
    history = [tool_turn(("align_to_baseline", {
        "metrics": {"aligned_key": ALIGNED, "valid_mask_key": VALID_MASK},
        "policy": verdict,
    }))]
    call = only_call(driver().generate("", history, []))
    assert call.name == "diff_against_memory"
    assert call.args["aligned_key"] == ALIGNED
    assert call.args["valid_mask_key"] == VALID_MASK


def test_an_empty_history_starts_with_the_quality_gate():
    call = only_call(driver().generate("", [], []))
    assert call.name == "assess_quality"
    assert call.args["image_key"] == CAPTURE
