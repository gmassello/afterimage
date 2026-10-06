#!/usr/bin/env bash
set -euo pipefail

SINCE="${1:?usage: latency.sh <ISO-8601 start, e.g. the last deploy>}"
GROUP="${LOG_GROUP:-/aws/lambda/afterimage-api}"
REGION="${AWS_REGION:-us-east-1}"
MEMORY_GB=2
REQUEST_USD=0.0000002
PUBLISHED_RATE=0.0000133334

if date -d "$SINCE" +%s >/dev/null 2>&1; then
  START=$(date -d "$SINCE" +%s)
else
  START=$(date -j -u -f "%Y-%m-%dT%H:%M:%SZ" "$SINCE" +%s)
fi
END=$(date +%s)

query() {
  local id status
  id=$(aws logs start-query --region "$REGION" --log-group-name "$GROUP" \
    --start-time "$START" --end-time "$END" --query-string "$2" --query queryId --output text)
  until status=$(aws logs get-query-results --region "$REGION" --query-id "$id" --query status --output text) \
    && [ "$status" = Complete ]; do sleep 2; done
  echo "## $1"
  aws logs get-query-results --region "$REGION" --query-id "$id" \
    --query 'results[0][].[field,value]' --output text
}

query cold 'filter @type="REPORT" and ispresent(@initDuration)
  | stats count(), pct(@initDuration,50), pct(@initDuration,90), max(@initDuration), max(@duration)'
query warm 'filter @type="REPORT" and not ispresent(@initDuration)
  | stats count(), pct(@duration,50), pct(@duration,90), pct(@duration,99)'
INSPECTION=$(query inspection 'filter @type="REPORT" and @duration > 10000
  | stats count(), pct(@duration,50), min(@duration), max(@duration), pct(@billedDuration,50) as billed_p50, max(@maxMemoryUsed)/1048576')
echo "$INSPECTION"
query totals 'filter @type="REPORT"
  | stats count(), sum(@billedDuration)/1000*2 as gb_s, sum(ispresent(@initDuration)) as cold'

RATE=$(aws pricing get-products --region us-east-1 --service-code AWSLambda \
  --filters Type=TERM_MATCH,Field=group,Value=AWS-Lambda-Duration-ARM \
  Type=TERM_MATCH,Field=regionCode,Value="$REGION" \
  --query 'PriceList[0]' --output text 2>/dev/null \
  | jq -r '[.terms.OnDemand[].priceDimensions[] | {b: (.beginRange|tonumber), p: .pricePerUnit.USD}]
           | sort_by(.b) | .[0].p' 2>/dev/null || true)
if [ -z "$RATE" ] || [ "$RATE" = null ]; then
  echo "pricing:GetProducts unavailable; using the rate read on 27 September 2026" >&2
  RATE=$PUBLISHED_RATE
fi

BILLED_MS=$(printf '%s\n' "$INSPECTION" | awk '$1=="billed_p50"{print $2}')
echo "## cost"
awk -v ms="${BILLED_MS:-0}" -v gb="$MEMORY_GB" -v rate="$RATE" -v req="$REQUEST_USD" \
  'BEGIN { printf "rate %s USD per GB-s\nper inspection %.4f USD (%.2f s billed at p50)\n", rate, ms/1000*gb*rate+req, ms/1000 }'
