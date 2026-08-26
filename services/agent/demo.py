import argparse
import asyncio
import json
import uuid

from services.agent import hitl, loop
from services.agent import policy as policy_module
from services.agent.llm import GeminiLLM
from services.agent.scripted import PolicyFollowingLLM, seed_baseline
from services.memory import images, store
from services.perception import alignment
from services.perception.tests.panels import (
    blurred,
    foreign_panel,
    shifted,
    solar_panel,
    with_crack,
    with_faint_spot,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Drive the four agent branches locally.")
    parser.add_argument("--live", action="store_true", help="use the Gemini API instead of the scripted driver")
    args = parser.parse_args()

    store.ensure_table()
    images.ensure_bucket()
    panel = solar_panel(seed=0)
    detector = alignment.default_detector()
    scenarios = [
        ("ACTION 1 - request recapture", blurred(panel), policy_module.RECAPTURE),
        ("ACTION 2 - unrecognized asset", foreign_panel(), policy_module.UNRECOGNIZED_ASSET),
        ("ACTION 3 - active perception", shifted(with_faint_spot(panel, 3, 7)), policy_module.AUTO_WRITE),
        ("ACTION 4 - human approval", shifted(with_crack(panel, 2, 4)), policy_module.HUMAN_APPROVAL),
    ]

    for title, capture, expected in scenarios:
        asset = f"demo-{uuid.uuid4().hex[:6]}"
        baseline_key = seed_baseline(asset, panel)
        capture_key = images.put_image(asset, "capture", "capture", capture)
        llm = GeminiLLM() if args.live else PolicyFollowingLLM(capture_key, baseline_key, detector)
        result = asyncio.run(loop.run(asset, capture_key, llm))
        print(f"\n=== {title} -> {result.branch} ({result.status}) ===")
        print(json.dumps(result.decisions, indent=2))
        assert result.branch == expected, f"{title}: expected {expected}, got {result.branch}"
        if result.branch == policy_module.HUMAN_APPROVAL:
            print("human gate:", json.dumps(hitl.resolve(result.run_dir, approved=True)))

    print("\nall four branches fired")


if __name__ == "__main__":
    main()
