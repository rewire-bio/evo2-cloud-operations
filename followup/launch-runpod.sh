#!/usr/bin/env bash
# Amendment 5 launcher: one Runpod pod, workloads run detached, the launcher polls for DONE.
# A dropped SSH connection no longer stops the workload. The pod is deleted on exit.
#
# Required environment: PLATFORM_ID, GPU_TYPE_IDS (JSON array), VARIANTS, RUNPOD_API_KEY,
#   IMAGE_REF, BUNDLE, OUT. Optional: MAX_HOURS (default 3), DISK_GB (default 150).
set -euo pipefail
source "$(dirname "$0")/../cloud/common.sh"

MAX_HOURS=${MAX_HOURS:-3}
DISK_GB=${DISK_GB:-150}
NAME="evo2ops-fu-$(lower "$PLATFORM_ID")-$(date -u +%Y%m%d%H%M%S)"
API=https://api.runpod.io/v2
mkdir -p "$OUT"
KEY="$OUT/.ssh-key"

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
  if [[ -n $POD_ID ]]; then log "Deleting pod $POD_ID"; rp -X DELETE "$API/pods/$POD_ID" >/dev/null; mark terminated; fi
  rm -f "$KEY" "$KEY.pub"
}
trap cleanup EXIT

new_ssh_key
mark launch_requested
for gpu in $(echo "$GPU_TYPE_IDS" | jq -r '.[] | @base64'); do
  gpu=$(echo "$gpu" | base64 --decode)
  BODY=$(jq -n --arg name "$NAME" --arg image "$IMAGE_REF" --arg gpu "$gpu" \
    --arg key "$(cat "$KEY.pub")" --argjson disk "$DISK_GB" --arg max "$((MAX_HOURS * 3600))" '{
      name: $name, image: $image, gpu: {id: $gpu, count: 1}, cloud: "SECURE", disk: $disk,
      ports: ["22/tcp"], env: {PUBLIC_KEY: $key, MAX_SECONDS: $max}, cmd: ["/opt/evo2ops/pod-start.sh"]}')
  if POD=$(rp -X POST "$API/pods" -d "$BODY"); then POD_ID=$(echo "$POD" | jq -r .id); break; fi
done
[[ -n $POD_ID ]] || { log "No pod could be created"; exit 3; }
log "Pod $POD_ID created ($gpu)"
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
echo "$POD" | jq --argjson disk "$DISK_GB" '{provider: "runpod", gpu: .gpu, region: .dataCenterId,
  instance_id: .id, image: .image, cost_per_hr: .cost, disk_gb: $disk, host_cuda: .cudaVersion}' > "$OUT/instance.json"
SSH_USER=root
log "Pod at $SSH_HOST:$SSH_PORT, $(jq -r .cost_per_hr "$OUT/instance.json") USD/h"

wait_for_ssh
ssh_cmd "mkdir -p /work"
copy_to "$BUNDLE/code.tar.gz" "$BUNDLE/data" /work/
ssh_cmd "mkdir -p /work/code && tar -xzf /work/code.tar.gz -C /work/code"
mark workload_start
# setsid detaches the job from the SSH session completely; a plain nohup ... & kept the session
# open in the first follow-up run (the launcher waited on it until the job finished).
ssh_cmd "cd /work && VARIANTS='$VARIANTS' setsid nohup bash /work/code/followup/remote-followup.sh > /work/remote.log 2>&1 < /dev/null & disown" || true

deadline=$((SECONDS + MAX_HOURS * 3600 - 600))
until ssh_cmd "test -f /work/out/DONE" 2>/dev/null; do
  [[ $SECONDS -lt $deadline ]] || { log "Time limit reached before DONE"; break; }
  done_now=$(ssh_cmd "ls /work/out/*/receipt.json 2>/dev/null | wc -l" 2>/dev/null || echo "?")
  log "Waiting; configurations finished: $done_now"
  sleep 120
done
mark workload_end
copy_from "/work/out/." "$OUT/" || log "Copying outputs back failed"
ssh_cmd "test -f /work/out/DONE"
