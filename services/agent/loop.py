import asyncio
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from services.agent import hitl
from services.agent import policy as policy_module
from services.agent.llm import GeminiLLM
from services.agent.policy import Policy
from services.agent.scripted import PolicyFollowingLLM
from services.memory import runs, store
from services.observability import trace
from services.perception import alignment

SYSTEM = (
    "You are a visual inspection agent for solar panels with longitudinal memory. "
    "Inspect the capture by calling the perception tools in order: assess_quality, "
    "align_to_baseline, diff_against_memory, crop_and_rescan only when mandated, "
    "classify_severity. Every tool result carries a 'policy' verdict computed in code "
    "from calibrated thresholds; you MUST follow its 'branch' - your judgment covers "
    "phrasing the operator-facing message and passing the right arguments, never "
    "overriding a verdict. When the verdict is terminal, call submit with that exact "
    "branch and one concrete sentence for the operator (e.g. recapture guidance built "
    "from the failing metric). Never fabricate metrics; only tool results count."
)

SUBMIT = "submit"
SUBMIT_TOOL = {
    "name": SUBMIT,
    "description": "Finish the inspection with the branch mandated by the last policy verdict.",
    "input_schema": {
        "type": "object",
        "properties": {
            "branch": {"type": "string"},
            "message": {"type": "string"},
        },
        "required": ["branch", "message"],
    },
}

STAGE_OF = {
    "assess_quality": "quality",
    "align_to_baseline": "alignment",
    "diff_against_memory": "diff",
    "crop_and_rescan": "rescan",
    "classify_severity": "severity",
}

NEXT_TOOL = {
    policy_module.QUALITY_OK: "align_to_baseline",
    policy_module.RETRY_CLASSIC: "align_to_baseline",
    policy_module.ALIGNED: "diff_against_memory",
    policy_module.CROP_AND_RESCAN: "crop_and_rescan",
    policy_module.CHANGE_CONFIRMED: "classify_severity",
}

NUDGE = "You did not call any tool. Call {expected} to continue the inspection."
PREMATURE_SUBMIT = (
    "You called submit in the same turn as other tools, so you have not seen their "
    "results yet. The submission was discarded."
)
WRONG_BRANCH = (
    "The policy verdict mandates branch {expected!r}, not {got!r}. "
    "Call submit again with the mandated branch."
)
WRONG_TOOL = "The policy verdict mandates calling {expected!r} next."
LAST_CHANCE = (
    "You are almost out of turns. Call submit NOW with the branch of the last policy verdict."
)


@dataclass
class RunResult:
    run_id: str
    status: str
    branch: str | None
    decisions: list[dict]
    run_dir: Path


