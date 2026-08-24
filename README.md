# afterimage

A visual inspection agent that remembers. It inspects physical assets from photos or video, decides on its own what to look at next, and keeps a memory of every previous inspection of the same asset to detect degradation over time.

Built for the [OpenCV AI Competition 2026](https://opencv26.devpost.com/) — Agentic Vision path.

## Architecture

An agentic loop where every OpenCV result changes what the system does next: capture quality gates recapture requests, feature alignment (OpenCV 5 `Features`: ALIKED + LightGlue) anchors the image to the stored baseline of the same asset, diffing against memory triggers active zoom on uncertain regions, and severity gates human approval before any ticket is opened. Perception runs in an arm64 OpenCV 5 container on AWS (ECS Fargate on Graviton), memory lives in DynamoDB + S3, and every decision is emitted as an OpenTelemetry span carrying the numeric value that triggered it.

Full brief and weekly plan: [`docs/BRIEF.md`](docs/BRIEF.md).

## Requirements

- Docker with Compose v2 (arm64 host or emulation)
- `make`

## Run

```bash
make dev    # build the image and start the full local stack (LocalStack S3 + DynamoDB)
make test   # run the test suite inside the container
```

## Status

Week 1: scaffolding. An arm64 container with OpenCV 5 that reads an image from S3 (LocalStack) and returns a blur metric (Laplacian variance) computed with OpenCV.
