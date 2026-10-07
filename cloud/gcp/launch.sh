#!/usr/bin/env bash
# Run the Evo 2 workloads on one Compute Engine GPU VM, copy results back, and delete it.
#
# Required environment:
#   PLATFORM_ID     e.g. P2
#   MACHINE_TYPE    e.g. a3-highgpu-1g (1 x H100 80 GB; Spot or Flex-start only)
#   GCP_PROJECT     project with billing and GPU quota
#   GCP_ZONES       space-separated zones to try, e.g. "us-central1-a us-central1-c"
#   IMAGE_REF, BUNDLE, OUT, CODE_SHA256 as for the AWS launcher
# Optional: PROVISIONING (default SPOT), MAX_HOURS (default 3), DISK_GB (default 200)
set -euo pipefail
source "$(dirname "$0")/../common.sh"

PROVISIONING=${PROVISIONING:-SPOT}
MAX_HOURS=${MAX_HOURS:-3}
DISK_GB=${DISK_GB:-200}
NAME="evo2ops-$(lower "$PLATFORM_ID")-$(date -u +%Y%m%d%H%M%S)"
mkdir -p "$OUT"
KEY="$OUT/.ssh-key"
gc() { gcloud --project "$GCP_PROJECT" --quiet "$@"; }

ZONE="" FIREWALL=""
cleanup() {
  set +e
  if [[ -n $ZONE ]]; then
    log "Deleting $NAME"
    gc compute instances delete "$NAME" --zone "$ZONE" >/dev/null 2>&1
    mark terminated
  fi
  [[ -n $FIREWALL ]] && gc compute firewall-rules delete "$FIREWALL" >/dev/null 2>&1
  rm -f "$KEY" "$KEY.pub"
}
trap cleanup EXIT

# 1. One-off SSH key, passed in instance metadata, and a firewall rule for this machine's IP only.
new_ssh_key
MY_IP=$(curl -fsS https://checkip.amazonaws.com)
FIREWALL="$NAME-ssh"
gc compute firewall-rules create "$FIREWALL" --network default --direction INGRESS \
  --allow tcp:22 --source-ranges "$MY_IP/32" --target-tags "$NAME" >/dev/null

# 2. Launch on a Deep Learning VM image (NVIDIA driver, Docker, NVIDIA container toolkit).
#    The A3 machine type includes its GPU. --max-run-duration deletes the VM after MAX_HOURS.
IMAGE_FAMILY=${IMAGE_FAMILY:-common-cu128-ubuntu-2204-nvidia-570}
mark launch_requested
for candidate in $GCP_ZONES; do
  if gc compute instances create "$NAME" --zone "$candidate" \
      --machine-type "$MACHINE_TYPE" \
      --provisioning-model "$PROVISIONING" --instance-termination-action DELETE \
      --max-run-duration "${MAX_HOURS}h" --maintenance-policy TERMINATE \
      --image-family "$IMAGE_FAMILY" --image-project deeplearning-platform-release \
      --boot-disk-size "${DISK_GB}GB" --boot-disk-type pd-ssd \
      --metadata "install-nvidia-driver=True,ssh-keys=evo2ops:$(cat "$KEY.pub")" \
      --tags "$NAME" --labels project=evo2-cloud-operations \
      --no-service-account --no-scopes >/dev/null 2>"$OUT/create.err"; then
    ZONE=$candidate
    break
  fi
  log "Could not create in $candidate: $(grep -m1 -i error "$OUT/create.err" || tail -1 "$OUT/create.err")"
done
[[ -n $ZONE ]] || { log "No zone had capacity for $MACHINE_TYPE"; exit 3; }
mark running
IP=$(gc compute instances describe "$NAME" --zone "$ZONE" --format 'value(networkInterfaces[0].accessConfigs[0].natIP)')
SOURCE_IMAGE=$(gc compute disks describe "$NAME" --zone "$ZONE" --format 'value(sourceImage)')
cat > "$OUT/instance.json" <<EOF
{"provider": "gcp", "instance_type": "$MACHINE_TYPE", "region": "${ZONE%-*}", "zone": "$ZONE",
 "instance_id": "$NAME", "image": "$SOURCE_IMAGE", "purchase_option": "$(lower "$PROVISIONING")", "disk_gb": $DISK_GB}
EOF
log "$NAME running in $ZONE at $IP"

SSH_USER=evo2ops SSH_HOST=$IP SSH_PORT=22

# 3. The Deep Learning VM installs its driver on first boot; wait for nvidia-smi before running.
wait_for_ssh
for _ in $(seq 1 60); do ssh_cmd nvidia-smi >/dev/null 2>&1 && break; sleep 10; done
mark gpu_ready
run_bundle docker
