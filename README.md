# afterimage

A visual inspection agent that remembers. It inspects physical assets from photos or video, decides on its own what to look at next, and keeps a memory of every previous inspection of the same asset to detect degradation over time.

Built for the [OpenCV AI Competition 2026](https://opencv26.devpost.com/) — Agentic Vision path.

**[Try the live agent](https://jgmzrkpa344jwixw7nbulgh2ju0mojcb.lambda-url.us-east-1.on.aws/)** — upload a capture, watch the loop decide, read the trace. No login.

**[Read the field manual](https://gmassello.github.io/afterimage/)** — a plain-language walkthrough of what the agent measures, what it decides, and why.

## Architecture

An agentic loop where every OpenCV result changes what the system does next: capture quality gates recapture requests, feature alignment (OpenCV 5 `Features`: ALIKED + LightGlue) anchors the image to the stored baseline of the same asset, diffing against memory triggers active zoom on uncertain regions, and severity gates human approval before any ticket is opened. Perception runs in an arm64 OpenCV 5 container on AWS Lambda (Graviton), memory lives in DynamoDB + S3, and every decision is emitted as an event in the per-run trace carrying the numeric value that triggered it.

Full brief and weekly plan: [`docs/BRIEF.md`](docs/BRIEF.md).

## Requirements

- Docker with Compose v2 (arm64 host or emulation)
- `make`

## Run

```bash
make weights   # download the ALIKED and LightGlue ONNX models into models/ (52 MB, sha1 verified)
make dev       # build the image and start the full local stack (LocalStack S3 + DynamoDB)
make test      # run the test suite inside the container
make demo      # drive the agent loop through all four action branches locally
```

`make demo` uses a scripted driver by default; add `GOOGLE_API_KEY` to the environment and run
`docker-compose run --rm app python -m services.agent.demo --live` to let Gemini orchestrate the
same loop over MCP. Either way the branch verdicts are computed in code by the policy.

## Deploy

The app runs as a single arm64 Lambda container image behind a Function URL: FastAPI serves the
site (upload, asset history, approval queue, trace viewer) and runs the agent loop inside the
request; run artefacts persist under `runs/` in the app bucket (`AFTERIMAGE_RUNS_S3=1`), so traces
survive redeploys and cold sandboxes.

One-time bootstrap:

```bash
# immutable IDs for the OIDC sub claim (already baked into the template default)
gh api repos/gmassello/afterimage --jq '{repo_id: .id, owner_id: .owner.id}'

aws cloudformation deploy --template-file infra/github-oidc.yaml \
    --stack-name afterimage-github-oidc --capabilities CAPABILITY_NAMED_IAM

# GitHub: secrets.AWS_ROLE_ARN (RoleArn output above), secrets.GOOGLE_API_KEY, vars.AWS_REGION
```

Then either run the **Deploy** workflow (Actions → Deploy → run), or locally:

```bash
GOOGLE_API_KEY=... make deploy   # ECR + docker buildx arm64 + CloudFormation, idempotent
```

The deploy prints the public URL. Endpoints: `/` (assets + upload), `/assets/{id}` (history),
`/queue` (human approvals), `/traces/{run_id}` (per-run trace, JSON or HTML), `/health`.

## Status

Week 6: the public endpoint. The same FastAPI that serves traces now serves the whole product —
upload a capture and the agent loop runs live (Gemini over MCP, policy verdicts in code), the
approval queue resolves the human gate, and the asset history shows every inspection and baseline.
Deployed by IaC (`infra/`) through GitHub OIDC with a permissions boundary; run traces live in S3.

Week 5: observability. Every run persists `runs/{run_id}/events.json` — one span per tool call with
its arguments, metrics, duration and the policy verdict that the value triggered — served by
`GET /traces/{run_id}` as JSON or a human-readable page.

Week 4: the agent. `services/mcp_server/` exposes the five perception tools over MCP (images
travel as S3 keys, never inline), and `services/agent/` runs the loop: an LLM (Gemini) orchestrates
the tool calls while `policy.py` evaluates every result in code and records
`{input_metric, value, threshold, branch}` for each decision — the branch verdict is deterministic
and provable, never inferred from the prompt. All four actions fire locally (`make demo`): request
recapture, retry with the fallback detector / declare the asset unrecognised, crop-and-rescan an
uncertain region, and hold a high-severity write for human approval (`pending.json` +
`python -m services.agent.run --resume RUN_ID --approve`).

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
