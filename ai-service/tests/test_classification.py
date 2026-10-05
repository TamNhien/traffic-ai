from app.classification import RefineEvidenceAccumulator, TrackLabelSmoother, TruckSemanticLock, VehicleClassPolicy


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


def test_v0554_context_overlap_cannot_bypass_bounded_center_for_either_class() -> None:
    from app.classification import RefineCandidate, select_contextual_two_wheel_refinement

    target = (80.0, 70.0, 120.0, 150.0)
    # The huge box covers the entire small target, but its center is more than
    # two target diagonals away. Overlap cannot identify a local context owner.
    for label in ("bicycle", "motorcycle"):
        candidates = [RefineCandidate(label, 0.95, (85.0, 20.0, 500.0, 210.0))]
        assert select_contextual_two_wheel_refinement(target, candidates, label=label) is None


def test_v0554_context_custom_center_bound_applies_to_strict_matching() -> None:
    from app.classification import RefineCandidate, select_contextual_two_wheel_refinement

    target = (80.0, 70.0, 120.0, 150.0)
    for label in ("bicycle", "motorcycle"):
        candidates = [RefineCandidate(label, 0.70, (50.0, 45.0, 180.0, 165.0))]
        assert select_contextual_two_wheel_refinement(
            target, candidates, label=label, max_center_distance_ratio=0.10,
        ) is None
        assert select_contextual_two_wheel_refinement(target, candidates, label=label) is not None


def test_v0554_context_bounded_candidate_survives_high_score_remote_overlap() -> None:
    from app.classification import RefineCandidate, select_contextual_bicycle_refinement

    match = select_contextual_bicycle_refinement(
        (80.0, 70.0, 120.0, 150.0),
        [
            RefineCandidate("bicycle", 0.99, (85.0, 20.0, 500.0, 210.0)),
            RefineCandidate("bicycle", 0.46, (55.0, 45.0, 135.0, 165.0)),
        ],
    )
    assert match is not None and match.confidence == 0.46


def test_v0554_no_confidence_cannot_prove_temporal_hits_or_source_diversity() -> None:
    from app.classification import RefineEvidenceAccumulator

    evidence = RefineEvidenceAccumulator()
    for frame, confidence, source in [(100, 0.0, "domain"), (110, float("nan"), "general"), (120, -0.4, "general")]:
        evidence.update(7, frame, "bicycle", confidence, source)
    assert evidence.support(7, 120, "bicycle") == (0, 0.0, 0.0)
    assert evidence.source_count(7, 120, "bicycle") == 0
    evidence.update(7, 120, "bicycle", 0.80, "general")
    assert evidence.support(7, 120, "bicycle")[0] == 1
    assert evidence.source_count(7, 120, "bicycle") == 1
    assert evidence.minority_consensus(7, 120, "motorcycle") is None


def test_v0554_retry_same_opinion_cannot_evict_distinct_temporal_evidence() -> None:
    from app.classification import RefineEvidenceAccumulator

    evidence = RefineEvidenceAccumulator(max_observations=16)
    for frame in (100, 110, 120):
        evidence.update(7, frame, "bicycle", 0.60, "domain")
    for _ in range(32):
        evidence.update(7, 120, "bicycle", 0.60, "domain")
    assert evidence.support(7, 120, "bicycle")[0] == 3
    assert evidence.minority_consensus(7, 120, "motorcycle", bicycle_min_hits=3) is not None


def test_v0554_merge_aliases_deduplicates_opinions_before_history_limit() -> None:
    from app.classification import RefineEvidenceAccumulator

    evidence = RefineEvidenceAccumulator(max_observations=16)
    for frame in range(100, 108):
        evidence.update(7, frame, "bicycle", 0.60, "domain")
    for frame in range(100, 112):
        evidence.update(8, frame, "bicycle", 0.60, "domain")
    evidence.merge_track(7, 8)
    assert evidence.support(8, 111, "bicycle")[0] == 12
    assert evidence.support(7, 111, "bicycle")[0] == 0


