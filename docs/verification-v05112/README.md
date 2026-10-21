# Traffic AI V0.5.112 — Verification and review flow

- Baseline: V0.5.111, Benchmark #81 / Session #208.
- 6 GT misses and 5 unmatched AI events remain; the new review tool does not
  change counts, routes or model inference.
- Run `scripts/export-benchmark-review-frames.ps1` with the verified ZIP and
  original `.mp4` to export time-aligned frames with the benchmark line.
- Metadata guards: session, certified trace, video FPS, frame count, aspect.
- All frame annotations require manual review. The exported images are **not**
  pre-labeled YOLO positives or negatives.
- Version head: `0126_review_frames_v05112`.