async def run(
    asset_id: str,
    capture_key: str,
    llm=None,
    policy: Policy | None = None,
    max_turns: int = 12,
    runs_dir: str | Path = "runs",
) -> RunResult:
    pol = policy or Policy.from_env()
    run_id = uuid.uuid4().hex[:12]
    captured_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    run_dir = Path(runs_dir) / run_id
    trace.emit(run_dir, "run_started", run_id=run_id, asset_id=asset_id, capture_key=capture_key)

    decisions: list[dict] = []
    stage_metrics: dict[str, dict] = {}
    image_keys = {"capture": capture_key}
    state = {
        "run_id": run_id,
        "asset_id": asset_id,
        "captured_at": captured_at,
        "capture_key": capture_key,
    }

    def record(decision: dict, span: dict | None = None) -> dict:
        decisions.append(decision)
        runs.write(run_dir, "decisions.json", decisions)
        if span is None:
            trace.emit(run_dir, "decision", **decision)
        else:
            trace.emit(run_dir, "tool_call", **span, policy=decision)
        return decision

    def finish(status: str, branch: str | None, message: str | None = None) -> RunResult:
        trace.emit(run_dir, "run_finished", status=status, branch=branch, message=message)
        state.update(status=status, branch=branch, message=message)
        runs.write(run_dir, "state.json", state)
        return RunResult(run_id, status, branch, decisions, run_dir)

    def conclude(branch: str, message: str) -> RunResult:
        if branch == policy_module.AUTO_WRITE:
            hitl.commit(asset_id, run_id, captured_at, stage_metrics, image_keys)
        elif branch == policy_module.NO_CHANGE:
            store.put_inspection(asset_id, run_id, captured_at, stage_metrics, image_keys)
        elif branch == policy_module.HUMAN_APPROVAL:
            trace.emit(run_dir, "approval_requested", message=message)
            hitl.request_approval(run_dir, {
                "run_id": run_id,
                "asset_id": asset_id,
                "captured_at": captured_at,
                "metrics": stage_metrics,
                "image_keys": image_keys,
                "message": message,
            })
            return finish("awaiting_approval", branch, message)
        return finish("completed", branch, message)

    baseline = store.current_baseline(asset_id)
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "services.mcp_server.server"],
        env=dict(os.environ),
    )
    async with (
        stdio_client(params) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()

        async def call(name: str, args: dict) -> tuple[dict, dict | None]:
            start = time.perf_counter()
            result = await session.call_tool(name, args)
            duration_ms = round((time.perf_counter() - start) * 1000, 1)
            text = result.content[0].text if result.content else ""
            payload = {"error": text} if result.is_error else json.loads(text)
            span = {"tool": name, "args": args, "duration_ms": duration_ms}
            if "error" in payload:
                trace.emit(run_dir, "tool_call", **span, error=payload["error"])
                return payload, None
            span["metrics"] = payload
            return payload, span

        if baseline is None:
            record(policy_module.decision(
                "baseline_exists", 0.0, 1.0, policy_module.FIRST_BASELINE
            ))
            metrics, span = await call("assess_quality", {"image_key": capture_key})
            if "error" in metrics:
                return finish("failed", None, metrics["error"])
            stage_metrics["quality"] = metrics
            verdict = record(policy_module.evaluate("quality", metrics, pol), span)
            if verdict["branch"] == policy_module.RECAPTURE:
                return finish("completed", policy_module.RECAPTURE)
            hitl.commit(asset_id, run_id, captured_at, stage_metrics, image_keys)
            return finish("completed", policy_module.FIRST_BASELINE)

        baseline_key = baseline["image_key"]
        detector = alignment.default_detector()
        if llm is None:
            llm = (
                GeminiLLM()
                if os.environ.get("GOOGLE_API_KEY")
                else PolicyFollowingLLM(capture_key, baseline_key, detector)
            )
        listed = (await session.list_tools()).tools
        tools = [
            {"name": t.name, "description": t.description or "", "input_schema": t.input_schema}
            for t in listed
        ]
        tools.append(SUBMIT_TOOL)

        expected_tool = "assess_quality"
        expected_branch: str | None = None
        history: list[dict] = [{
            "role": "user",
            "text": (
                f"Inspect asset {asset_id}. Capture: {capture_key}. Baseline: {baseline_key}. "
                f"Start with assess_quality, and use detector {detector!r} when aligning "
                f"(on a retry_classic verdict, align again with detector {alignment.CLASSIC!r})."
            ),
        }]

        for turn_index in range(max_turns):
            turn = await asyncio.to_thread(llm.generate, SYSTEM, history, tools)
            if not turn.calls:
                history.append({"role": "model", "text": turn.text or "(no content)"})
                history.append({"role": "user", "text": NUDGE.format(expected=expected_tool)})
                continue

            history.append({"role": "model", "text": turn.text, "calls": turn.calls})
            responses: list[tuple[str, dict]] = []
            if len(turn.calls) == 1 and turn.calls[0].name == SUBMIT:
                got = turn.calls[0].args.get("branch")
                if expected_branch is not None and got == expected_branch:
                    return conclude(got, turn.calls[0].args.get("message", ""))
                responses.append((
                    SUBMIT,
                    {"error": WRONG_BRANCH.format(expected=expected_branch, got=got)},
                ))
            else:
                for tool_call in turn.calls:
                    if tool_call.name == SUBMIT:
                        responses.append((SUBMIT, {"error": PREMATURE_SUBMIT}))
                        continue
                    if tool_call.name != expected_tool:
                        responses.append((
                            tool_call.name,
                            {"error": WRONG_TOOL.format(expected=expected_tool)},
                        ))
                        continue
                    metrics, span = await call(tool_call.name, tool_call.args)
                    if "error" in metrics:
                        responses.append((tool_call.name, metrics))
                        continue
                    stage = STAGE_OF[tool_call.name]
                    verdict = record(policy_module.evaluate(stage, metrics, pol), span)
                    stage_metrics[stage] = metrics
                    if stage == "alignment" and metrics.get("aligned_key"):
                        image_keys["aligned"] = metrics["aligned_key"]
                        image_keys["valid_mask"] = metrics["valid_mask_key"]
                    expected_tool = NEXT_TOOL.get(verdict["branch"], SUBMIT)
                    expected_branch = verdict["branch"] if expected_tool == SUBMIT else None
                    responses.append((tool_call.name, {"metrics": metrics, "policy": verdict}))
            history.append({"role": "tool", "responses": responses})
            if turn_index == max_turns - 2:
                history.append({"role": "user", "text": LAST_CHANCE})

    return finish("failed", None, f"no submit within {max_turns} turns")
