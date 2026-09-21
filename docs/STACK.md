# Technology stack

This document is the canonical inventory of the technologies used by Afterimage. Exact Python
package versions are owned by `requirements.txt` for the direct dependencies and by
`requirements.lock` for the whole installed tree; deployment settings are owned by
`infra/template.yaml` and the container files.

## Application stack

| Layer | Technology | Role | Source of truth |
|---|---|---|---|
| Language | Python 3.12 | Application, evaluation, tooling, and deployment scripts | `Dockerfile` |
| Computer vision | OpenCV headless 5.0.0.93, NumPy 2.5.2 | Quality, alignment, diffing, cropping, and severity features | `requirements.txt` |
| Learned features | ALIKED and LightGlue ONNX | Neural keypoint detection and matching | `services/perception/weights.py` |
| Web | FastAPI 0.141.1, Uvicorn 0.52.4 | HTTP routing and ASGI runtime | `requirements.txt` |
| Server rendering | Jinja2 3.1.6 | Autoescaped HTML templates | `requirements.txt` |
| Browser | HTML, CSS, vanilla JavaScript | Interaction, polling, theme, and progressive enhancement | `services/ui/` |
| Agent protocol | MCP 2.1.1 | Stdio boundary for the five perception tools | `requirements.txt` |
| Optional model | Google Gen AI SDK 2.20.0 | Gemini function calling and phrasing | `requirements.txt` |
| AWS client | boto3 1.43.78 | DynamoDB and S3 access | `requirements.txt` |
| Quality gates | pytest, pytest-cov, Ruff, mypy | Tests, coverage, lint, and type checking | `requirements.txt`, `pyproject.toml` |

There is no React, Vite, Node runtime, frontend package manager, or browser build step. Static files
are served directly by FastAPI with content-hashed URLs.

## Runtime and data

| Environment | Components |
|---|---|
| Local | Docker Compose, an `arm64` application container, LocalStack 4.9.2, DynamoDB, and S3. |
| Production | One `arm64` Lambda container with Lambda Web Adapter 0.9.1 behind a public Function URL. |
| Durable data | One DynamoDB table for asset history and one private S3 bucket for images and run artifacts. |
| Operational data | CloudWatch Logs with configured retention and an EventBridge health request every five minutes. |

The production function is configured with 2,048 MB of memory and a 900-second timeout. S3 objects
expire after 180 days, and DynamoDB items carry a `ttl` set to the same horizon. The DynamoDB
table uses on-demand billing. These values must be verified in
`infra/template.yaml` before being quoted elsewhere.

## Build and delivery

- `Dockerfile` builds the Python environment, installs OpenCV 5 dependencies, includes the ONNX
  models under `/opt/models`, and produces the Lambda-compatible image.
- `docker-compose.yml` runs the local application on port 8000 and LocalStack on port 4566.
- `Makefile` owns the supported build, test, evaluation, demo, and deployment commands.
- `.github/workflows/ci.yml` runs on native `ubuntu-24.04-arm` and executes the runtime, lint, type,
  coverage, and test gates.
- `.github/workflows/deploy.yml` is manual, authenticates to AWS through GitHub OIDC, and delegates
  deployment to `deploy.sh`.
- `deploy.sh` downloads weights, maintains the ECR retention policy, builds for `linux/arm64`,
  deploys through SAM/CloudFormation, and performs a health smoke test.

## Configuration

| Variable | Purpose |
|---|---|
| `AFTERIMAGE_TABLE` | DynamoDB table name. |
| `AFTERIMAGE_BUCKET` | S3 bucket for images and run artifacts. |
| `AFTERIMAGE_WEIGHTS_DIR` | ALIKED and LightGlue model directory. |
| `AFTERIMAGE_RUNS_DIR` | Local run-artifact directory. |
| `AFTERIMAGE_RUNS_S3` | Enables S3-backed run artifacts. |
| `AFTERIMAGE_GEMINI_MODEL` | Overrides the Gemini model name. |
| `GOOGLE_API_KEY` | Enables the live Gemini driver. |

Every field in `services/agent/policy.py:Policy` can also be overridden with
`AFTERIMAGE_<FIELD_NAME_UPPER>`. Without `GOOGLE_API_KEY`, the deterministic
`PolicyFollowingLLM` driver is used.

## Supported commands

| Command | Result |
|---|---|
| `make weights` | Downloads and verifies ALIKED and LightGlue weights. |
| `make dev` | Starts the local application and dependencies. |
| `make build` | Builds the application container. |
| `make verify-runtime` | Verifies OpenCV 5 and required feature APIs on `arm64`. |
| `make lint` | Runs Ruff over application and evaluation code. |
| `make typecheck` | Runs mypy over `services/`. |
| `make test` | Runs all tests with the 90% service coverage floor. |
| `make demo` | Exercises the four main action branches with the scripted driver. |
| `make eval` | Evaluates the committed scenarios and updates published results. |
| `make deploy` | Builds and deploys the AWS stack. |
