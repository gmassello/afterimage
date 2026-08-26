import asyncio
import json
import os
import uuid

import pytest

from services.agent import hitl, loop
from services.agent.llm import ToolCall, Turn
from services.agent.policy import Policy
from services.agent.scripted import PolicyFollowingLLM, ScriptedLLM, seed_baseline
from services.memory import images, store
from services.observability import trace
from services.perception import alignment, weights
from services.perception.tests.panels import (
    blurred,
    shifted,
    solar_panel,
    with_crack,
    with_faint_spot,
)

localstack = pytest.mark.skipif(
    "AWS_ENDPOINT_URL" not in os.environ, reason="requires LocalStack"
)

PANEL = solar_panel(seed=0)


def unique(name):
    return f"{name}-{uuid.uuid4().hex[:6]}"


def seed_asset(asset_id, baseline_image):
    return seed_baseline(asset_id, baseline_image, "insp0")


def upload_capture(asset_id, image):
    return images.put_image(asset_id, "insp1", "capture", image)


def detector():
    return alignment.default_detector()


def run_loop(asset_id, capture_key, llm, tmp_path, **kwargs):
    return asyncio.run(
        loop.run(asset_id, capture_key, llm, policy=Policy(), runs_dir=tmp_path, **kwargs)
    )


def decisions_on_disk(result):
    return json.loads((result.run_dir / "decisions.json").read_text())


@localstack
def test_blurred_capture_ends_in_recapture(tmp_path):
    asset = unique("loop-recapture")
    baseline_key = seed_asset(asset, PANEL)
    capture_key = upload_capture(asset, blurred(PANEL))
    llm = PolicyFollowingLLM(capture_key, baseline_key, detector())
    result = run_loop(asset, capture_key, llm, tmp_path)
    assert result.status == "completed"
    assert result.branch == "recapture"
    blur = next(d for d in result.decisions if d["input_metric"] == "blur_variance")
    assert blur["value"] < blur["threshold"]
    assert blur["branch"] == "recapture"
    assert decisions_on_disk(result) == result.decisions


@localstack
def test_unknown_panel_retries_then_unrecognized(tmp_path):
    if not weights.neural_weights_available():
        pytest.skip("requires ALIKED weights for the retry branch")
    asset = unique("loop-unrecognized")
    baseline_key = seed_asset(asset, PANEL)
    capture_key = upload_capture(asset, solar_panel(seed=99, rows=4, cols=7, cell=80))
    llm = PolicyFollowingLLM(capture_key, baseline_key, alignment.NEURAL)
    result = run_loop(asset, capture_key, llm, tmp_path)
    assert result.status == "completed"
    assert result.branch == "unrecognized_asset"
    alignments = [d for d in result.decisions if d["input_metric"] == "inlier_ratio"]
    assert [d["branch"] for d in alignments] == ["retry_classic", "unrecognized_asset"]
    policy = Policy()
    assert alignments[0]["threshold"] == policy.inlier_ratio_min_neural
    assert alignments[1]["threshold"] == policy.inlier_ratio_min_classic

    events = trace.read_events(result.run_dir)
    assert events[0]["type"] == "run_started"
    assert events[0]["run_id"] == result.run_id
    assert events[-1]["type"] == "run_finished"
    assert events[-1]["branch"] == "unrecognized_asset"
    assert [e["ts"] for e in events] == sorted(e["ts"] for e in events)
    spans = [e for e in events if e["type"] == "tool_call"]
    assert len(spans) == 3
    for span in spans:
        assert span["args"]
        assert span["metrics"]
        assert span["duration_ms"] >= 0
    assert spans[-1]["policy"] == alignments[1]


@localstack
def test_faint_change_zooms_then_auto_writes(tmp_path):
    asset = unique("loop-rescan")
    baseline_key = seed_asset(asset, PANEL)
    capture_key = upload_capture(asset, shifted(with_faint_spot(PANEL, 3, 7)))
    llm = PolicyFollowingLLM(capture_key, baseline_key, detector())
    result = run_loop(asset, capture_key, llm, tmp_path)
    assert result.status == "completed"
    assert result.branch == "auto_write"
    rescan = next(d for d in result.decisions if d["branch"] == "crop_and_rescan")
    assert rescan["input_metric"] == "mean_delta"
    assert rescan["value"] < rescan["threshold"]
    assert rescan["extra"]["bbox"]
    confirmed = next(d for d in result.decisions if d["input_metric"] == "area_ratio")
    assert confirmed["branch"] == "change_confirmed"
    assert store.current_baseline(asset)["inspection_id"] == result.run_id


