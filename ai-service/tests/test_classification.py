from app.classification import TrackLabelSmoother, VehicleClassPolicy


def test_track_label_smoothing_resists_one_frame_bus_truck_flip() -> None:
    smoother = TrackLabelSmoother(history=10)
    for confidence in (0.82, 0.88, 0.79, 0.84):
        smoother.update(1, "truck", confidence)
    smoother.update(1, "bus", 0.91)
    label, certainty, hits = smoother.stable_label(1, "bus")
    assert label == "truck"
    assert hits == 4
    assert certainty > 0.6


def test_bicycle_requires_repeated_strong_bicycle_evidence() -> None:
    policy = VehicleClassPolicy(bicycle_certainty=0.75, bicycle_hits=4)
    label, _ = policy.final_label("bicycle", "bicycle", 0.82, 5, ("bicycle", 0.71))
    assert label == "bicycle"


def test_ambiguous_bicycle_defaults_to_motorcycle() -> None:
    policy = VehicleClassPolicy(bicycle_certainty=0.75, bicycle_hits=4)
    label, _ = policy.final_label("bicycle", "bicycle", 0.62, 2, ("motorcycle", 0.58))
    assert label == "motorcycle"


def test_heavy_vehicle_refiner_can_correct_bus_truck_flip() -> None:
    policy = VehicleClassPolicy()
    label, confidence = policy.final_label("bus", "bus", 0.61, 3, ("truck", 0.73))
    assert label == "truck"
    assert confidence >= 0.73


def test_display_suppresses_weak_bicycle_flip_as_motorcycle() -> None:
    policy = VehicleClassPolicy(bicycle_certainty=0.80, bicycle_hits=5)
    assert policy.display_label("bicycle", "bicycle", 0.64, 2, 0.77) == "motorcycle"


def test_display_allows_repeated_strong_bicycle_evidence() -> None:
    policy = VehicleClassPolicy(bicycle_certainty=0.80, bicycle_hits=5)
    assert policy.display_label("bicycle", "bicycle", 0.91, 7, 0.84) == "bicycle"


def test_very_strong_primary_bicycle_can_survive_without_refiner() -> None:
    policy = VehicleClassPolicy(strong_bicycle_certainty=0.90, strong_bicycle_hits=8)
    label, _ = policy.final_label("bicycle", "bicycle", 0.94, 10, None)
    assert label == "bicycle"


def test_target_refiner_ignores_high_confidence_neighbor() -> None:
    from app.classification import RefineCandidate, select_target_refinement

    target = (40.0, 40.0, 140.0, 180.0)
    candidates = [
        # Unrelated parked motorcycle in the same expanded crop.
        RefineCandidate("motorcycle", 0.96, (170.0, 45.0, 250.0, 170.0)),
        # Lower-confidence target-matched bicycle.
        RefineCandidate("bicycle", 0.66, (46.0, 48.0, 136.0, 176.0)),
    ]
    match = select_target_refinement(target, candidates)
    assert match is not None
    assert match.label == "bicycle"
    assert match.confidence == 0.66


def test_refiner_can_rescue_bicycle_from_motorcycle_biased_primary() -> None:
    policy = VehicleClassPolicy(bicycle_refine_override_conf=0.90)
    label, confidence = policy.final_label(
        "motorcycle", "motorcycle", 0.96, 18, ("bicycle", 0.93)
    )
    assert label == "bicycle"
    assert confidence >= 0.96


def test_v0533_single_medium_bicycle_refiner_no_longer_flips_scooter() -> None:
    policy = VehicleClassPolicy(bicycle_refine_override_conf=0.90)
    label, _ = policy.final_label(
        "motorcycle", "motorcycle", 0.96, 18, ("bicycle", 0.72)
    )
    assert label == "motorcycle"


def test_target_refiner_can_promote_small_car_shaped_truck() -> None:
    policy = VehicleClassPolicy(truck_refine_override_conf=0.48)
    label, confidence = policy.final_label(
        "car", "car", 0.94, 24, ("truck", 0.53)
    )
    assert label == "truck"
    assert confidence >= 0.94


def test_weak_truck_refiner_does_not_override_stable_car() -> None:
    policy = VehicleClassPolicy(truck_refine_override_conf=0.48)
    label, _ = policy.final_label("car", "car", 0.94, 24, ("truck", 0.31))
    assert label == "car"


