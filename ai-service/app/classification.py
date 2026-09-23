from __future__ import annotations

from collections import defaultdict, deque


class TrackLabelSmoother:
    def __init__(self, history: int = 24) -> None:
        self.history = max(3, history)
        self._samples: dict[int, deque[tuple[str, float]]] = defaultdict(lambda: deque(maxlen=self.history))

    def update(self, track_id: int, label: str, confidence: float) -> None:
        self._samples[int(track_id)].append((str(label), float(confidence)))

    def evidence(self, track_id: int) -> tuple[dict[str, float], dict[str, int]]:
        samples = self._samples.get(int(track_id))
        scores: dict[str, float] = defaultdict(float)
        hits: dict[str, int] = defaultdict(int)
        if not samples:
            return {}, {}
        for age, (label, confidence) in enumerate(reversed(samples)):
            recency = 0.965 ** age
            scores[label] += (max(confidence, 0.01) ** 2) * recency
            hits[label] += 1
        return dict(scores), dict(hits)

    def stable_label(self, track_id: int, fallback: str) -> tuple[str, float, int]:
        scores, hits = self.evidence(track_id)
        if not scores:
            return fallback, 0.0, 0
        label = max(scores, key=lambda item: (scores[item], hits.get(item, 0)))
        total = sum(scores.values()) or 1.0
        return label, scores[label] / total, hits.get(label, 0)


class VehicleClassPolicy:
    """Conservative traffic-class policy for Vietnamese road scenes.

    The COCO detector can flip motorcycle/bicycle and bus/truck on overhead
    footage. Bicycle is therefore accepted only with repeated strong evidence;
    ambiguous two-wheelers fall back to motorcycle instead of creating false
    bicycle counts. Heavy vehicles prefer a preloaded crossing refiner when the
    temporal vote is uncertain.
    """

    def __init__(self, bicycle_certainty: float = 0.76, bicycle_hits: int = 4) -> None:
        self.bicycle_certainty = float(bicycle_certainty)
        self.bicycle_hits = int(bicycle_hits)

    def final_label(
        self,
        current_label: str,
        stable_label: str,
        certainty: float,
        hits: int,
        refined: tuple[str, float] | None = None,
    ) -> tuple[str, float]:
        refined_label, refined_conf = refined if refined is not None else (None, 0.0)
        base_conf = float(certainty)

        if stable_label in {"bicycle", "motorcycle"} or current_label in {"bicycle", "motorcycle"}:
            bicycle_ok = (
                stable_label == "bicycle"
                and hits >= self.bicycle_hits
                and certainty >= self.bicycle_certainty
                and refined_label == "bicycle"
                and refined_conf >= 0.52
            )
            if bicycle_ok:
                return "bicycle", max(base_conf, refined_conf)
            # Strongly bias ambiguous powered two-wheel traffic to motorcycle.
            return "motorcycle", max(base_conf, refined_conf if refined_label == "motorcycle" else 0.0)

        if stable_label in {"car", "bus", "truck"} or current_label in {"car", "bus", "truck"}:
            if refined_label in {"car", "bus", "truck"}:
                if certainty < 0.78 or hits < 4 or refined_label == stable_label:
                    if refined_conf >= 0.42:
                        return refined_label, max(base_conf, refined_conf)
                if refined_conf >= 0.62:
                    return refined_label, max(base_conf, refined_conf)
            return stable_label if hits >= 2 else current_label, base_conf

        return stable_label or current_label or "other", base_conf