def test_v0554_temporal_bicycle_only_history_cannot_hide_motorcycle_contradiction() -> None:
    from app.classification import RefineEvidenceAccumulator, contextual_bicycle_temporal_decision

    evidence = RefineEvidenceAccumulator()
    for frame in (100, 110, 120):
        evidence.update(7, frame, "bicycle", 0.55, "domain")
        evidence.update(7, frame, "motorcycle", 0.80, "general")
    hits, fused, strongest, sources = evidence.competitive_support(7, 125, "bicycle", "motorcycle")
    assert (hits, fused, strongest, sources) == (0, 0.0, 0.0, 0)
    assert contextual_bicycle_temporal_decision(
        [("domain", 0.60)], temporal_hits=hits, temporal_fused=fused,
        temporal_strongest=strongest, temporal_sources=sources,
    ) is None


def test_v0554_temporal_tied_frame_cannot_prove_bicycle_agreement() -> None:
    from app.classification import RefineEvidenceAccumulator

    evidence = RefineEvidenceAccumulator()
    for frame, bike, moto in [(100, 0.50, 0.50), (110, 0.52, 0.49), (120, 0.53, 0.50)]:
        evidence.update(7, frame, "bicycle", bike, "domain")
        evidence.update(7, frame, "motorcycle", moto, "general")
    hits, fused, strongest, sources = evidence.competitive_support(
        7, 125, "bicycle", "motorcycle", min_source_win=0.015,
    )
    assert hits == 2 and sources == 1 and fused > strongest > 0.0


def test_v0554_temporal_winning_history_keeps_two_source_bicycle_rescue() -> None:
    from app.classification import RefineEvidenceAccumulator, contextual_bicycle_temporal_decision

    evidence = RefineEvidenceAccumulator()
    evidence.update(7, 100, "bicycle", 0.50, "domain")
    evidence.update(7, 110, "bicycle", 0.55, "general")
    hits, fused, strongest, sources = evidence.competitive_support(7, 115, "bicycle", "motorcycle")
    assert hits == 2 and sources == 2
    assert contextual_bicycle_temporal_decision(
        [("domain", 0.50)], temporal_hits=hits, temporal_fused=fused,
        temporal_strongest=strongest, temporal_sources=sources,
    ) is not None


def test_v0554_temporal_losing_source_cannot_borrow_another_sources_win() -> None:
    from app.classification import RefineEvidenceAccumulator

    evidence = RefineEvidenceAccumulator()
    for frame in (100, 110):
        evidence.update(7, frame, "bicycle", 0.55, "general")
        evidence.update(7, frame, "bicycle", 0.10, "domain")
        evidence.update(7, frame, "motorcycle", 0.45, "domain")
    hits, _, _, sources = evidence.competitive_support(7, 115, "bicycle", "motorcycle")
    assert hits == 2 and sources == 1


def test_v0554_temporal_context_needs_earlier_frames_and_ignores_future_or_expired() -> None:
    from app.classification import RefineEvidenceAccumulator

    evidence = RefineEvidenceAccumulator(history_frames=20)
    for frame in (10, 90, 100, 110):
        evidence.update(7, frame, "bicycle", 0.60, "domain")
    # Frame100 is the current crossing opinion, not another prior agreement.
    hits, _, _, sources = evidence.competitive_support(
        7, 100, "bicycle", "motorcycle", include_current_frame=False,
    )
    assert hits == 1 and sources == 1
    assert evidence.competitive_support(7, 100, "bicycle", "motorcycle")[0] == 2


def test_v0554_completed_passage_consumes_all_labels_but_preserves_newer_samples() -> None:
    from app.classification import RefineEvidenceAccumulator

    evidence = RefineEvidenceAccumulator()
    evidence.update(7, 100, "bicycle", 0.60, "domain")
    evidence.update(7, 105, "motorcycle", 0.80, "general")
    evidence.update(7, 110, "bicycle", 0.70, "general")
    evidence.consume_through(7, 105)
    assert evidence.support(7, 105, "bicycle") == (0, 0.0, 0.0)
    assert evidence.support(7, 105, "motorcycle") == (0, 0.0, 0.0)
    assert evidence.support(7, 110, "bicycle") == (1, 0.70, 0.70)


