import argparse
import asyncio
import json
import sys
import uuid
from pathlib import Path

from services.agent import hitl, loop


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one inspection through the agent loop.")
    parser.add_argument("--asset")
    parser.add_argument("--image", help="path to the capture image")
    parser.add_argument("--resume", metavar="RUN_ID")
    parser.add_argument("--approve", action="store_true")
    parser.add_argument("--reject", action="store_true")
    parser.add_argument("--interactive", action="store_true")
    parser.add_argument("--max-turns", type=int, default=12)
    parser.add_argument("--runs-dir", default="runs")
    args = parser.parse_args()

    if args.resume:
        if args.approve == args.reject:
            parser.error("--resume needs exactly one of --approve / --reject")
        decision = hitl.resolve(Path(args.runs_dir) / args.resume, approved=args.approve)
        print(json.dumps(decision, indent=2))
        return

    if not (args.asset and args.image):
        parser.error("--asset and --image are required to start a run")
    import cv2

    from services.agent.llm import GeminiLLM
    from services.memory import images, store

    capture = cv2.imread(args.image, cv2.IMREAD_COLOR)
    if capture is None:
        parser.error(f"{args.image} is not a readable image")
    store.ensure_table()
    images.ensure_bucket()
    store.put_asset(args.asset)
    capture_key = images.put_image(args.asset, uuid.uuid4().hex[:12], "capture", capture)
    result = asyncio.run(loop.run(
        args.asset,
        capture_key,
        GeminiLLM(),
        max_turns=args.max_turns,
        runs_dir=args.runs_dir,
    ))
    print(json.dumps({
        "run_id": result.run_id,
        "status": result.status,
        "branch": result.branch,
        "decisions": result.decisions,
    }, indent=2))
    if result.status == "awaiting_approval" and args.interactive and sys.stdin.isatty():
        answer = input("approve the write? [y/N] ")
        decision = hitl.resolve(result.run_dir, approved=answer.strip().lower() == "y")
        print(json.dumps(decision, indent=2))


if __name__ == "__main__":
    main()