def test_target_refiner_stays_inside_target_vehicle_family() -> None:
    from app.classification import RefineCandidate, select_target_refinement

    target = (40.0, 40.0, 180.0, 190.0)
    candidates = [
        RefineCandidate("motorcycle", 0.97, (45.0, 45.0, 175.0, 185.0)),
        RefineCandidate("truck", 0.56, (48.0, 47.0, 178.0, 188.0)),
    ]
    match = select_target_refinement(target, candidates, target_family="four-wheel")
    assert match is not None
    assert match.label == "truck"


def test_target_refiner_rejects_unrelated_neighbor_only() -> None:
    from app.classification import RefineCandidate, select_target_refinement

    target = (40.0, 40.0, 140.0, 180.0)
    candidates = [RefineCandidate("motorcycle", 0.99, (180.0, 40.0, 260.0, 170.0))]
    assert select_target_refinement(target, candidates, target_family="two-wheel") is None


def test_v0527_consensus_requires_distinct_frames() -> None:
    from app.classification import RefineEvidenceAccumulator

    evidence = RefineEvidenceAccumulator(history_frames=120)
    evidence.update(7, 100, "bicycle", 0.55, "domain")
    evidence.update(7, 100, "bicycle", 0.65, "general")
    hits, fused, strongest = evidence.support(7, 100, "bicycle")
    assert hits == 1
    assert strongest == 0.65
    assert fused == 0.65
    assert evidence.minority_consensus(7, 100, "motorcycle", min_hits=2, bicycle_confidence=0.60) is None


def test_v0527_repeated_low_bicycle_evidence_can_rescue_motorcycle_track() -> None:
    from app.classification import RefineEvidenceAccumulator

    evidence = RefineEvidenceAccumulator(history_frames=120)
    evidence.update(11, 200, "bicycle", 0.38, "general")
    evidence.update(11, 210, "bicycle", 0.39, "general")
    result = evidence.minority_consensus(
        11, 210, "motorcycle", min_hits=2, bicycle_confidence=0.60
    )
    assert result is not None
    assert result[0] == "bicycle"
    assert result[1] >= 0.60


def test_v0527_repeated_low_truck_evidence_can_rescue_car_track() -> None:
    from app.classification import RefineEvidenceAccumulator

    evidence = RefineEvidenceAccumulator(history_frames=120)
    evidence.update(12, 300, "truck", 0.31, "domain")
    evidence.update(12, 320, "truck", 0.35, "general")
    result = evidence.minority_consensus(
        12, 320, "car", min_hits=2, truck_confidence=0.52
    )
    assert result is not None
    assert result[0] == "truck"
    assert result[1] >= 0.52


def test_v0527_single_weak_truck_guess_does_not_promote_car() -> None:
    from app.classification import RefineEvidenceAccumulator

    evidence = RefineEvidenceAccumulator(history_frames=120)
    evidence.update(13, 400, "truck", 0.44, "general")
    assert evidence.minority_consensus(13, 400, "car", min_hits=2, truck_confidence=0.52) is None


def test_v0529_bicycle_consensus_requires_extra_distinct_frame_when_configured() -> None:
    from app.classification import RefineEvidenceAccumulator

    evidence = RefineEvidenceAccumulator(history_frames=120)
    evidence.update(77, 100, "bicycle", 0.48, "general")
    evidence.update(77, 110, "bicycle", 0.49, "domain")
    assert evidence.minority_consensus(
        77,
        110,
        "motorcycle",
        min_hits=2,
        bicycle_confidence=0.60,
        bicycle_min_hits=3,
        bicycle_margin=0.08,
        bicycle_min_strongest=0.34,
    ) is None
    evidence.update(77, 120, "bicycle", 0.50, "general")
    result = evidence.minority_consensus(
        77,
        120,
        "motorcycle",
        min_hits=2,
        bicycle_confidence=0.60,
        bicycle_min_hits=3,
        bicycle_margin=0.08,
        bicycle_min_strongest=0.34,
    )
    assert result is not None
    assert result[0] == "bicycle"


def test_v0529_bicycle_consensus_rejects_when_motorcycle_refiner_support_is_similar() -> None:
    from app.classification import RefineEvidenceAccumulator

    evidence = RefineEvidenceAccumulator(history_frames=120)
    for frame, bike, moto in [(100, 0.42, 0.46), (110, 0.44, 0.47), (120, 0.45, 0.48)]:
        evidence.update(88, frame, "bicycle", bike, "domain")
        evidence.update(88, frame, "motorcycle", moto, "general")
    assert evidence.minority_consensus(
        88,
        120,
        "motorcycle",
        min_hits=2,
        bicycle_confidence=0.60,
        bicycle_min_hits=3,
        bicycle_margin=0.08,
        bicycle_min_strongest=0.34,
    ) is None


