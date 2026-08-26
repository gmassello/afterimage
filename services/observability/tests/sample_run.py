RUN_ID = "abcdef123456"

STATE = {
    "run_id": RUN_ID,
    "asset_id": "demo-asset",
    "status": "completed",
    "branch": "unrecognized_asset",
}

EVENTS = [
    {
        "type": "run_started",
        "ts": "2026-08-26T12:00:00.000+00:00",
        "run_id": RUN_ID,
        "asset_id": "demo-asset",
        "capture_key": "demo-asset/insp1/capture.png",
    },
    {
        "type": "tool_call",
        "ts": "2026-08-26T12:00:01.000+00:00",
        "tool": "align_to_baseline",
        "args": {"image_key": "demo-asset/insp1/capture.png", "detector": "classic"},
        "duration_ms": 500.0,
        "metrics": {"inlier_ratio": 0.259, "matches": 41},
        "policy": {
            "input_metric": "inlier_ratio",
            "value": 0.259,
            "threshold": 0.5,
            "branch": "unrecognized_asset",
        },
    },
    {
        "type": "run_finished",
        "ts": "2026-08-26T12:00:01.100+00:00",
        "status": "completed",
        "branch": "unrecognized_asset",
        "message": "panel not recognized",
    },
]
