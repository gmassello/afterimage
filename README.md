# afterimage

A visual inspection agent that remembers. It inspects physical assets from photos or video, decides on its own what to look at next, and keeps a memory of every previous inspection of the same asset to detect degradation over time.

Built for the [OpenCV AI Competition 2026](https://opencv26.devpost.com/) — Agentic Vision path.

**[Read the field manual](https://gmassello.github.io/afterimage/)** — a plain-language walkthrough of what the agent measures, what it decides, and why.

## Architecture

An agentic loop where every OpenCV result changes what the system does next: capture quality gates recapture requests, feature alignment (OpenCV 5 `Features`: ALIKED + LightGlue) anchors the image to the stored baseline of the same asset, diffing against memory triggers active zoom on uncertain regions, and severity gates human approval before any ticket is opened. Perception runs in an arm64 OpenCV 5 container on AWS (ECS Fargate on Graviton), memory lives in DynamoDB + S3, and every decision is emitted as an OpenTelemetry span carrying the numeric value that triggered it.

Full brief and weekly plan: [`docs/BRIEF.md`](docs/BRIEF.md).

## Requirements

- Docker with Compose v2 (arm64 host or emulation)
- `make`

## Run

```bash
make weights   # download the ALIKED and LightGlue ONNX models into models/ (52 MB, sha1 verified)
make dev       # build the image and start the full local stack (LocalStack S3 + DynamoDB)
make test      # run the test suite inside the container
```

## Status

Week 3: memory. `services/memory/` is the longitudinal store — a single DynamoDB table that returns
an asset's whole history in one query, images in S3, and a baseline that is superseded rather than
overwritten. A second inspection of the same asset now retrieves its baseline from memory, aligns to
it and locates the new defect: `services/memory/tests/test_longitudinal.py`.

Week 2 closed perception. The five tools of `services/perception/` are implemented and tested on
synthetic fixtures — capture quality, baseline alignment (OpenCV 5 `Features`: ALIKED + LightGlue,
with ORB as the fallback detector), diffing against memory, crop-and-rescan, and defect severity.
Each returns the raw numeric metrics the agent will branch on; thresholds and policy land in week 4.

The neural matchers need two ONNX files that are not in the wheel. `make weights` downloads them into
`models/` and verifies the published sha1; the image copies them in at build time.

Progress against the rubric is tracked in [`docs/SUBMISSION.md`](docs/SUBMISSION.md).
