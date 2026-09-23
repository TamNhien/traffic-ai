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

    Motorcycle/bicycle confusion is asymmetric in typical road footage: a false
    bicycle label is much more common than a real bicycle having many repeated,
    high-confidence bicycle observations. V0.5.8 therefore requires strong
    temporal evidence before showing or persisting `bicycle`; ambiguous two-wheel
    tracks remain `motorcycle`. A very strong primary-model vote can confirm a
    bicycle even when the optional crossing refiner is skipped to protect FPS.
    """

    def __init__(
        self,
        bicycle_certainty: float = 0.80,
        bicycle_hits: int = 5,
        strong_bicycle_certainty: float = 0.90,
        strong_bicycle_hits: int = 8,
    ) -> None:
        self.bicycle_certainty = float(bicycle_certainty)
        self.bicycle_hits = int(bicycle_hits)
        self.strong_bicycle_certainty = float(strong_bicycle_certainty)
        self.strong_bicycle_hits = int(strong_bicycle_hits)

    def display_label(
        self,
        current_label: str,
        stable_label: str,
        certainty: float,
        hits: int,
        current_confidence: float,
    ) -> str:
        if stable_label in {"bicycle", "motorcycle"} or current_label in {"bicycle", "motorcycle"}:
            bicycle_ok = (
                stable_label == "bicycle"
                and current_label == "bicycle"
                and hits >= self.bicycle_hits
                and certainty >= self.bicycle_certainty
                and current_confidence >= 0.28
            )
            return "bicycle" if bicycle_ok else "motorcycle"
        return stable_label if hits >= 2 else current_label

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
            strong_primary_bicycle = (
                stable_label == "bicycle"
                and hits >= self.strong_bicycle_hits
                and certainty >= self.strong_bicycle_certainty
            )
            refined_bicycle = (
                stable_label == "bicycle"
                and hits >= self.bicycle_hits
                and certainty >= self.bicycle_certainty
                and refined_label == "bicycle"
                and refined_conf >= 0.52
            )
            if strong_primary_bicycle or refined_bicycle:
                return "bicycle", max(base_conf, refined_conf)
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
