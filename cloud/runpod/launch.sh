#!/usr/bin/env bash
# Run the Evo 2 workloads on one Runpod Secure Cloud pod, copy results back, and delete it.
# The pod runs the study image itself, so there is no Docker step. Uses Runpod REST API v2.
#
# Required environment:
#   PLATFORM_ID      e.g. P3
#   GPU_TYPE_IDS     JSON array, e.g. '["NVIDIA H100 80GB HBM3"]' (tried in order)
#   RUNPOD_API_KEY   API key (never commit it)
#   IMAGE_REF, BUNDLE, OUT, CODE_SHA256 as for the other launchers
# Optional: MAX_HOURS (default 3), DISK_GB (default 200)
set -euo pipefail
source "$(dirname "$0")/../common.sh"

MAX_HOURS=${MAX_HOURS:-3}
DISK_GB=${DISK_GB:-200}
NAME="evo2ops-$(lower "$PLATFORM_ID")-$(date -u +%Y%m%d%H%M%S)"
API=https://api.runpod.io/v2
mkdir -p "$OUT"
KEY="$OUT/.ssh-key"

# Call the API; print the body, and fail with the API's own error message on a non-2xx status.
rp() {
  local body status
  body=$(curl -sS -w '\n%{http_code}' -H "Authorization: Bearer $RUNPOD_API_KEY" -H "Content-Type: application/json" "$@")
  status=${body##*$'\n'}; body=${body%$'\n'*}
  if [[ $status != 2* ]]; then log "Runpod API $status: $body"; return 1; fi
  printf '%s' "$body"
}

POD_ID=""
cleanup() {
  set +e
  if [[ -n $POD_ID ]]; then
    log "Deleting pod $POD_ID"
    rp -X DELETE "$API/pods/$POD_ID" >/dev/null
    mark terminated
  fi
  rm -f "$KEY" "$KEY.pub"
}
trap cleanup EXIT

new_ssh_key
mark launch_requested
# Secure Cloud, on-demand. pod-start.sh installs the key, starts sshd and deletes the pod after MAX_HOURS.
for gpu in $(echo "$GPU_TYPE_IDS" | jq -r '.[] | @base64'); do
  gpu=$(echo "$gpu" | base64 --decode)
  BODY=$(jq -n --arg name "$NAME" --arg image "$IMAGE_REF" --arg gpu "$gpu" \
    --arg key "$(cat "$KEY.pub")" --argjson disk "$DISK_GB" --arg max "$((MAX_HOURS * 3600))" '{
      name: $name, image: $image, gpu: {id: $gpu, count: 1}, cloud: "SECURE", disk: $disk,
      ports: ["22/tcp"], env: {PUBLIC_KEY: $key, MAX_SECONDS: $max},
      cmd: ["/opt/evo2ops/pod-start.sh"]}')
  if POD=$(rp -X POST "$API/pods" -d "$BODY"); then
    POD_ID=$(echo "$POD" | jq -r .id)
    break
  fi
done
[[ -n $POD_ID ]] || { log "No pod could be created"; exit 3; }
log "Pod $POD_ID created ($gpu); waiting for the image pull and SSH port"
mark pod_created

for _ in $(seq 1 120); do
  POD=$(rp "$API/pods/$POD_ID" || true)
  SSH_HOST=$(echo "$POD" | jq -r '.ssh.direct.host // empty' 2>/dev/null)
  SSH_PORT=$(echo "$POD" | jq -r '.ssh.direct.port // empty' 2>/dev/null)
  [[ -n $SSH_HOST && -n $SSH_PORT ]] && break
  sleep 15
done
[[ -n ${SSH_HOST:-} ]] || { log "Pod never exposed SSH"; exit 3; }
mark running
echo "$POD" | jq --argjson disk "$DISK_GB" '{provider: "runpod", instance_type: .gpu.id, gpu: .gpu,
  region: .dataCenterId, zone: .dataCenterId, instance_id: .id, image: .image, purchase_option: "on-demand",
  cost_per_hr: .cost, disk_gb: $disk, host_cuda: .cudaVersion}' > "$OUT/instance.json"
SSH_USER=root
log "Pod at $SSH_HOST:$SSH_PORT, $(jq -r .cost_per_hr "$OUT/instance.json") USD/h"

wait_for_ssh
run_bundle direct
