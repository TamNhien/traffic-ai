"""V0.5.72: deterministic order is not a recall/precision threshold change."""
from app.dedup import stable_tracking_order, single_heavy_vehicle_plan


def test_v0572_permutations_preserve_identity_and_gate_schedule():
    objects = [
        (19, (400., 300., 460., 390.), 'motorcycle', .82),
        (7, (760., 190., 810., 295.), 'motorcycle', .69),
        (31, (500., 420., 620., 570.), 'truck', .75),
        (11, (600., 240., 660., 310.), 'bicycle', .91),
    ]
    expected = sorted((raw, rect) for raw, rect, _, _ in objects)
    for order in ([0, 1, 2, 3], [3, 1, 0, 2], [2, 0, 3, 1]):
        rows = [objects[i] for i in order]
        ids = [r[0] for r in rows]
        rects = [r[1] for r in rows]
        kept, aliases, removed = single_heavy_vehicle_plan(
            rects, [r[2] for r in rows], [r[3] for r in rows], .68
        )
        result = stable_tracking_order(kept, ids, rects)
        assert [(ids[i], rects[i]) for i in result] == expected
        assert len(result) == len(objects) and not aliases and removed == 0


def test_v0572_suppressed_duplicate_is_not_reinserted_by_sort():
    rects = [(100., 100., 250., 300.), (101., 99., 251., 300.), (750., 400., 810., 480.)]
    labels = ['truck', 'car', 'motorcycle']
    ids = [75, 5, 8]
    kept, aliases, suppressed = single_heavy_vehicle_plan(rects, labels, [.94, .80, .92], .68)
    ordered = stable_tracking_order(kept, ids, rects)
    assert suppressed == 1 and kept == [0, 2]
    assert [ids[i] for i in ordered] == [8, 75]
    assert aliases == {0: [1]}


def test_v0572_tied_ids_stable_by_geometry():
    assert stable_tracking_order([2, 0, 1], [4, 4, 4], [
        (50., 0., 60., 10.), (10., 0., 20., 10.), (30., 0., 40., 10.)
    ]) == [1, 2, 0]


def test_v0572_same_confidence_semantic_alias_invariant_to_yolo_box_order():
    rows = [('truck', .9, (100., 100., 200., 220.)),
            ('car', .9, (101., 101., 201., 221.))]
    for permutation in (rows, list(reversed(rows))):
        keep, aliases, suppressed = single_heavy_vehicle_plan(
            [row[2] for row in permutation],
            [row[0] for row in permutation],
            [row[1] for row in permutation], .68
        )
        assert suppressed == 1 and len(aliases) == 1
        assert [permutation[i][0] for i in keep] == ['car']