@localstack
def test_severe_change_awaits_human_and_resolve_writes(tmp_path):
    asset = unique("loop-hitl-approve")
    baseline_key = seed_asset(asset, PANEL)
    capture_key = upload_capture(asset, shifted(with_crack(PANEL, 2, 4)))
    llm = PolicyFollowingLLM(capture_key, baseline_key, detector())
    result = run_loop(asset, capture_key, llm, tmp_path)
    assert result.status == "awaiting_approval"
    assert result.branch == "human_approval"
    assert (result.run_dir / "pending.json").exists()
    severity = next(d for d in result.decisions if d["input_metric"] == "score")
    assert severity["value"] >= severity["threshold"]
    assert store.current_baseline(asset)["inspection_id"] == "insp0"

    hitl.resolve(result.run_dir, approved=True)
    assert store.current_baseline(asset)["inspection_id"] == result.run_id
    assert not (result.run_dir / "pending.json").exists()
    assert decisions_on_disk(result)[-1]["branch"] == "approved"

    events = trace.read_events(result.run_dir)
    assert any(e["type"] == "approval_requested" for e in events)
    assert events[-1]["type"] == "decision"
    assert events[-1]["input_metric"] == "human_approved"
    assert events[-1]["branch"] == "approved"


@localstack
def test_rejection_leaves_the_baseline_untouched(tmp_path):
    asset = unique("loop-hitl-reject")
    baseline_key = seed_asset(asset, PANEL)
    capture_key = upload_capture(asset, shifted(with_crack(PANEL, 2, 4)))
    llm = PolicyFollowingLLM(capture_key, baseline_key, detector())
    result = run_loop(asset, capture_key, llm, tmp_path)
    assert result.status == "awaiting_approval"

    hitl.resolve(result.run_dir, approved=False)
    assert store.current_baseline(asset)["inspection_id"] == "insp0"
    assert decisions_on_disk(result)[-1]["branch"] == "rejected"


@localstack
def test_first_capture_becomes_the_baseline(tmp_path):
    asset = unique("loop-first-baseline")
    capture_key = upload_capture(asset, PANEL)
    result = run_loop(asset, capture_key, ScriptedLLM([]), tmp_path)
    assert result.status == "completed"
    assert result.branch == "first_baseline"
    assert result.decisions[0]["input_metric"] == "baseline_exists"
    assert store.current_baseline(asset)["inspection_id"] == result.run_id


@localstack
def test_premature_submit_is_discarded(tmp_path):
    asset = unique("loop-premature")
    seed_asset(asset, PANEL)
    capture_key = upload_capture(asset, blurred(PANEL))
    llm = ScriptedLLM([
        Turn(calls=(
            ToolCall("assess_quality", {"image_key": capture_key}),
            ToolCall("submit", {"branch": "recapture", "message": "too early"}),
        )),
        Turn(calls=(ToolCall("submit", {"branch": "recapture", "message": "retake closer"}),)),
    ])
    result = run_loop(asset, capture_key, llm, tmp_path)
    assert result.status == "completed"
    assert result.branch == "recapture"
    assert not llm.turns


@localstack
def test_submit_with_wrong_branch_is_rejected(tmp_path):
    asset = unique("loop-wrong-branch")
    seed_asset(asset, PANEL)
    capture_key = upload_capture(asset, blurred(PANEL))
    llm = ScriptedLLM([
        Turn(calls=(ToolCall("assess_quality", {"image_key": capture_key}),)),
        Turn(calls=(ToolCall("submit", {"branch": "auto_write", "message": "looks fine"}),)),
        Turn(calls=(ToolCall("submit", {"branch": "recapture", "message": "retake closer"}),)),
    ])
    result = run_loop(asset, capture_key, llm, tmp_path)
    assert result.status == "completed"
    assert result.branch == "recapture"
    assert not llm.turns


@localstack
def test_never_submitting_fails_the_run(tmp_path):
    asset = unique("loop-no-submit")
    seed_asset(asset, PANEL)
    capture_key = upload_capture(asset, PANEL)
    llm = ScriptedLLM([Turn(text="thinking..."), Turn(text="still thinking"), Turn(text="hmm")])
    result = run_loop(asset, capture_key, llm, tmp_path, max_turns=3)
    assert result.status == "failed"
    assert result.branch is None
