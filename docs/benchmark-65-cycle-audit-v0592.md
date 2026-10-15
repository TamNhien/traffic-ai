# V0.5.92 · Benchmark #65 / Session #192 — Canonical vs Raw-ID Passage Audit

## Evidence

- Closed signed benchmark export: GT **149**, persisted AI **150**, time matches **138**, missed **11**, unmatched AI **12**, F1 **92.3%**.
- In the 12-second same-canonical-ID window, exactly **5 pairs** were found; **2 pairs** include at least one unmatched AI event. **3 pairs** show distinct raw ByteTrack IDs in stored nearby trace frames.
- Review priorities:
  - AI 13044 (IN 631.992s) → AI 13045 (OUT 637.988s), canonical ID **248105**; near-event **raw IDs changed**, both events unmatched GT.
  - AI 13077 (IN 811.640s) → AI 13079 (OUT 815.248s), canonical ID **345897**; **same raw ID** observed, both events unmatched GT.
- Other same-canonical passage pairs (not unmatched GT): AI **12992 → 12996** (8.570s), **12998 → 13000** (8.195s), **13030 → 13031** (7.041s).

## Why there is no automatic deletion

1. The project's counting semantics are **passage-based**, not unique-vehicle based. A motorcycle reversing direction and crossing again is a **valid new event**.
2. A canonical ID can represent an alias chain; a raw ID can also be reused. Neither proves the identity of a physical vehicle without visual evidence.
3. The RAR contains 190 snapshots but not the entire frame sequence. Several suspected GT timecodes do not have a still image at the exact crossing. Neighboring pedestrians and vehicles at ~638s and ~812s make time-only pairings unsafe.
4. Rejection of one candidate before a real-video GPU replay may turn an unmatched AI into a missed GT, decreasing recall.

## New operator workflow

- In **Benchmark Report**, expand **“Các lượt dùng chung tracking ID”** to jump to the two times of each candidate pair. No report or GT records are modified.
- Export the current benchmark ZIP, then run:

```powershell
.\scripts\audit-crossing-cycles.ps1 `
  -Export '.\traffic-ai-benchmark-65-session-192.zip' `
  -OutputDirectory '.\crossing-cycle-audit'
```

- Read `crossing-cycles.csv` or `.md` for the raw-ID evidence and pairing. Mark each candidate in your local review notes only after watching the original MP4. No changes to scoring or production counting thresholds in V0.5.92.

## Boundaries

This release modifies **audit tooling and read-only UX**, not detection/tracker/counting decisions. The previous score is a **baseline**, not an improved V0.5.92 result. To validate a counting adjustment, compare independent replays under the same GT fingerprint and source/geometry/model settings. The ZIP excludes video/model weights.
