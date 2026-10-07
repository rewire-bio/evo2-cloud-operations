#!/usr/bin/env bash
# Run the Evo 2 workloads on one RunPod Secure Cloud pod, copy results back, and delete it.
# The pod runs the study image itself, so there is no Docker step.
#
# Required environment:
#   PLATFORM_ID      e.g. P3
#   GPU_TYPE_IDS     JSON array, e.g. '["NVIDIA H100 80GB HBM3","NVIDIA H100 PCIe"]' (tried in order)
#   RUNPOD_API_KEY   API key (never commit it)
#   IMAGE_REF, BUNDLE, OUT, CODE_SHA256 as for the AWS launcher
# Optional: MAX_HOURS (default 3), DISK_GB (default 200)
set -euo pipefail
source "$(dirname "$0")/../common.sh"

MAX_HOURS=${MAX_HOURS:-3}
DISK_GB=${DISK_GB:-200}
NAME="evo2ops-$(lower "$PLATFORM_ID")-$(date -u +%Y%m%d%H%M%S)"
API=https://rest.runpod.io/v1
mkdir -p "$OUT"
KEY="$OUT/.ssh-key"
rp() { curl -fsS -H "Authorization: Bearer $RUNPOD_API_KEY" -H "Content-Type: application/json" "$@"; }

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
BODY=$(jq -n --arg name "$NAME" --arg image "$IMAGE_REF" --argjson gpus "$GPU_TYPE_IDS" \
  --arg key "$(cat "$KEY.pub")" --argjson disk "$DISK_GB" --arg max "$((MAX_HOURS * 3600))" '{
    name: $name, imageName: $image, gpuTypeIds: $gpus, gpuTypePriority: "custom", gpuCount: 1,
    cloudType: "SECURE", interruptible: false, containerDiskInGb: $disk, volumeInGb: 0,
    ports: ["22/tcp"], env: {PUBLIC_KEY: $key, MAX_SECONDS: $max},
    dockerStartCmd: ["/opt/evo2ops/pod-start.sh"]}')
POD_ID=$(rp -X POST "$API/pods" -d "$BODY" | jq -r .id)
log "Pod $POD_ID created; waiting for the image pull and SSH port"
mark pod_created

for _ in $(seq 1 120); do
  POD=$(rp "$API/pods/$POD_ID")
  SSH_HOST=$(echo "$POD" | jq -r '.publicIp // empty')
  SSH_PORT=$(echo "$POD" | jq -r '.portMappings["22"] // empty')
  [[ -n $SSH_HOST && -n $SSH_PORT ]] && break
  sleep 15
done
[[ -n ${SSH_HOST:-} ]] || { log "Pod never exposed SSH"; exit 3; }
mark running
echo "$POD" | jq '{provider: "runpod", instance_type: .machine.gpuTypeId, gpu: .gpu, region: .machine.dataCenterId,
  instance_id: .id, image: .imageName, purchase_option: "on-demand", cost_per_hr: .costPerHr,
  adjusted_cost_per_hr: .adjustedCostPerHr, disk_gb: .containerDiskInGb, machine: .machine}' > "$OUT/instance.json"
SSH_USER=root
log "Pod at $SSH_HOST:$SSH_PORT"

wait_for_ssh
run_bundle direct