def test_v0555_target_matcher_honors_center_bound_despite_full_target_overlap() -> None:
    from app.classification import RefineCandidate, select_target_refinement

    target = (80.0, 70.0, 120.0, 150.0)
    candidate = RefineCandidate("truck", 0.90, (50.0, 45.0, 180.0, 165.0))
    assert select_target_refinement(target, [candidate], max_center_distance_ratio=0.10) is None
    assert select_target_refinement(target, [candidate]) is not None


def test_v0555_target_matcher_remote_large_neighbor_cannot_steal_local_vote() -> None:
    from app.classification import RefineCandidate, select_target_refinement

    match = select_target_refinement(
        (80.0, 70.0, 120.0, 150.0),
        [
            RefineCandidate("truck", 0.99, (85.0, 20.0, 500.0, 210.0)),
            RefineCandidate("car", 0.46, (85.0, 75.0, 115.0, 145.0)),
        ],
        target_family="four-wheel",
    )
    assert match is not None and match.label == "car" and match.confidence == 0.46


def test_v0555_target_matcher_retains_bounded_partial_and_family_filter() -> None:
    from app.classification import RefineCandidate, select_target_refinement

    match = select_target_refinement(
        (40.0, 40.0, 180.0, 190.0),
        [
            RefineCandidate("motorcycle", 0.99, (45.0, 45.0, 175.0, 185.0)),
            RefineCandidate("truck", 0.53, (120.0, 100.0, 175.0, 185.0)),
        ],
        target_family="four-wheel",
    )
    assert match is not None and match.label == "truck" and match.confidence == 0.53


def test_v0555_truck_consensus_cannot_accumulate_losing_car_votes() -> None:
    from app.classification import RefineEvidenceAccumulator

    evidence = RefineEvidenceAccumulator()
    for frame in (100, 110):
        evidence.update(7, frame, "truck", 0.55, "domain")
        evidence.update(7, frame, "car", 0.80, "general")
    assert evidence.minority_consensus(7, 110, "car") is None


def test_v0555_tied_car_and_truck_frames_cannot_prove_truck_consensus() -> None:
    from app.classification import RefineEvidenceAccumulator

    evidence = RefineEvidenceAccumulator()
    for frame in (100, 110):
        evidence.update(7, frame, "truck", 0.65, "domain")
        evidence.update(7, frame, "car", 0.65, "general")
    assert evidence.minority_consensus(7, 110, "car") is None


def test_v0555_bus_consensus_cannot_accumulate_losing_car_votes() -> None:
    from app.classification import RefineEvidenceAccumulator

    evidence = RefineEvidenceAccumulator()
    for frame in (100, 110):
        evidence.update(7, frame, "bus", 0.65, "domain")
        evidence.update(7, frame, "car", 0.80, "general")
    assert evidence.minority_consensus(7, 110, "car") is None


def test_v0555_bus_winner_survives_losing_truck_label_priority() -> None:
    from app.classification import RefineEvidenceAccumulator

    evidence = RefineEvidenceAccumulator()
    for frame in (100, 110):
        evidence.update(7, frame, "truck", 0.55, "domain")
        evidence.update(7, frame, "bus", 0.70, "general")
    result = evidence.minority_consensus(7, 110, "car")
    assert result is not None and result[0] == "bus"


def test_v0555_tied_truck_bus_frames_cannot_prove_either_correction() -> None:
    from app.classification import RefineEvidenceAccumulator

    evidence = RefineEvidenceAccumulator()
    for frame in (100, 110):
        evidence.update(7, frame, "truck", 0.65, "domain")
        evidence.update(7, frame, "bus", 0.65, "general")
    assert evidence.minority_consensus(7, 110, "car") is None


def test_v0555_truck_consensus_checks_competing_history_outside_winning_frames() -> None:
    from app.classification import RefineEvidenceAccumulator

    evidence = RefineEvidenceAccumulator()
    evidence.update(7, 100, "truck", 0.50, "domain")
    evidence.update(7, 110, "truck", 0.50, "general")
    evidence.update(7, 105, "car", 0.99, "general")
    assert evidence.minority_consensus(7, 110, "car") is None


