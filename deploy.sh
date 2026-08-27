#!/usr/bin/env bash
set -euo pipefail

STACK=${STACK_NAME:-afterimage}
ROOT=$(cd "$(dirname "$0")" && pwd)

command -v aws >/dev/null || { echo "aws CLI not found"; exit 1; }
command -v docker >/dev/null || { echo "docker not found"; exit 1; }
: "${GOOGLE_API_KEY:?GOOGLE_API_KEY is missing: the public endpoint runs the live agent}"

export AWS_DEFAULT_REGION=${AWS_REGION:-${AWS_DEFAULT_REGION:-$(aws configure get region || echo us-east-1)}}
REGION=$AWS_DEFAULT_REGION

ACCOUNT=$(aws sts get-caller-identity --query Account --output text 2>/dev/null) || {
    echo "AWS credentials are not valid"
    echo "(temporary credentials also need AWS_SESSION_TOKEN, and they expire)"
    exit 1
}
REPO="$ACCOUNT.dkr.ecr.$REGION.amazonaws.com/$STACK"

echo "==> Ensuring the ECR repository"
aws ecr describe-repositories --repository-names "$STACK" >/dev/null 2>&1 \
    || aws ecr create-repository --repository-name "$STACK" >/dev/null
aws ecr put-lifecycle-policy --repository-name "$STACK" --lifecycle-policy-text '{
    "rules": [{"rulePriority": 1, "description": "keep the last 5 images",
               "selection": {"tagStatus": "any", "countType": "imageCountMoreThan", "countNumber": 5},
               "action": {"type": "expire"}}]}' >/dev/null
aws ecr get-login-password | docker login --username AWS --password-stdin "$ACCOUNT.dkr.ecr.$REGION.amazonaws.com" >/dev/null

echo "==> Building and pushing the image"
make -C "$ROOT" weights
TAG=$(git -C "$ROOT" rev-parse --short HEAD)
docker buildx build --platform linux/arm64 --provenance=false \
    -t "$REPO:$TAG" --push "$ROOT"

echo "==> Deploying the stack"
STATUS=$(aws cloudformation describe-stacks --stack-name "$STACK" \
    --query 'Stacks[0].StackStatus' --output text 2>/dev/null || echo NONE)
if [ "$STATUS" = ROLLBACK_COMPLETE ] || [ "$STATUS" = REVIEW_IN_PROGRESS ]; then
    echo "    $STACK is in $STATUS (a first creation that failed): deleting it before retrying"
    aws cloudformation delete-stack --stack-name "$STACK"
    aws cloudformation wait stack-delete-complete --stack-name "$STACK"
fi
PARAMS_FILE=$(mktemp)
trap 'rm -f "$PARAMS_FILE"' EXIT
cat > "$PARAMS_FILE" <<EOF
{"Parameters": {"ImageUri": "$REPO:$TAG", "GoogleApiKey": "$GOOGLE_API_KEY"}}
EOF
aws cloudformation deploy \
    --template-file "$ROOT/infra/template.yaml" \
    --stack-name "$STACK" \
    --capabilities CAPABILITY_IAM \
    --no-fail-on-empty-changeset \
    --parameter-overrides "file://$PARAMS_FILE"

FUNCTION_URL=$(aws cloudformation describe-stacks --stack-name "$STACK" \
    --query "Stacks[0].Outputs[?OutputKey=='FunctionUrl'].OutputValue" --output text)

echo "==> Smoke test"
curl -sf "${FUNCTION_URL%/}/health" >/dev/null || { echo "health check failed at $FUNCTION_URL"; exit 1; }

echo
echo "App: $FUNCTION_URL"
