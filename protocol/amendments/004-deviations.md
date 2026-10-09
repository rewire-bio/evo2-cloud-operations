# Amendment 4: deviations from the approved run plan

Date: 9 October 2026. Recorded after the recorded run (b75c67aa) and the methods review, which
listed these deviations as blocking until acknowledged. No workload, metric, tolerance or budget
changed.

## Deviations

1. **Attempt limits in the phased runs.** The protocol allows at most 2 attempts per platform per
   phase and says to stop a platform after two failed attempts. In the phased runs on
   9 October, P3 (Runpod H100) used 9 attempts, P2 (Google Cloud H100) 5 and P5 (Runpod L40S) 3.
   Most failures happened before any machine existed (Runpod API version, account credit, L40S
   capacity); P2 attempts 3 and 4 billed about 20 and 1 minutes of compute. P5 attempt 3 was
   launched after the run log had declared P5 unavailable for that phase, under amendment 3.
2. **"Each platform runs once."** The study ran a phased run, a run rejected by the harness
   (698234c1, coordinator changed analysis code mid-run), the recorded run (b75c67aa), an aborted
   reproduction (stopped before any output to finalise evidence files) and a reproduction. The
   owner approved the clean recorded run and the reproduction in conversation; this amendment
   records it.
3. **Evidence from non-recorded runs.** The paper uses the phased and rejected runs for three
   statements: bit-identical scores across runs, L40S throughput on US-TX-4 hosts (0.92 to 0.93
   windows per second), and the India and Texas placements. Each is attributed to its run, and
   the cross-run comparison is computed in `evidence/checks/verification.json`.
4. **Text revised after reproduction.** The manuscript, claims and README were revised in response
   to the methods review after the final reproduction started. No scientific input (code,
   configuration, data manifest, container) changed. The owner decided not to repeat the cloud
   reproduction for text-only changes, so the harness's manuscript-bound verification gate was
   not re-run.

## Acknowledgement

Acknowledged by Tim Richardson on 9 October 2026 (reply: "Amendments acknowledged"; on the
reproduction: "It's not worth doing a re-run just because of the text changes").
