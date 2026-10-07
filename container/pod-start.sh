#!/usr/bin/env bash
# Start command for RunPod pods: accept the launcher's SSH key, then idle until
# the launcher deletes the pod. As a backstop, the pod deletes itself after
# MAX_SECONDS using the pod-scoped key RunPod injects, when one is present.
set -euo pipefail

mkdir -p /root/.ssh
echo "${PUBLIC_KEY:?PUBLIC_KEY is required}" > /root/.ssh/authorized_keys
chmod 700 /root/.ssh && chmod 600 /root/.ssh/authorized_keys
# RunPod passes pod variables to the start process only; make them visible to SSH sessions.
env | grep -E '^(RUNPOD_|IMAGE_)' | sed 's/^/export /' > /etc/profile.d/runpod-env.sh || true
/usr/sbin/sshd

sleep "${MAX_SECONDS:-10800}"
if [[ -n "${RUNPOD_API_KEY:-}" && -n "${RUNPOD_POD_ID:-}" ]]; then
  curl -fsS -X DELETE -H "Authorization: Bearer ${RUNPOD_API_KEY}" \
    "https://rest.runpod.io/v1/pods/${RUNPOD_POD_ID}" || true
fi
exit 0