def test_v0555_four_wheel_support_counts_only_strict_winning_frames() -> None:
    from app.classification import RefineEvidenceAccumulator

    evidence = RefineEvidenceAccumulator()
    for frame in (100, 110, 120):
        evidence.update(7, frame, "truck", 0.65, "domain")
    evidence.update(7, 100, "car", 0.90, "general")
    hits, fused, strongest = evidence.four_wheel_support(7, 120, "truck")
    assert hits == 2 and fused > strongest > 0.0
    assert evidence.minority_consensus(7, 120, "car") == ("truck", fused)


def test_v0555_four_wheel_support_keeps_weak_repeated_winners() -> None:
    from app.classification import RefineEvidenceAccumulator

    evidence = RefineEvidenceAccumulator()
    evidence.update(7, 300, "truck", 0.31, "domain")
    evidence.update(7, 300, "car", 0.20, "general")
    evidence.update(7, 320, "truck", 0.35, "general")
    evidence.update(7, 320, "bus", 0.20, "domain")
    result = evidence.minority_consensus(7, 320, "car", truck_confidence=0.52)
    assert result is not None and result[0] == "truck" and result[1] >= 0.52
    assert evidence.four_wheel_support(7, 320, "truck")[0] == 2


def test_v0555_four_wheel_support_ignores_future_expired_and_other_family() -> None:
    from app.classification import RefineEvidenceAccumulator

    evidence = RefineEvidenceAccumulator(history_frames=20)
    for frame in (10, 90, 100, 110):
        evidence.update(7, frame, "truck", 0.60, "domain")
    evidence.update(7, 90, "motorcycle", 0.99, "general")
    assert evidence.four_wheel_support(7, 100, "truck")[0] == 2
    assert evidence.four_wheel_support(7, 100, "motorcycle") == (0, 0.0, 0.0)


def test_v0555_four_wheel_support_collapses_duplicate_sources_to_one_frame() -> None:
    from app.classification import RefineEvidenceAccumulator

    evidence = RefineEvidenceAccumulator()
    for source in ("domain", "general"):
        for _ in range(10):
            evidence.update(7, 100, "truck", 0.70, source)
    assert evidence.four_wheel_support(7, 100, "truck") == (1, 0.70, 0.70)
    assert evidence.minority_consensus(7, 100, "car") is None


def _v0556_bicycle_consensus(evidence, frame_index: int = 130):
    # The active worker defaults require four frames and two winning sources.
    return evidence.minority_consensus(
        7, frame_index, "motorcycle", bicycle_confidence=0.78,
        bicycle_min_hits=4, bicycle_margin=0.16,
        bicycle_min_strongest=0.45, bicycle_min_sources=2,
        bicycle_single_source_strong=0.88,
    )


def test_v0556_bicycle_consensus_cannot_borrow_three_losing_frames() -> None:
    from app.classification import RefineEvidenceAccumulator

    evidence = RefineEvidenceAccumulator()
    evidence.update(7, 100, "bicycle", 0.90, "domain")
    for frame in (110, 120, 130):
        evidence.update(7, frame, "bicycle", 0.25, "general")
        evidence.update(7, frame, "motorcycle", 0.30, "domain")
    assert _v0556_bicycle_consensus(evidence) is None


def test_v0556_bicycle_consensus_cannot_borrow_three_tied_frames() -> None:
    from app.classification import RefineEvidenceAccumulator

    evidence = RefineEvidenceAccumulator()
    evidence.update(7, 100, "bicycle", 0.90, "domain")
    for frame in (110, 120, 130):
        evidence.update(7, frame, "bicycle", 0.25, "general")
        evidence.update(7, frame, "motorcycle", 0.25, "domain")
    assert _v0556_bicycle_consensus(evidence) is None


def test_v0556_bicycle_consensus_tied_source_cannot_supply_diversity() -> None:
    from app.classification import RefineEvidenceAccumulator

    evidence = RefineEvidenceAccumulator()
    for frame in (100, 110, 120, 130):
        evidence.update(7, frame, "bicycle", 0.55, "domain")
        evidence.update(7, frame, "bicycle", 0.10, "general")
        evidence.update(7, frame, "motorcycle", 0.10, "general")
    assert _v0556_bicycle_consensus(evidence) is None


