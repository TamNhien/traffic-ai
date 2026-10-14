# Session #190 · Benchmark #63 · V0.5.90

- The **attached benchmark #63 ZIP** was exported BEFORE the 149 GT marks were copied: its `ground_truth_total` is **0** and `report_readiness.scoring_available=false`.
- The **later screenshot** shows benchmark #63 AFTER GT copy/reconcile: **149 GT, 150 AI, 138 matched, 11 missed, 12 extra, F1 92.3%**. The screenshot alone does not update an already-downloaded ZIP.
- Verified baseline benchmark #62 and pre-GT #63 archives: all **150 AI crossing signatures are identical** when compared independent of database IDs and wall clock receipts; 0 removed / 0 added.
- `scripts/compare-benchmark-exports.py` now permits **AI-only** comparison with one or two unscored exports. It **never** emits accuracy deltas unless BOTH archives have completed matching GT sets and the same tolerance.
- The frontend clone and export notifications instruct users to re-download ZIP after GT is copied/reconciled.
- This release changes **diagnostics and data export guidance only**. No changes to model weights, tracking, crossing algorithm, or false positive filtering; no measured F1 gain.
- To compare scored accuracy for Session #190, copy GT (already shown in screenshot), press **Tải hồ sơ benchmark** again, and use the NEW ZIP. Reusing old #63 ZIP cannot establish GT identity.

## Forensics review queue
Run `scripts/review-benchmark-errors.ps1` with the **scored** #62 ZIP to export 23 missing/extra review timecodes as CSV, JSON and Markdown. Candidate time neighbors are navigation aids, never grounds for automatic event suppression.
