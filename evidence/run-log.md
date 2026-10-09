# Run log

Chronological record of every launch, including failures. Times are UTC.

## 2026-10-09, phase 1 (P3, Runpod H100)

- 09:25. P3 attempts 1 and 2 failed before any pod existed: `POST https://rest.runpod.io/v1/pods`
  returned HTTP 500. No compute was billed. Cause: the launcher used Runpod REST API v1 with v1
  field names; Runpod's current API is v2 (`https://api.runpod.io/v2`, nested `gpu`, `disk`,
  `cmd`). The launcher was rewritten for v2 and now prints the API's error body.
- Known limitation of image `sha256:22970720`: the in-pod self-delete backstop in
  `container/pod-start.sh` calls the v1 endpoint and may not work. The launcher deletes the pod
  on exit, and pods were also checked through the Runpod console API after each run.
- 09:27. P3 attempts 3 and 4 (v2 launcher) reached the API and were refused with HTTP 402,
  "Your account balance is too low to rent a pod". No pod was created; no compute was billed.
- 09:29 and 09:31. P3 attempts 5 to 8 refused with HTTP 402 (balance too low). No pod created.
- 09:32 to 10:20. P3 attempt 9 (pod 6oa79ihlpmq4dl, H100 80GB HBM3, Secure Cloud, USD 3.99/h)
  completed W0 to W4. Pod deleted by the launcher at 10:20:04; confirmed absent via the Runpod API.
- 10:21. P5 attempts 1 and 2 refused with HTTP 400: "There are no longer any instances available
  with the requested specifications". No pod created. Secure Cloud L40S stock showed as
  unavailable on all host CUDA versions immediately afterwards. P5 is unavailable for this phase.
- 10:22 to 12:15. P5 attempt 3 (pod eq8fyz8grfp4kt, L40S, Secure Cloud, USD 1.09/h) completed
  W0 to W4. An L40S was available at relaunch, so the amendment 3 fallbacks were not used. Pod
  deleted by the launcher at 12:15:08; confirmed absent via the Runpod API.
- 12:15. P2 attempt 1 launched: a3-highgpu-1g Spot, us-central1-a, Deep Learning VM family
  common-cu129-ubuntu-2204-nvidia-580 (the cu128/570 family named in the first launcher version
  no longer exists). H100 Spot quota of 1 in us-central1 was requested and granted the same day.
- 12:15 and 12:17. P2 attempts 1 and 2 got Spot capacity in us-central1-a but stopped within a
  minute: "Docker is not installed on this image". The CUDA 12.9 Deep Learning VM ships the NVIDIA
  driver without Docker. Both VMs and firewall rules were deleted by the launcher (confirmed by
  listing). remote-run.sh now installs docker.io and the NVIDIA container toolkit when missing
  and records the install time. Billed time for the two attempts: under 2 minutes each.
- 12:21 to 12:44. P2 attempts 3 and 4 installed docker.io (29.1.3) but failed installing
  nvidia-container-toolkit 1.20.1: the image holds nvidia-container-toolkit-base and
  libnvidia-container-tools at 1.19.1. Attempt 3 ran about 20 minutes before failing; attempt 4
  about 1 minute. VMs and firewall rules deleted by the launcher. remote-run.sh now installs the
  toolkit at the version already on the image, and adds NVIDIA's apt source only if absent.
- 12:52 to 13:47. P2 attempt 5 (a3-highgpu-1g Spot, us-central1-a, image
  common-cu129-ubuntu-2204-nvidia-580-v20261001) completed W0 to W4. Docker install took 457 s and
  the image pull 587 s. VM and firewall rule deleted by the launcher; confirmed by listing.
  Spot list price at run time: USD 6.24/h plus USD 0.05/h disk (Cloud Billing Catalog API).

## 2026-10-09, clean recorded run

- Phased results moved to `results/phased-20261009/` and kept. Configuration changes since the
  amendment 3 approval were operational only (Google Cloud zones limited to us-central1, where
  the H100 Spot quota was granted). Tim Richardson approved a clean run of P2, P3 and P5 from one
  revision followed by an independent reproduction (reply: "Yes please").