def test_v0556_bicycle_consensus_losing_source_cannot_supply_diversity() -> None:
    from app.classification import RefineEvidenceAccumulator

    evidence = RefineEvidenceAccumulator()
    for frame in (100, 110, 120, 130):
        evidence.update(7, frame, "bicycle", 0.55, "domain")
        evidence.update(7, frame, "bicycle", 0.10, "general")
        evidence.update(7, frame, "motorcycle", 0.15, "general")
    assert _v0556_bicycle_consensus(evidence) is None


def test_v0556_bicycle_consensus_fusion_excludes_losing_frame_confidence() -> None:
    from app.classification import RefineEvidenceAccumulator

    evidence = RefineEvidenceAccumulator()
    for frame, source in ((100, "domain"), (110, "general")):
        evidence.update(7, frame, "bicycle", 0.36, source)
    evidence.update(7, 120, "bicycle", 0.20, "domain")
    evidence.update(7, 120, "motorcycle", 0.21, "general")
    # Two genuine wins alone remain below the unchanged 0.60 confidence floor.
    assert evidence.minority_consensus(
        7, 120, "motorcycle", bicycle_confidence=0.60,
    ) is None


def test_v0556_bicycle_consensus_strong_single_source_cannot_borrow_escape_hits() -> None:
    from app.classification import RefineEvidenceAccumulator

    evidence = RefineEvidenceAccumulator()
    evidence.update(7, 136, "bicycle", 0.99, "domain")
    for frame in (137, 138, 139, 140):
        evidence.update(7, frame, "bicycle", 0.10, "domain")
        evidence.update(7, frame, "motorcycle", 0.10, "general")
    assert _v0556_bicycle_consensus(evidence, 140) is None


def test_v0556_bicycle_consensus_retains_repeated_winning_dual_sources() -> None:
    from app.classification import RefineEvidenceAccumulator

    evidence = RefineEvidenceAccumulator()
    for frame, source in ((100, "domain"), (110, "general"), (120, "domain"), (130, "general")):
        evidence.update(7, frame, "bicycle", 0.55, source)
        evidence.update(7, frame, "motorcycle", 0.10, "general")
    result = _v0556_bicycle_consensus(evidence)
    assert result is not None and result[0] == "bicycle" and result[1] >= 0.78


def test_v0556_bicycle_consensus_retains_clear_single_source_escape() -> None:
    from app.classification import RefineEvidenceAccumulator

    evidence = RefineEvidenceAccumulator()
    for frame in (100, 110, 120, 130, 140):
        evidence.update(7, frame, "bicycle", 0.90, "domain")
    result = _v0556_bicycle_consensus(evidence, 140)
    assert result is not None and result[0] == "bicycle" and result[1] >= 0.78


def test_v0556_bicycle_consensus_keeps_aggregate_motorcycle_margin() -> None:
    from app.classification import RefineEvidenceAccumulator

    evidence = RefineEvidenceAccumulator()
    for frame, source in ((100, "domain"), (110, "general"), (120, "domain"), (130, "general")):
        evidence.update(7, frame, "bicycle", 0.55, source)
    evidence.update(7, 125, "motorcycle", 0.99, "domain")
    assert _v0556_bicycle_consensus(evidence) is None


def test_v0556_bicycle_consensus_preserves_aggregate_policy_without_new_veto() -> None:
    from app.classification import RefineEvidenceAccumulator

    evidence = RefineEvidenceAccumulator()
    for frame, source in ((100, "domain"), (110, "general"), (120, "domain"), (130, "general")):
        evidence.update(7, frame, "bicycle", 0.80, source)
    evidence.update(7, 125, "motorcycle", 0.75, "domain")
    # Ordinary consensus historically uses an aggregate margin. Its existing
    # policy is preserved; the crossing-context per-frame veto is separate.
    result = _v0556_bicycle_consensus(evidence)
    assert result is not None and result[0] == "bicycle" and result[1] >= 0.78


