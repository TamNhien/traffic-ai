from pathlib import Path

import app.training as training
from app.training import _candidate_changed_enough, _review_priority, purge_dataset, safe_slug, split_items


def test_safe_slug() -> None:
    assert safe_slug("Traffic Vietnam 01") == "traffic-vietnam-01"


def test_split_items_is_deterministic_and_complete() -> None:
    items = [f"frame_{i}.jpg" for i in range(100)]
    first = split_items(items, 0.70, 0.20, 2026)
    second = split_items(items, 0.70, 0.20, 2026)
    assert first == second
    assert len(first["train"]) == 70
    assert len(first["val"]) == 20
    assert len(first["test"]) == 10
    assert set(first["train"]) | set(first["val"]) | set(first["test"]) == set(items)
    assert not (set(first["train"]) & set(first["val"]))


def test_smart_frame_change_threshold() -> None:
    assert _candidate_changed_enough(0.020, 0.008)
    assert _candidate_changed_enough(0.008, 0.008)
    assert not _candidate_changed_enough(0.002, 0.008)


def test_review_priority_never_auto_accepts_two_wheelers() -> None:
    motorcycle = _review_priority([{"class_id": 0, "confidence": 0.98}])
    bicycle = _review_priority([{"class_id": 1, "confidence": 0.97}])
    clear_car = _review_priority([{"class_id": 2, "confidence": 0.91}])
    empty = _review_priority([])
    assert motorcycle["score"] >= 35 and not motorcycle["safe_auto_accept"]
    assert bicycle["score"] >= 35 and not bicycle["safe_auto_accept"]
    assert clear_car["safe_auto_accept"]
    assert empty["score"] >= 35 and not empty["safe_auto_accept"]


def test_purge_dataset_preserves_exported_models(tmp_path, monkeypatch) -> None:
    dataset_root = tmp_path / "datasets"
    training_root = tmp_path / "training-runs"
    model_root = tmp_path / "models"
    for root in (dataset_root, training_root, model_root):
        root.mkdir()
    monkeypatch.setattr(training, "DATASET_ROOT", dataset_root)
    monkeypatch.setattr(training, "TRAINING_ROOT", training_root)
    monkeypatch.setattr(training, "MODEL_ROOT", model_root)
    (dataset_root / "demo" / "raw").mkdir(parents=True)
    (dataset_root / "demo" / "raw" / "x.txt").write_text("x", encoding="utf-8")
    (training_root / "run-7" / "weights").mkdir(parents=True)
    (training_root / "run-7" / "weights" / "best.pt").write_bytes(b"run")
    exported = model_root / "traffic-ai-v059-run-7-best.pt"
    exported.write_bytes(b"exported")

    result = purge_dataset("demo", [7], True)

    assert result["removed_dataset"] is True
    assert result["removed_training_runs"] == [7]
    assert not (dataset_root / "demo").exists()
    assert not (training_root / "run-7").exists()
    assert exported.read_bytes() == b"exported"
