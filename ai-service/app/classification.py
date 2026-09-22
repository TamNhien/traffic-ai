from __future__ import annotations

from collections import defaultdict, deque


class TrackLabelSmoother:
    """Stabilise the semantic class assigned to one ByteTrack ID.

    YOLO can alternate between bus/truck (or bicycle/motorcycle) on adjacent
    frames. Counting should use the accumulated evidence for the complete track
    instead of the class from a single crossing frame.
    """

    def __init__(self, history: int = 18) -> None:
        self.history = max(3, history)
        self._samples: dict[int, deque[tuple[str, float]]] = defaultdict(lambda: deque(maxlen=self.history))

    def update(self, track_id: int, label: str, confidence: float) -> None:
        self._samples[int(track_id)].append((str(label), float(confidence)))

    def stable_label(self, track_id: int, fallback: str) -> tuple[str, float, int]:
        samples = self._samples.get(int(track_id))
        if not samples:
            return fallback, 0.0, 0

        scores: dict[str, float] = defaultdict(float)
        hits: dict[str, int] = defaultdict(int)
        for label, confidence in samples:
            # Squared confidence gives repeated high-confidence observations more
            # influence than a single low-confidence class flip.
            scores[label] += max(confidence, 0.01) ** 2
            hits[label] += 1
        label = max(scores, key=lambda item: (scores[item], hits[item]))
        total = sum(scores.values()) or 1.0
        certainty = scores[label] / total
        return label, certainty, len(samples)
