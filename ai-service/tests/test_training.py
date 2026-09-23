from app.training import safe_slug, split_items


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