def test_v0530_truck_semantic_lock_holds_through_closeup_car_flip() -> None:
    from app.classification import TruckSemanticLock

    lock = TruckSemanticLock(ttl_frames=450, min_refiner_hits=2, min_refiner_confidence=0.62)
    assert lock.observe(286423, 21815, stable_label="truck", certainty=0.93, hits=6) == ("truck", 0.93)
    # Same physical van is COCO-car shaped 262 frames later while crossing.
    assert lock.resolve(286423, 22077, "car") == ("truck", 0.93)


def test_v0530_truck_semantic_lock_requires_durable_evidence() -> None:
    from app.classification import TruckSemanticLock

    lock = TruckSemanticLock(ttl_frames=450, min_refiner_hits=2, min_refiner_confidence=0.62)
    assert lock.observe(7, 100, stable_label="car", certainty=0.95, hits=20, refiner_hits=1, refiner_confidence=0.61) is None
    assert lock.resolve(7, 120, "car") is None


def test_v0533_bicycle_consensus_prefers_source_diversity() -> None:
    from app.classification import RefineEvidenceAccumulator

    evidence = RefineEvidenceAccumulator(history_frames=120)
    for frame, conf in [(100, 0.50), (110, 0.52), (120, 0.54), (130, 0.56)]:
        evidence.update(901, frame, "bicycle", conf, "general")
    assert evidence.minority_consensus(
        901, 130, "motorcycle", min_hits=2, bicycle_confidence=0.78,
        bicycle_min_hits=4, bicycle_margin=0.16, bicycle_min_strongest=0.45,
        bicycle_min_sources=2, bicycle_single_source_strong=0.88,
    ) is None

    evidence.update(901, 140, "bicycle", 0.58, "domain")
    result = evidence.minority_consensus(
        901, 140, "motorcycle", min_hits=2, bicycle_confidence=0.78,
        bicycle_min_hits=4, bicycle_margin=0.16, bicycle_min_strongest=0.45,
        bicycle_min_sources=2, bicycle_single_source_strong=0.88,
    )
    assert result is not None
    assert result[0] == "bicycle"


def test_v0533_very_strong_single_refiner_can_rescue_repeated_clear_bicycle() -> None:
    from app.classification import RefineEvidenceAccumulator

    evidence = RefineEvidenceAccumulator(history_frames=120)
    for frame in (200, 210, 220, 230, 240):
        evidence.update(902, frame, "bicycle", 0.91, "general")
    result = evidence.minority_consensus(
        902, 240, "motorcycle", min_hits=2, bicycle_confidence=0.78,
        bicycle_min_hits=4, bicycle_margin=0.16, bicycle_min_strongest=0.45,
        bicycle_min_sources=2, bicycle_single_source_strong=0.88,
    )
    assert result is not None
    assert result[0] == "bicycle"


def test_v0534_context_bicycle_requires_dual_moderate_sources() -> None:
    from app.classification import contextual_bicycle_decision

    decision = contextual_bicycle_decision(
        [("domain", 0.46), ("general", 0.55)],
        dual_source_confidence=0.72,
        single_source_confidence=0.90,
        min_source_confidence=0.18,
        min_strongest=0.34,
    )
    assert decision is not None
    assert decision[0] == "bicycle"


def test_v0534_context_bicycle_rejects_single_medium_guess() -> None:
    from app.classification import contextual_bicycle_decision

    assert contextual_bicycle_decision(
        [("general", 0.72)], single_source_confidence=0.90
    ) is None


def test_v0534_context_bicycle_allows_one_extremely_strong_source() -> None:
    from app.classification import contextual_bicycle_decision

    decision = contextual_bicycle_decision(
        [("general", 0.94)], single_source_confidence=0.90
    )
    assert decision == ("bicycle", 0.94)


def test_v0535_context_match_accepts_full_bicycle_near_partial_front_box() -> None:
    from app.classification import RefineCandidate, select_contextual_bicycle_refinement
    target = (80.0, 70.0, 120.0, 150.0)
    candidates = [RefineCandidate("bicycle", 0.46, (55.0, 45.0, 135.0, 165.0))]
    match = select_contextual_bicycle_refinement(target, candidates)
    assert match is not None
    assert match.label == "bicycle"


