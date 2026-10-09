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
- 14:19 to 16:14. Recorded run 698234c1 (harness). P3 and P5 completed W0 to W4. P2 attempts 1 and
  2 completed W0 to W3 but W4 failed in both: the new process saw "No CUDA GPUs are available"
  while the first process had used the GPU normally. Probable cause (not confirmed; VMs deleted):
  a systemd daemon-reload on the host revoking the container's GPU device access, a documented
  NVIDIA container toolkit issue. The harness then rejected the run, correctly, with "Experiment
  modified its scientific inputs": the coordinator had committed changes to scripts/ (analysis
  and paper build) while the run was in progress. The run's outputs are kept in .research; the
  run is not used as the recorded result.
- Fix for the next run: remote-run.sh pauses apt timers and attaches the GPU through CDI
  (`--device nvidia.com/gpu=all`) when available. No study files will be edited during runs.
- 16:15 to 19:44. Recorded run b75c67aa (harness status: completed). P2 attempt 1 completed W0 to
  W4, including W4, with the GPU attached through CDI. P3 attempt 1 completed W0 to W4. P5 attempt
  1 failed at 16:59 when the SSH session from the coordinator's laptop dropped ("Broken pipe" from
  the workload's progress output); P5 attempt 2 completed W0 to W4 on a slower L40S host
  (0.61 windows per second, against 0.93 on the host used earlier the same day).
- All three platforms' BRCA1 scores in the recorded run were bit-identical to the phased run and
  to the rejected run 698234c1, for every variant (maximum absolute difference 0.0 per platform).
- 19:39. A first reproduction attempt was stopped at 19:45 by the coordinator, before any
  workload output, because evidence/claims.json was still empty and the harness binds a
  reproduction to every tracked file. All pods and VMs were deleted by their launchers; one
  orphaned firewall rule (evo2ops-p2-20261009193951-ssh) was deleted manually. The claims file,
  run log, paper and README were then finalised in one commit before the reproduction restarted.
- Known launcher weakness: workloads run in the foreground of the SSH session, so a dropped
  connection kills them. Running them detached on the machine would remove this failure mode.
- 19:51 to 21:45. Reproduction 30e7ae49 (harness status: completed) from a clean checkout of
  64de22d on fresh machines: P2 us-central1-c, P3 AP-IN-1 (Runpod again chose India), P5 US-MO-1
  at 0.91 windows per second. Every platform completed W0 to W4 on its first attempt.
  results.json was identical to the recorded run, and per-variant scores and exon probabilities
  were bit-identical on every platform (evidence/checks/verification.json).
- Methods review (worker f0eb685d): verdict fail on reporting issues; text, claims and
  documentation corrected afterwards without changing scientific inputs (reviews/, amendment 4).
- Total cloud spend for the study: USD 21.56 on Runpod (billing API, 9 October) and about USD 27
  on Google Cloud (4.3 billed VM hours at USD 6.29/h Spot list price).
