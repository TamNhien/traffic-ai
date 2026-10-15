# Benchmark #64 · Session #191 — V0.5.91

Source: `traffic-ai-benchmark-64-session-191.zip`, verified checksum manifest and closed trace; uploaded still images in `camera_1(20261014-161915).rar`.

* Ground Truth 149, persisted AI 150, timecode matched 138, missed 11, extra 12; precision 92.00%, recall 92.62%, F1 92.31%. Direction mismatches 2, class mismatches 2.
* Verified comparator to benchmark #62: same source, line/ROI, fps, tolerance, GT and all 150 persisted crossing signatures. Changed events 0, recovered misses 0, removed extras 0.
* Missed at 59.446, 237.042, 289.824, 392.179, 397.288, 406.488, 525.210, 534.087 (bicycle), 591.091 (bicycle), 640.141, and 816.965 seconds.
* Extra at 54.296, 70.520, 292.324, 519.520, 631.992, 637.988, 638.120, 808.000, 811.640, 812.571, 815.248 and 882.290 seconds.
* Four missed mark diagnoses mention anchor span rejection; five extra AI events are tagged `rescued_gap_unmatched`. These are trace diagnoses, **not** verified labels about physical vehicle identity.
* Snapshot archive has 190 JPG frames, but not every error has a sufficiently close reference frame. Still-image proximity alone cannot establish a false positive, detection miss, or correct GT direction/class.

## V0.5.91 operator workflow

The `Benchmark Report` now has a compact review navigator after the score badges. Filters: all, missed, extra, or cases with temporal proximity/competition. Previous/Next seeks the existing benchmark video 0.4 seconds before the selected case and pauses playback; existing one-frame stepping and IN/OUT marking remain unchanged. No automatic GT mutation, event suppression, or benchmark rescore occurs.

Export complete evidence with `scripts/review-benchmark-errors.ps1`, and compare exports with `scripts/compare-benchmark-exports.ps1`. The navigator works from **current server report data**; it does not read the uploaded ZIP. For precision/recall improvements, adjudicate the vehicles on video and collect new replay evidence.
