# Benchmark #62 / Session #188 — V0.5.87 forensic comparison

Actual evidence provided: `traffic-ai-benchmark-62-session-188.zip`, prior `traffic-ai-benchmark-61-session-187(1).zip`, and `camera_1(20261013-153523).rar`.

Both ZIPs verified with source-integrity gate and SHA-256 manifests; 149 GT mark scoring signatures and 150 AI recorded crossing signatures are **identical** across #61 and #62 after removing session/event IDs and wall-clock metadata. Both use `clip1.mp4`, 25 FPS, 946-second video, same geometry, GT, model 47 and ±0.75 second matching tolerance. No drift in F1 (92.3077%), Precision (92%), Recall (92.6174%), missed (11), extra (12), direction mismatches (2), class mismatches (2). Session #188 worker proposed 191, DB persisted 150; 41 backend dedups, 35 human guard rejects. These counters do not prove that 41 or 35 actual vehicles were lost.

11 unmatched GT: 4 anchor-span, 1 center-only, 2 confirmation, 1 cooldown, 1 gate miss, 2 near without span (diagnosis categories are not guaranteed real cause). 12 unmatched AI: 5 direct, 5 rescued gap, 2 interpolated. Temporal audit says 4 missed marks have a claimed nearby persisted event which matched another GT, and 2 extra AI events are near GT already matched to another AI; **do not merge or delete by time alone.**

RAR frame samples at 12989/12993 (519s), 15954 (638s), 20201 (808s), 20292/20381/20421 (811–817s) show crowded camera observations; a timestamp collision is not physical duplicate evidence. At 7243 the bicycle context is ambiguous; at 16050 and 22059 an enclosed delivery van appears near the gate. The GT vehicle labels were not modified. Model weights/original MP4 were not rerun; these are comparisons of past completed sessions.

V0.5.87 adds a read-only verified comparison CLI and frontend temporal-competition explanation that was incorrectly hidden when GT and AI totals differed. The counting algorithm is unchanged, so measured AI performance cannot be claimed to improve until a real full clip inference replay.
