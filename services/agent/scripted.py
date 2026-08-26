from services.agent import policy
from services.agent.llm import ToolCall, Turn
from services.memory import images, store
from services.perception import alignment


class ScriptedLLM:
    def __init__(self, turns):
        self.turns = list(turns)

    def generate(self, system, history, tools):
        return self.turns.pop(0)


class PolicyFollowingLLM:
    def __init__(self, capture_key, baseline_key, detector):
        self.capture_key = capture_key
        self.baseline_key = baseline_key
        self.detector = detector
        self.aligned_key = None
        self.valid_mask_key = None

    def generate(self, system, history, tools):
        last_tool_entry = next(
            (entry for entry in reversed(history) if entry["role"] == "tool"), None
        )
        if last_tool_entry is None:
            return Turn(calls=(ToolCall("assess_quality", {"image_key": self.capture_key}),))
        name, payload = last_tool_entry["responses"][-1]
        verdict = payload["policy"]
        branch = verdict["branch"]
        if name == "align_to_baseline":
            self.aligned_key = payload["metrics"]["aligned_key"]
            self.valid_mask_key = payload["metrics"]["valid_mask_key"]
        if branch == policy.QUALITY_OK:
            call = ToolCall("align_to_baseline", {
                "image_key": self.capture_key,
                "baseline_key": self.baseline_key,
                "detector": self.detector,
            })
        elif branch == policy.RETRY_CLASSIC:
            call = ToolCall("align_to_baseline", {
                "image_key": self.capture_key,
                "baseline_key": self.baseline_key,
                "detector": alignment.CLASSIC,
            })
        elif branch == policy.ALIGNED:
            call = ToolCall("diff_against_memory", {
                "aligned_key": self.aligned_key,
                "baseline_key": self.baseline_key,
                "valid_mask_key": self.valid_mask_key,
            })
        elif branch == policy.CROP_AND_RESCAN:
            call = ToolCall("crop_and_rescan", {
                "aligned_key": self.aligned_key,
                "baseline_key": self.baseline_key,
                "bbox": verdict["extra"]["bbox"],
            })
        elif branch == policy.CHANGE_CONFIRMED:
            call = ToolCall("classify_severity", {
                "aligned_key": self.aligned_key,
                "baseline_key": self.baseline_key,
                "bbox": verdict["extra"]["bbox"],
                "area_ratio": verdict["extra"]["area_ratio"],
            })
        else:
            call = ToolCall("submit", {"branch": branch, "message": f"inspection ended: {branch}"})
        return Turn(calls=(call,))


def seed_baseline(asset_id, baseline_image, inspection_id="baseline"):
    store.put_asset(asset_id)
    key = images.put_image(asset_id, inspection_id, "capture", baseline_image)
    store.promote_baseline(asset_id, inspection_id, "2026-08-01T00:00:00+00:00", key, 300.0)
    return key
