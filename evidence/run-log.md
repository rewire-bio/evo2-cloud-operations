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
