# Security

afterimage is a competition demonstrator with a public, unauthenticated endpoint. This file states
what that means, which controls exist, and which deliberately do not. Every control below is a line
of code or infrastructure in this repository, not an intention.

## The endpoint is public by design

The competition requires a judge to use the system without an account, so the Function URL is
deployed with `AuthType: NONE` (`infra/template.yaml`). The consequences are stated rather than
mitigated:

- Anything uploaded is visible to anyone holding the URL.
- The human approval gate stops the machine from writing to memory on its own. It does **not**
  authenticate an operator: any visitor can resolve a pending inspection. It gates policy, not
  identity.
- Treat it as a demonstrator. Do not upload anything you would not publish.

## What the application checks

In `services/api/app.py`:

| Control | What it does |
|---|---|
| `ASSET_ID_PATTERN` | `^[a-z0-9-]{1,64}$`, enforced with `fullmatch` before any storage call |
| `RUN_ID_PATTERN` | twelve hex characters, enforced before the filesystem or S3 is touched |
| `MAX_UPLOAD_BYTES` | 6 MB; a larger body is rejected with 413 |
| Image decoding | a body that OpenCV cannot decode is rejected with 400, before anything is stored |
| Unknown ids | answered with 404 rather than 400, so the endpoint does not confirm what exists |
| Approval verdicts | restricted to `approve` and `reject` |

Templates are rendered by Jinja2 with autoescaping on (`services/ui/views.py`), and static assets are
served content-addressed from the same origin — no third-party script or font is fetched by the page.

Run traces are hash-chained: each event carries the SHA-256 of the one before it, and
`trace.broken_at` in `services/observability/trace.py` names the first event that does not verify.
That detects an edited, removed or reordered event. It is a chain, not a signature: it does not
detect a trace truncated at the end, and it does not stop anyone who can rewrite every hash from the
genesis link.

## What the deployment grants

- **No deploy credentials are stored.** GitHub Actions federates over OIDC
  (`.github/workflows/deploy.yml` requests `id-token: write` and nothing else). The trust policy in
  `infra/github-oidc.yaml` pins the `sub` claim to the immutable numeric owner and repository IDs,
  not to names, which can be transferred.
- **The deploy role carries no managed policy.** Its inline grant reaches only this stack's ECR
  repository, CloudFormation stack, function, table, bucket, log group and warmer rule. It may create
  roles only under `afterimage-*`, only with the stack's permissions boundary attached, and may pass
  a role only to Lambda.
- **The function itself** runs under the same permissions boundary, with CRUD on its own DynamoDB
  table and its own S3 bucket and nothing else (`infra/template.yaml`).
- **The API key** for the model provider is a `NoEcho` CloudFormation parameter. `deploy.sh` never
  puts it on a command line: it writes a `mktemp` parameter file, passes it as `file://`, and removes
  it on a shell trap.
- **No credentials live in git history.** The history was swept for key patterns and credential
  filenames; the only match is `AWS_SECRET_ACCESS_KEY=test`, the LocalStack dummy.

## Data handling and retention

- Captures and run artefacts live in one S3 bucket with all four public-access blocks enabled, and
  expire after **180 days**; incomplete multipart uploads are aborted after 7.
- DynamoDB items carry a `ttl` attribute set to the same **180 days**, so memory and images expire
  together instead of leaving records that point at deleted objects.
- CloudWatch Logs retain for **30 days**. ECR keeps the last 5 images.
- Encryption at rest is the AWS default for S3 and DynamoDB; the templates do not override it, and no
  customer-managed key is used.
- The approver of a human-gated inspection is recorded as a fingerprint, not an address: `_actor()`
  in `services/api/app.py` takes SHA-256 of the client address and user agent and keeps twelve hex
  characters. It is enough to tell two actors apart in a public trace. Note what it is not: the hash
  is unsalted, so anyone who already holds a candidate list of addresses can confirm a match by
  brute force. It de-identifies a trace for a reader, it does not anonymise against a targeted check.

## What is deliberately absent

- **No authentication or authorisation.** See above.
- **No rate limiting in the stack.** The account's Lambda concurrency quota is 10 and AWS will not
  let any of it be reserved, so the account limit is the only limit that exists. The property is
  deliberately absent from `infra/template.yaml`, where a `ponytail:` note records that reason and
  the upgrade path if the quota is ever raised.
- **No WAF, no bucket versioning, no CORS policy.** Out of scope for a demonstrator on a free-tier
  account.

## Reporting a problem

Open an issue at <https://github.com/gmassello/afterimage/issues>. If the problem should not be
public, use GitHub's private vulnerability reporting on the same repository. There is no bounty and
no SLA: this is a competition entry maintained by one person.
