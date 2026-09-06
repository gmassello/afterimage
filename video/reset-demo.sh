#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# reset-demo.sh — leave the public endpoint in the state a take needs.
#
# The asset list is the first screen of the video and the first screen a judge
# sees. Evaluation runs, README captures and rehearsals all leave assets behind,
# and they read as scaffolding. This removes every asset except the ones the demo
# is about, and it is idempotent: run it before a take and again between takes.
#
#   bash video/reset-demo.sh            # report only, changes nothing
#   bash video/reset-demo.sh --apply    # delete
#
# Only DynamoDB rows go. Traces live under runs/{run_id}/ and are addressed by
# run id, so every /traces/... URL already published stays reachable — including
# the two linked from the technical report. Orphaned S3 images are invisible to
# the app and the bucket expires them on its own.
#
# Env:  TABLE   DynamoDB table   (default: afterimage)
#       KEEP    assets to spare  (default: the three the demo is about)
# ---------------------------------------------------------------------------
set -euo pipefail

TABLE="${TABLE:-afterimage}"
KEEP="${KEEP:-panel-a7-north panel-b3-east panel-c2-west}"
APPLY=0
[ "${1:-}" = "--apply" ] && APPLY=1

command -v aws >/dev/null || { echo "aws CLI not found"; exit 1; }
aws sts get-caller-identity >/dev/null 2>&1 || {
  echo "AWS credentials are not valid or have expired."
  echo "Refresh them, then run this again."
  exit 1
}

kept() {
  for k in $KEEP; do [ "$k" = "$1" ] && return 0; done
  return 1
}

keys() {
  aws dynamodb query --table-name "$TABLE" \
    --key-condition-expression '#p = :p' \
    --expression-attribute-names '{"#p":"pk"}' \
    --expression-attribute-values "{\":p\":{\"S\":\"ASSET#$1\"}}" \
    --query 'Items[].sk.S' --output text | tr '\t' '\n' | grep -v '^$'
}

ASSETS=$(aws dynamodb scan --table-name "$TABLE" \
  --filter-expression '#s = :m' \
  --expression-attribute-names '{"#s":"sk"}' \
  --expression-attribute-values '{":m":{"S":"META"}}' \
  --query 'Items[].asset_id.S' --output text | tr '\t' '\n' | grep -v '^$' | sort)

[ -n "$ASSETS" ] || { echo "no assets in $TABLE"; exit 0; }

echo
GONE=0
ROWS=0
for asset in $ASSETS; do
  if kept "$asset"; then
    printf '  keep    %-28s\n' "$asset"
    continue
  fi
  n=$(keys "$asset" | wc -l | tr -d ' ')
  printf '  delete  %-28s %s rows\n' "$asset" "$n"
  GONE=$((GONE + 1)); ROWS=$((ROWS + n))
  [ "$APPLY" = 1 ] || continue
  while read -r sk; do
    aws dynamodb delete-item --table-name "$TABLE" \
      --key "{\"pk\":{\"S\":\"ASSET#$asset\"},\"sk\":{\"S\":\"$sk\"}}"
  done < <(keys "$asset")
done

echo
if [ "$APPLY" = 1 ]; then
  echo "  removed $GONE assets, $ROWS rows"
else
  echo "  would remove $GONE assets, $ROWS rows — re-run with --apply"
fi
echo
