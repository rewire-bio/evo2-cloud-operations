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