def test_v0535_context_match_rejects_parked_neighbor() -> None:
    from app.classification import RefineCandidate, select_contextual_bicycle_refinement
    target = (80.0, 70.0, 120.0, 150.0)
    candidates = [RefineCandidate("bicycle", 0.95, (220.0, 40.0, 300.0, 160.0))]
    assert select_contextual_bicycle_refinement(target, candidates) is None


def test_v0535_context_trail_combines_one_context_opinion_with_temporal_evidence() -> None:
    from app.classification import contextual_bicycle_temporal_decision
    result = contextual_bicycle_temporal_decision(
        [("general", 0.38)], temporal_hits=3, temporal_fused=0.63,
        temporal_strongest=0.47, temporal_sources=1, min_combined=0.72,
    )
    assert result is not None
    assert result[0] == "bicycle"


def test_v0535_context_trail_rejects_single_weak_guess_without_history() -> None:
    from app.classification import contextual_bicycle_temporal_decision
    assert contextual_bicycle_temporal_decision(
        [("general", 0.60)], temporal_hits=1, temporal_fused=0.60,
        temporal_strongest=0.60, temporal_sources=1,
    ) is None


def test_v0536_weak_motor_dual_context_rescues_two_source_bicycle() -> None:
    from app.classification import contextual_bicycle_weak_motor_decision
    result = contextual_bicycle_weak_motor_decision(
        [("domain", 0.38), ("general", 0.36)],
        detector_confidence=0.49,
        max_motorcycle_confidence=0.62,
        dual_source_confidence=0.58,
        min_source_confidence=0.18,
        min_strongest=0.24,
    )
    assert result is not None and result[0] == "bicycle"


def test_v0536_weak_motor_dual_context_rejects_confident_motorcycle() -> None:
    from app.classification import contextual_bicycle_weak_motor_decision
    assert contextual_bicycle_weak_motor_decision(
        [("domain", 0.55), ("general", 0.52)], detector_confidence=0.81
    ) is None


def test_v0536_weak_motor_dual_context_rejects_single_source() -> None:
    from app.classification import contextual_bicycle_weak_motor_decision
    assert contextual_bicycle_weak_motor_decision(
        [("domain", 0.72)], detector_confidence=0.49
    ) is None


def test_v0537_competitive_context_rescues_weak_motor_when_bicycle_wins_both_sources() -> None:
    from app.classification import contextual_bicycle_competitive_decision
    result = contextual_bicycle_competitive_decision(
        [
            ("domain", 0.21, 0.05),
            ("general", 0.20, 0.04),
        ],
        detector_confidence=0.49,
        max_motorcycle_confidence=0.55,
        min_bicycle_confidence=0.12,
        min_source_margin=0.06,
        dual_fused_confidence=0.34,
        fused_margin=0.08,
    )
    assert result is not None
    assert result[0] == "bicycle"


def test_v0537_competitive_context_rejects_when_motorcycle_wins_target() -> None:
    from app.classification import contextual_bicycle_competitive_decision
    assert contextual_bicycle_competitive_decision(
        [
            ("domain", 0.34, 0.46),
            ("general", 0.31, 0.44),
        ],
        detector_confidence=0.48,
    ) is None


def test_v0537_competitive_context_rejects_confident_primary_motorcycle() -> None:
    from app.classification import contextual_bicycle_competitive_decision
    assert contextual_bicycle_competitive_decision(
        [
            ("domain", 0.51, 0.12),
            ("general", 0.48, 0.10),
        ],
        detector_confidence=0.78,
    ) is None


def test_v0537_competitive_single_source_needs_temporal_support() -> None:
    from app.classification import contextual_bicycle_competitive_decision
    observations = [("domain", 0.61, 0.08)]
    assert contextual_bicycle_competitive_decision(
        observations, detector_confidence=0.44, temporal_hits=1, temporal_fused=0.61
    ) is None
    result = contextual_bicycle_competitive_decision(
        observations, detector_confidence=0.44, temporal_hits=2, temporal_fused=0.57
    )
    assert result is not None and result[0] == "bicycle"