def test_v0557_four_wheel_support_clock_excludes_losing_tied_future_and_expired_frames() -> None:
    from app.classification import RefineEvidenceAccumulator

    evidence = RefineEvidenceAccumulator(history_frames=40)
    for frame in (90, 100):
        evidence.update(7, frame, "truck", .70, "domain")
    evidence.update(7, 105, "truck", .10, "domain")
    evidence.update(7, 105, "car", .11, "general")
    evidence.update(7, 106, "truck", .10, "domain")
    evidence.update(7, 106, "bus", .10, "general")
    evidence.update(7, 111, "truck", .99, "domain")
    evidence.update(7, 20, "truck", .99, "domain")
    hits, fused, strongest, source_frame = evidence.four_wheel_support_snapshot(7, 110, "truck")
    assert hits == 2 and fused > strongest > 0.0 and source_frame == 100
    assert evidence.four_wheel_support(7, 110, "truck") == (hits, fused, strongest)
    assert evidence.four_wheel_support_snapshot(7, 110, "bicycle") == (0, 0.0, 0.0, None)


def test_v0557_old_refiner_clock_cannot_replace_newer_primary_truck_lock() -> None:
    from app.classification import TruckSemanticLock

    lock = TruckSemanticLock(ttl_frames=30)
    assert lock.observe(7, 200, stable_label="truck", certainty=.90, hits=6) == ("truck", .90)
    assert lock.observe(
        7, 210, stable_label="car", certainty=.99, hits=20,
        refiner_hits=2, refiner_confidence=.99, refiner_frame_index=195,
    ) == ("truck", .90)
    assert lock.resolve(7, 230, "car") == ("truck", .90)
    assert lock.resolve(7, 231, "car") is None


def test_v0557_future_refiner_clock_cannot_create_current_truck_lock() -> None:
    from app.classification import TruckSemanticLock

    lock = TruckSemanticLock(ttl_frames=30)
    assert lock.observe(
        7, 100, stable_label="car", certainty=.99, hits=20,
        refiner_hits=2, refiner_confidence=.99, refiner_frame_index=101,
    ) is None
    assert lock.active_count(100) == 0


def test_v0557_future_refiner_score_cannot_inflate_valid_primary_truck_confidence() -> None:
    from app.classification import TruckSemanticLock

    lock = TruckSemanticLock(ttl_frames=30)
    assert lock.observe(
        7, 100, stable_label="truck", certainty=.90, hits=6,
        refiner_hits=2, refiner_confidence=.99, refiner_frame_index=101,
    ) == ("truck", .90)
    assert lock.resolve(7, 130, "car") == ("truck", .90)
    assert lock.resolve(7, 131, "car") is None


def test_v0558_bicycle_consensus_clock_tracks_only_eligible_winning_frames() -> None:
    evidence = RefineEvidenceAccumulator(history_frames=120)
    evidence.update(7, 100, "bicycle", .90, "domain")
    evidence.update(7, 110, "bicycle", .80, "general")
    evidence.update(7, 120, "bicycle", .30, "domain")
    evidence.update(7, 120, "motorcycle", .40, "general")
    evidence.update(7, 130, "bicycle", .50, "domain")
    evidence.update(7, 130, "motorcycle", .50, "general")
    evidence.update(7, 141, "bicycle", .99, "general")
    evidence.update(7, 10, "bicycle", .99, "domain")
    assert evidence.minority_consensus_source_frame(7, 140, "bicycle") == 110
    assert evidence.minority_consensus_source_frame(7, 231, "bicycle") == 141
    assert evidence.minority_consensus_source_frame(7, 262, "bicycle") is None


def test_v0558_four_wheel_consensus_clock_does_not_use_current_losing_truck_opinion() -> None:
    evidence = RefineEvidenceAccumulator()
    for frame in (100, 110):
        evidence.update(7, frame, "truck", .90, "domain")
    evidence.update(7, 120, "truck", .10, "domain")
    evidence.update(7, 120, "car", .20, "general")
    assert evidence.minority_consensus_source_frame(7, 120, "truck") == 110


