#!/usr/bin/env bash
set -euo pipefail

IMAGE=afterimage-smoke
PORT=${SMOKE_PORT:-8080}
docker build -t "$IMAGE" .
docker rm -f "$IMAGE" >/dev/null 2>&1 || true
trap 'docker logs "$IMAGE" 2>&1 | tail -20; docker rm -f "$IMAGE" >/dev/null 2>&1 || true' EXIT
docker run -d --name "$IMAGE" -p "$PORT:8080" "$IMAGE" >/dev/null

health=""
for _ in $(seq 1 60); do
  health=$(curl -s "http://localhost:$PORT/health" || true)
  [ -n "$health" ] && break
  sleep 2
done
echo "/health: $health"
echo "$health" | grep -q '"ok":true' || { echo "the container is up but its calibration failed"; exit 1; }
echo "$health" | grep -q '"branch":"aligned"' || { echo "the calibration did not align"; exit 1; }
curl -s "http://localhost:$PORT/" | grep -q '<title>afterimage' || { echo "the landing did not render"; exit 1; }
echo "smoke ok"
