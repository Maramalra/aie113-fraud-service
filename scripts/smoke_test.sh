#!/usr/bin/env bash
# Smoke test: start the image, wait until healthy, score one payment. Usage: scripts/smoke_test.sh IMAGE
set -euo pipefail
IMAGE="${1:-fraud-service:local}"
cid=$(docker run -d -p 8000:8000 "$IMAGE")
trap 'docker rm -f "$cid" >/dev/null' EXIT

for i in $(seq 1 30); do
  status=$(docker inspect -f '{{.State.Health.Status}}' "$cid")
  [ "$status" = healthy ] && break
  sleep 2
done
echo "health: $status"; [ "$status" = healthy ]

echo "user inside the container: $(docker exec "$cid" whoami)"
[ "$(docker exec "$cid" whoami)" != root ]

body=$(curl -sf -X POST localhost:8000/v1/score -H 'content-type: application/json' -d @scripts/example_payment.json)
echo "$body"
echo "$body" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['decision']=='block' and d['reasons'][0]['feature']=='V14'; print('smoke test passed')"