def test_v0558_old_alias_labels_cannot_replace_newer_canonical_car_history() -> None:
    smoother = TrackLabelSmoother(history=24)
    for frame in range(25, 49):
        smoother.update(7, "truck", .90, frame_index=frame)
    for frame in range(77, 101):
        smoother.update(8, "car", .90, frame_index=frame)
    smoother.merge_track(7, 8)
    smoother.update(8, "car", .90, frame_index=101)
    assert smoother.stable_label(8, "car") == ("car", 1.0, 24)
    label, certainty, hits = smoother.stable_label(8, "car")
    assert TruckSemanticLock().observe(8, 101, stable_label=label, certainty=certainty, hits=hits) is None


def test_v0558_newer_alias_truck_history_keeps_its_actual_recent_position() -> None:
    smoother = TrackLabelSmoother(history=24)
    for frame in range(25, 49):
        smoother.update(8, "car", .90, frame_index=frame)
    for frame in range(77, 101):
        smoother.update(7, "truck", .90, frame_index=frame)
    smoother.merge_track(7, 8)
    assert smoother.stable_label(8, "car") == ("truck", 1.0, 24)


def test_v0558_same_frame_alias_votes_do_not_inflate_temporal_hits() -> None:
    smoother = TrackLabelSmoother(history=24)
    for frame in range(100, 110):
        smoother.update(7, "car", .70, frame_index=frame)
        smoother.update(8, "car", .90, frame_index=frame)
    smoother.merge_track(7, 8)
    assert smoother.stable_label(8, "truck") == ("car", 1.0, 10)


def test_v0558_same_frame_alias_competition_keeps_strongest_actual_opinion() -> None:
    smoother = TrackLabelSmoother(history=24)
    for frame in range(100, 110):
        smoother.update(7, "car", .90, frame_index=frame)
        smoother.update(8, "truck", .60, frame_index=frame)
    smoother.merge_track(7, 8)
    assert smoother.stable_label(8, "truck") == ("car", 1.0, 10)


def test_v0558_delayed_label_observation_retains_source_chronology() -> None:
    smoother = TrackLabelSmoother(history=3)
    smoother.update(7, "car", .90, frame_index=200)
    smoother.update(7, "truck", .90, frame_index=100)
    assert smoother.stable_label(7, "truck")[0] == "car"


def test_v0558_clockless_label_callers_keep_legacy_two_tuple_history() -> None:
    smoother = TrackLabelSmoother(history=3)
    smoother.update(7, "truck", .90)
    smoother.update(8, "car", .80)
    smoother.merge_track(7, 8)
    assert list(smoother._samples[8]) == [("car", .80), ("truck", .90)]
    smoother.update(8, "car", .90, frame_index=200)
    assert list(smoother._samples[8]) == [("car", .80), ("truck", .90), ("car", .90)]


def test_v0559_stable_primary_truck_does_not_renew_from_current_car_pixels() -> None:
    smoother = TrackLabelSmoother(history=24)
    lock = TruckSemanticLock(ttl_frames=30)
    for frame in range(77, 126):
        current_label = "truck" if frame <= 100 else "car"
        smoother.update(7, current_label, .90 if current_label == "truck" else .10, frame_index=frame)
        label, certainty, hits = smoother.stable_label(7, current_label)
        lock.observe(
            7, frame, stable_label=label, certainty=certainty, hits=hits,
            primary_frame_index=smoother.source_frame_for(7, "truck"),
        )
    assert lock.resolve(7, 130, "car")[0] == "truck"
    assert lock.resolve(7, 131, "car") is None


def test_v0559_new_actual_primary_truck_can_renew_source_deadline() -> None:
    lock = TruckSemanticLock(ttl_frames=30)
    lock.observe(7, 110, stable_label="truck", certainty=.90, hits=6, primary_frame_index=100)
    assert lock.observe(7, 120, stable_label="truck", certainty=.90, hits=6, primary_frame_index=120)
    assert lock.resolve(7, 150, "car")
    assert lock.resolve(7, 151, "car") is None


def test_v0559_newer_refiner_clock_wins_over_retained_primary_truck_clock() -> None:
    lock = TruckSemanticLock(ttl_frames=30)
    assert lock.observe(
        7, 120, stable_label="truck", certainty=.90, hits=6, primary_frame_index=100,
        refiner_hits=2, refiner_confidence=.80, refiner_frame_index=110,
    )
    assert lock.resolve(7, 140, "car")
    assert lock.resolve(7, 141, "car") is None