def test_v0538_near_margin_context_rescues_dual_source_weak_motorcycle() -> None:
    from app.classification import (
        contextual_bicycle_competitive_decision,
        contextual_bicycle_near_margin_decision,
    )

    observations = [
        ("domain", 0.17, 0.13),
        ("general", 0.16, 0.15),
    ]
    # V0.5.37 remains intentionally too strict for this almost-tied context.
    assert contextual_bicycle_competitive_decision(
        observations,
        detector_confidence=0.49,
        max_motorcycle_confidence=0.55,
        min_bicycle_confidence=0.12,
        min_source_margin=0.06,
        dual_fused_confidence=0.34,
        fused_margin=0.08,
    ) is None
    result = contextual_bicycle_near_margin_decision(
        observations,
        detector_confidence=0.49,
    )
    assert result is not None
    assert result[0] == "bicycle"
    assert result[1] >= 0.28


def test_v0538_near_margin_context_honors_motorcycle_veto() -> None:
    from app.classification import contextual_bicycle_near_margin_decision

    assert contextual_bicycle_near_margin_decision(
        [
            ("domain", 0.20, 0.11),
            ("general", 0.16, 0.29),
        ],
        detector_confidence=0.48,
    ) is None


def test_v0538_near_margin_context_rejects_confident_primary_or_single_source() -> None:
    from app.classification import contextual_bicycle_near_margin_decision

    dual = [("domain", 0.24, 0.12), ("general", 0.21, 0.11)]
    assert contextual_bicycle_near_margin_decision(dual, detector_confidence=0.61) is None
    assert contextual_bicycle_near_margin_decision(
        [("domain", 0.42, 0.10)], detector_confidence=0.45
    ) is None


def test_v0541_cross_frame_bicycle_accepts_two_sources_on_different_frames():
    from app.classification import contextual_bicycle_cross_frame_decision
    decision, audit = contextual_bicycle_cross_frame_decision(
        [(100, "domain", 0.19, 0.10), (104, "general", 0.18, 0.09)],
        detector_confidence=0.49,
    )
    assert decision is not None and decision[0] == "bicycle"
    assert audit["accepted"] is True
    assert audit["frames"] == 2 and audit["sources"] == 2


def test_v0541_cross_frame_bicycle_rejects_one_frame_even_with_two_sources():
    from app.classification import contextual_bicycle_cross_frame_decision
    decision, audit = contextual_bicycle_cross_frame_decision(
        [(100, "domain", 0.24, 0.08), (100, "general", 0.23, 0.07)],
        detector_confidence=0.48,
    )
    assert decision is None
    assert audit["reason"] == "insufficient_frames"


def test_v0541_cross_frame_bicycle_motorcycle_veto_is_fail_closed():
    from app.classification import contextual_bicycle_cross_frame_decision
    decision, audit = contextual_bicycle_cross_frame_decision(
        [(100, "domain", 0.20, 0.08), (104, "general", 0.15, 0.30)],
        detector_confidence=0.47,
    )
    assert decision is None
    assert audit["reason"] == "motorcycle_source_veto"


def test_v0541_cross_frame_bicycle_rejects_strong_primary_motorcycle():
    from app.classification import contextual_bicycle_cross_frame_decision
    decision, audit = contextual_bicycle_cross_frame_decision(
        [(100, "domain", 0.30, 0.08), (104, "general", 0.30, 0.08)],
        detector_confidence=0.72,
    )
    assert decision is None
    assert audit["reason"] == "primary_motorcycle_too_strong"


def test_v0543_xframe_priority_prefers_nearest_gate_candidate():
    from app.classification import prioritize_bicycle_xframe_candidates

    far_first_in_tracker_order = [
        (0.060, 0.28, 91, (1.0, 1.0, 10.0, 10.0)),
        (0.018, 0.49, 44, (2.0, 2.0, 12.0, 12.0)),
        (0.031, 0.20, 55, (3.0, 3.0, 13.0, 13.0)),
    ]
    selected = prioritize_bicycle_xframe_candidates(far_first_in_tracker_order, 1)
    assert [item[2] for item in selected] == [44]


def test_v0543_xframe_priority_keeps_budget_and_deterministic_ties():
    from app.classification import prioritize_bicycle_xframe_candidates

    candidates = [
        (0.020, 0.45, 9, (0.0, 0.0, 1.0, 1.0)),
        (0.020, 0.30, 8, (0.0, 0.0, 1.0, 1.0)),
        (0.020, 0.30, 7, (0.0, 0.0, 1.0, 1.0)),
    ]
    selected = prioritize_bicycle_xframe_candidates(candidates, 2)
    assert [item[2] for item in selected] == [7, 8]
    assert prioritize_bicycle_xframe_candidates(candidates, 0) == []


