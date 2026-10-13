# Session #187 — Ground Truth / trace audit (V0.5.86)

Benchmark #61 from the user-provided `traffic-ai-benchmark-61-session-187(1).zip` (report, GT, AI events and gzip trace). The offline forensics tool validated manifest and trace SHA256; the 190 JPEG files in `camera_1(20261013-135241)(1).rar` were accessible through libarchive. **No model inference or source-video replay was performed.**

| Metric (V0.5.85 baseline) | Value |
|---|---:|
| GT | 149 |
| AI persisted | 150 |
| Matched by timestamp | 138 |
| Missed GT | 11 |
| Unmatched AI | 12 |
| Wrong direction/class among matches | 2 / 2 |
| Precision / Recall / F1 | 92.0% / 92.6% / 92.3% |

The 12 unmatched events comprise 5 direct, 5 rescued-gap, and 2 interpolated events. Four missed marks have a persisted AI event nearby that global temporal assignment already matched to a different GT mark; this is not proof of an actual missed physical crossing. Two of the wrong direction comparisons are near 0.16 s and 58.984 s; inspect camera video before modifying direction code or GT.

**Frame 7243 / 289.7 s:** a green-shirted person pushing a bicycle is visible alongside a separate motorcycle near the gate. Timestamp-only pairing GT bicycle to motorcycle track 25767 does not establish that the rider was misclassified: a bicycle may simply have lacked its own tracked object. Require visual instance matching, ideally with a distinct object reference, before changing the classification logic.

**Frame 16050 / 642 s:** an enclosed delivery van is visibly tracked as TRUCK #254023. The existing GT car mark at 641.981 s should be *reviewed by the annotator* under the project's convention “vans carrying goods are Xe tải”. Do not automatically relabel GT. **Frame 22059 / 882.3 s:** a similar delivery van is tracked as truck #286434, but its event is unmatched within the benchmark's 0.75-second tolerance. This is a time/mark review case, not proof of a second car/truck misclassification.

**Fix in V0.5.86:** new two-wheel visible-incumbent reservation prevents a newcomer raw token from stealing a still-visible older identity after a 4–12-frame gap. The guard is source-frame evidence only, independent of GT and clock alignment, preserving 0–3-frame legacy behavior, valid recovery without an incumbent, and 4-wheel semantics. Whether it reduces extra events at 637–638 s or 808–815 s can ONLY be evaluated by a fresh full clip replay on the user's computer.