def test_v0559_newer_primary_clock_wins_over_retained_refiner_clock() -> None:
    lock = TruckSemanticLock(ttl_frames=30)
    assert lock.observe(
        7, 120, stable_label="truck", certainty=.90, hits=6, primary_frame_index=115,
        refiner_hits=2, refiner_confidence=.80, refiner_frame_index=110,
    )
    assert lock.resolve(7, 145, "car")
    assert lock.resolve(7, 146, "car") is None


def test_v0559_future_primary_clock_cannot_block_or_inflate_current_refiner_lock() -> None:
    lock = TruckSemanticLock(ttl_frames=30)
    assert lock.observe(
        7, 120, stable_label="truck", certainty=.99, hits=6, primary_frame_index=121,
        refiner_hits=2, refiner_confidence=.80, refiner_frame_index=110,
    ) == ("truck", .80)
    assert lock.resolve(7, 140, "car")
    assert lock.resolve(7, 141, "car") is None


def test_v0559_expired_primary_clock_cannot_block_or_inflate_current_refiner_lock() -> None:
    lock = TruckSemanticLock(ttl_frames=30)
    assert lock.observe(
        7, 120, stable_label="truck", certainty=.99, hits=6, primary_frame_index=89,
        refiner_hits=2, refiner_confidence=.80, refiner_frame_index=110,
    ) == ("truck", .80)


def test_v0559_expired_refiner_clock_cannot_inflate_current_primary_lock() -> None:
    lock = TruckSemanticLock(ttl_frames=30)
    assert lock.observe(
        7, 120, stable_label="truck", certainty=.90, hits=6, primary_frame_index=120,
        refiner_hits=2, refiner_confidence=.99, refiner_frame_index=89,
    ) == ("truck", .90)


def test_v0559_future_and_expired_primary_clocks_cannot_create_truck_lock() -> None:
    for clock in (121, 89):
        lock = TruckSemanticLock(ttl_frames=30)
        assert lock.observe(7, 120, stable_label="truck", certainty=.99, hits=6, primary_frame_index=clock) is None
        assert lock.active_count(120) == 0


def test_v0559_old_primary_clock_cannot_replace_newer_lock_observation() -> None:
    lock = TruckSemanticLock(ttl_frames=30)
    lock.observe(7, 115, stable_label="truck", certainty=.90, hits=6, primary_frame_index=115)
    assert lock.observe(7, 120, stable_label="truck", certainty=.99, hits=6, primary_frame_index=100) == ("truck", .90)
    assert lock.resolve(7, 145, "car")
    assert lock.resolve(7, 146, "car") is None


def test_v0559_primary_clock_lookup_preserves_label_identity_and_merged_chronology() -> None:
    smoother = TrackLabelSmoother(history=24)
    for frame in (100, 110, 120):
        smoother.update(7, "truck", .90, frame_index=frame)
    for frame in (121, 122):
        smoother.update(8, "car", .90, frame_index=frame)
    smoother.merge_track(7, 8)
    assert smoother.source_frame_for(8, "truck") == 120
    assert smoother.source_frame_for(8, "car") == 122
    assert smoother.source_frame_for(7, "truck") is None
    assert smoother.source_frame_for(8, "bus") is None
    smoother.update(8, "truck", .90, frame_index=90)
    assert smoother.source_frame_for(8, "truck") == 120


def test_v0559_clockless_primary_lock_and_smoother_keep_legacy_behavior() -> None:
    smoother = TrackLabelSmoother()
    smoother.update(7, "truck", .90)
    assert smoother.source_frame_for(7, "truck") is None
    smoother.update(7, "car", .90, frame_index=120)
    assert smoother.source_frame_for(7, "truck") is None
    lock = TruckSemanticLock(ttl_frames=30)
    assert lock.observe(7, 120, stable_label="truck", certainty=.90, hits=6) == ("truck", .90)
    assert lock.resolve(7, 150, "car")
    assert lock.resolve(7, 151, "car") is None