def test_v0553_context_motor_veto_keeps_motor_only_observations() -> None:
    from app.classification import contextual_motorcycle_veto

    assert contextual_motorcycle_veto([("general", 0.0, 0.44)]) is True
    assert contextual_motorcycle_veto(
        [("domain", 0.50, 0.625)], motorcycle_veto=0.125,
    ) is False


def test_v0553_near_margin_veto_cannot_hide_behind_source_best() -> None:
    from app.classification import contextual_bicycle_near_margin_decision

    assert contextual_bicycle_near_margin_decision(
        [
            ("domain", 0.45, 0.10),
            ("general", 0.40, 0.10),
            ("general", 0.0, 0.60),
        ],
        detector_confidence=0.48,
    ) is None


def test_v0553_xframe_losing_extra_frame_does_not_prove_temporal_support() -> None:
    from app.classification import contextual_bicycle_cross_frame_decision

    decision, audit = contextual_bicycle_cross_frame_decision(
        [
            (100, "domain", 0.24, 0.05),
            (100, "general", 0.23, 0.04),
            # A tied frame is usable, but supplies no bicycle-winning evidence.
            (104, "domain", 0.08, 0.08),
        ],
        detector_confidence=0.48,
    )
    assert decision is None
    assert audit["reason"] == "insufficient_frames"
    assert audit["frames"] == 1
    assert audit["usable_frames"] == 2


def test_v0553_xframe_winning_second_frame_survives_best_source_selection() -> None:
    from app.classification import contextual_bicycle_cross_frame_decision

    decision, audit = contextual_bicycle_cross_frame_decision(
        [
            (100, "domain", 0.24, 0.05),
            (100, "general", 0.23, 0.04),
            # This real temporal win survives even when source-best is frame100.
            (104, "domain", 0.09, 0.06),
        ],
        detector_confidence=0.48,
    )
    assert decision is not None and decision[0] == "bicycle"
    assert audit["winning_frames"] == [100, 104]


def test_v0553_xframe_motor_veto_precedes_best_frame_selection() -> None:
    from app.classification import contextual_bicycle_cross_frame_decision

    decision, audit = contextual_bicycle_cross_frame_decision(
        [
            (100, "domain", 0.24, 0.05),
            (104, "general", 0.23, 0.04),
            # A new motor-only result must not vanish below the bicycle floor.
            (106, "general", 0.0, 0.60),
        ],
        detector_confidence=0.48,
    )
    assert decision is None
    assert audit["reason"] == "motorcycle_source_veto"


def test_v0553_truck_observe_respects_family_for_existing_lock() -> None:
    from app.classification import TruckSemanticLock

    lock = TruckSemanticLock()
    assert lock.observe(7, 100, stable_label="truck", certainty=0.93, hits=6) is not None
    assert lock.observe(7, 110, stable_label="motorcycle", certainty=0.95, hits=8) is None
    assert lock.resolve(7, 110, "motorcycle") is None
    assert lock.resolve(7, 110, "car") == ("truck", 0.93)


def test_v0553_truck_refiner_evidence_cannot_create_two_wheel_lock() -> None:
    from app.classification import TruckSemanticLock

    lock = TruckSemanticLock()
    assert lock.observe(
        9, 100, stable_label="bicycle", certainty=0.95, hits=8,
        refiner_hits=5, refiner_confidence=0.95,
    ) is None
    assert lock.active_count(100) == 0


def test_v0553_truck_lock_cannot_resolve_or_refresh_before_source_frame() -> None:
    from app.classification import TruckSemanticLock

    lock = TruckSemanticLock(ttl_frames=30)
    assert lock.observe(7, 200, stable_label="truck", certainty=0.90, hits=6) == ("truck", 0.90)
    assert lock.resolve(7, 199, "car") is None
    assert lock.observe(7, 190, stable_label="truck", certainty=0.99, hits=6) is None
    # The old callback cannot replace the newer lock or regress its clock.
    assert lock.resolve(7, 230, "car") == ("truck", 0.90)
    assert lock.resolve(7, 231, "car") is None


def test_v0553_truck_expired_confidence_does_not_inflate_new_lock() -> None:
    from app.classification import TruckSemanticLock

    lock = TruckSemanticLock(ttl_frames=30)
    assert lock.observe(7, 100, stable_label="truck", certainty=0.99, hits=6) == ("truck", 0.99)
    assert lock.observe(7, 200, stable_label="truck", certainty=0.82, hits=6) == ("truck", 0.82)
    assert lock.resolve(7, 210, "car") == ("truck", 0.82)
