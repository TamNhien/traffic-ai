# Benchmark #80 / Session #207 — recovered and verified evidence

- Original export: 18,117-byte ZIP with `trace.available=false`, `reason=too_large` (no trace member).
- Camera RAR contained `session_207_benchmark-trace.jsonl` (413,128,306 raw bytes).
- Full trace recovered and independently compressed to 24,087,359 bytes (gzip); 23,650 sequential frames, terminal delivery footer, runtime **0.5.109**.
- The recovery result is a **derived evidence ZIP**, not a reissued certificate from the original running AI service. Five original source members (report, Ground Truth, events, session, config) are byte-for-byte unchanged. SHA-256 checksums are recorded in the derived manifest.
- Gate audit: 271,208 gate decision samples; GT **149**, AI **148**, matched **143**, missed **6**, extra **5**, F1 **96.2963%**.
- Five unmatched GT marks have near-gate geometric track observations, but these do not establish physical identity or justify automatic counting. One bicycle GT IN at 591.091 seconds has zero near-gate tracks, strict ROAD 0 and margin-eligible ROAD 1 around the target instant.
- At 237.042 and 406.488 seconds the closest persisted AI crossings have opposite directions to the GT marks; at 392.179 seconds there is a later rescued OUT event (393.3028 seconds) outside the configured 0.75-second matching window. These are review findings only, not evidence to shift clocks or reassign GT.
- This release changes **trace transport/recovery**, not crossing admission, vehicle classification or benchmarking scores.

## Verification procedure

Use the V0.5.110 recovery CLI (`scripts/recover-benchmark-trace.ps1`) to attach a closed trace from an exact matching camera RAR (requires 7-Zip), or an already extracted JSONL (`-TraceJsonl`). The CLI refuses mismatched sessions, incomplete trace files, incomplete frame sequences, corrupt benchmark manifests, oversized sources, and output overwrites. It never edits the original ZIP.

`audit-gate-coverage.ps1 -ExpectedSession 207 -RequireProvenance` was successful against the recovered ZIP. This proves the recovered trace conforms to the existing integrity and audit checks; it does not prove model improvement.
