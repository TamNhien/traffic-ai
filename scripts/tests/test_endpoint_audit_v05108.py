"""Causal endpoint audit regressions; stdlib-only and no model/GT edits."""
import copy
import gzip
import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('endpoint_audit_v108', ROOT / 'scripts/audit-endpoint-precision.py')
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)
LINE = [[.343, .479], [.7587, .385]]


def metadata(enabled=True, version='0.5.107'):
    return {'kind': 'session_metadata', 'source_fps': 25.0,
            'endpoint_precision_guard_enabled': enabled,
            'ai_runtime_version': version, 'worker_source_sha256': 'a' * 64,
            'gate_decision_schema_version': 1, 'gate_decision_scope': 'per-gate-track-v1'}


def event(identifier=1, time=9.92, direction='out', projection=.05):
    return {'id': identifier, 'tracking_id': 10, 'source_time_seconds': time,
            'source_frame_index': max(1, int(round(time * 25 + 1))),
            'vehicle_type': 'motorcycle', 'direction': direction, 'crossing_method': 'interpolated',
            'crossing_x': LINE[0][0] + (LINE[1][0] - LINE[0][0]) * projection,
            'crossing_y': LINE[0][1] + (LINE[1][1] - LINE[0][1]) * projection}


def track(time=9.92, direction='out', signed=.01, suppressed=False):
    value = {'track_id': 10, 'raw_track_id': 20, 'label': 'motorcycle',
             'final_gate_decision': 'primary-accepted', 'primary_gate_direction': direction,
             'center_signed': signed,
             'crossing_clock_audit': {
                 'source_frame_index': max(1, int(round(time * 25 + 1))),
                 'selected_frame_index': time * 25 + 1, 'source_time_seconds': time,
                 'direction': direction, 'vehicle_type': 'motorcycle',
                 'crossing_method': 'interpolated',
                 'producer_decision': AUDIT.SUPPRESSED if suppressed else 'committed_before_submit'}}
    if suppressed:
        value['endpoint_precision_suppression'] = {
            'kind': 'finite_endpoint_center_uncertain', 'projection': .05,
            'center_signed': signed, 'direction': direction, 'method': 'interpolated',
            'edge_fraction': .08, 'stable_center_side': .04}
    return value


def frame(*tracks, index=250, counter=0):
    value = {'frame_index': index, 'source_time_seconds': (index - 1) / 25,
             'gate_tracks': list(tracks)}
    if counter is not None:
        value['endpoint_precision_suppressed'] = counter
    return value


def analyze(events=(), frames=(), meta=None, matched=(), extra=()):
    report = {'benchmark': {'id': 1}, 'session_id': 2, 'matched': len(matched),
              'missed': 0, 'false_positives': len(extra),
              'matched_items': [{'ai_event_id': value} for value in matched],
              'false_positive_items': [{'ai_event_id': value} for value in extra]}
    trace = [metadata() if meta is None else meta,
             {'kind': 'geometry_metadata', 'line': copy.deepcopy(LINE)}, *frames]
    return AUDIT.analyze_trace(report, list(events), [], iter(trace))


class EndpointAuditTests(unittest.TestCase):
    def test_suppressions_exist_without_persisted_events(self):
        result = analyze(frames=[frame(track(suppressed=True), counter=1)])
        self.assertEqual(result['flagged_event_count'], 0)
        self.assertEqual(result['actual_suppression_count'], 1)
        row = result['runtime_suppression_evidence']['suppressions'][0]
        self.assertEqual(row['source_time_seconds'], 9.92)
        self.assertEqual(row['observed_frame_index'], 250)
        self.assertEqual(row['raw_tracking_id'], 20)
        self.assertFalse(row['physical_identity_proven'])

    def test_exact_clock_beats_nearest_confirmation_for_repeat_passages(self):
        first, second = event(1, 9.92), event(2, 9.96)
        result = analyze([first, second], [frame(track(9.96, signed=-.06), index=251),
                                         frame(track(9.92, signed=.01), index=258)], matched=[1, 2])
        self.assertEqual([row['ai_event_id'] for row in result['candidates']], [1])
        self.assertEqual([row['gate_evidence_frame'] for row in result['event_evidence']], [258, 251])
        self.assertEqual(result['event_evidence_status_counts'], {'exact-clock': 2})

    def test_wrong_direction_class_method_or_source_frame_never_fallback(self):
        for field, wrong in [('direction', 'in'), ('vehicle_type', 'bicycle'),
                             ('crossing_method', 'rescued'), ('source_frame_index', 248)]:
            with self.subTest(field=field):
                value = track()
                value['crossing_clock_audit'][field] = wrong
                result = analyze([event()], [frame(value)])
                self.assertEqual(result['flagged_event_count'], 0)
                self.assertEqual(result['event_evidence'][0]['status'], 'missing-clock-evidence')

    def test_rounded_database_clock_can_match_precise_trace(self):
        result = analyze([event(time=9.92)], [frame(track(time=9.92004))])
        self.assertEqual(result['event_evidence'][0]['status'], 'exact-clock')
        self.assertEqual(result['flagged_event_count'], 1)

    def test_duplicate_exact_clock_is_explicitly_ambiguous(self):
        result = analyze([event()], [frame(track()), frame(track(), index=251)])
        self.assertEqual(result['event_evidence'][0]['status'], 'ambiguous-clock')
        self.assertEqual(result['event_evidence'][0]['candidate_record_count'], 2)
        self.assertEqual(result['unknown_event_evidence_count'], 1)
        self.assertEqual(result['flagged_event_count'], 0)

    def test_legacy_projection_preserves_candidates_but_actual_is_unknown(self):
        value = track()
        del value['crossing_clock_audit']
        result = analyze([event()], [frame(value, counter=None)], meta={'kind': 'session_metadata'}, extra=[1])
        self.assertEqual(result['flagged_event_count'], 1)
        self.assertEqual(result['flagged_previously_unmatched'], 1)
        self.assertEqual(result['candidates'][0]['evidence_status'], 'legacy-approximation')
        self.assertIsNone(result['actual_suppression_count'])
        self.assertEqual(result['runtime_suppression_evidence']['status'], 'not-recorded')

    def test_legacy_wrong_direction_and_equal_distance_ambiguity_are_unknown(self):
        value = track(direction='in')
        del value['crossing_clock_audit']
        result = analyze([event()], [frame(value)], meta={'kind': 'session_metadata'})
        self.assertEqual(result['unknown_event_evidence_count'], 1)
        value['primary_gate_direction'] = 'out'
        result = analyze([event(time=10.0)], [frame(value, index=250), frame(value, index=252)],
                         meta={'kind': 'session_metadata'})
        self.assertEqual(result['event_evidence'][0]['status'], 'ambiguous-legacy-evidence')

    def test_enabled_trace_without_suppression_counter_is_unknown(self):
        result = analyze(frames=[frame(counter=None)])
        self.assertIsNone(result['actual_suppression_count'])
        self.assertEqual(result['runtime_suppression_evidence']['status'], 'not-recorded')

    def test_disabled_guard_and_verified_zero_have_distinct_statuses(self):
        result = analyze(frames=[frame()], meta=metadata(False))
        self.assertEqual(result['actual_suppression_count'], 0)
        self.assertEqual(result['runtime_suppression_evidence']['status'], 'disabled')
        result = analyze(frames=[frame()])
        self.assertEqual(result['actual_suppression_count'], 0)
        self.assertEqual(result['runtime_suppression_evidence']['status'], 'recorded')

    def test_counter_claim_mismatch_or_regression_is_not_reported_as_zero(self):
        cases = [[frame(counter=2)], [frame(counter=1), frame(index=251, counter=0)]]
        for frames in cases:
            with self.subTest(frames=frames):
                result = analyze(frames=frames)
                self.assertIsNone(result['actual_suppression_count'])
                self.assertEqual(result['runtime_suppression_evidence']['status'], 'inconsistent')

    def test_partial_counter_coverage_is_inconsistent(self):
        result = analyze(frames=[frame(), frame(index=251, counter=None)])
        self.assertIsNone(result['actual_suppression_count'])
        self.assertIn('incomplete_suppression_counter_evidence', result['runtime_suppression_evidence']['issues'])

    def test_counter_increment_must_occur_on_suppression_frame(self):
        result = analyze(frames=[frame(track(suppressed=True), counter=0), frame(index=251, counter=1)])
        self.assertIsNone(result['actual_suppression_count'])
        self.assertIn('suppression_counter_frame_mismatch', result['runtime_suppression_evidence']['issues'])

    def test_modern_missing_scope_cannot_use_legacy_nearest_frame(self):
        meta = metadata()
        del meta['gate_decision_scope']
        value = track()
        del value['crossing_clock_audit']
        result = analyze([event()], [frame(value)], meta=meta)
        self.assertEqual(result['runtime_provenance']['status'], 'inconsistent')
        self.assertEqual(result['event_evidence'][0]['status'], 'missing-clock-evidence')
        self.assertEqual(result['flagged_event_count'], 0)

    def test_uncommitted_clock_is_unknown_and_pending_clock_is_marked(self):
        for producer in [None, 'arbitrary', 'human_guard_rejected']:
            with self.subTest(producer=producer):
                value = track()
                value['crossing_clock_audit']['producer_decision'] = producer
                result = analyze([event()], [frame(value)])
                self.assertEqual(result['event_evidence'][0]['status'], 'uncommitted-producer-evidence')
                self.assertEqual(result['flagged_event_count'], 0)
        value['crossing_clock_audit']['producer_decision'] = 'human_guard_pending'
        result = analyze([event()], [frame(value)])
        self.assertEqual(result['event_evidence'][0]['status'], 'pending-producer-evidence')
        self.assertEqual(result['flagged_event_count'], 0)

    def test_malformed_membership_fields_return_inconsistent_not_typeerror(self):
        for field in ['direction', 'vehicle_type']:
            with self.subTest(field=field):
                value = track(suppressed=True)
                value['crossing_clock_audit'][field] = []
                result = analyze(frames=[frame(value, counter=1)])
                self.assertIsNone(result['actual_suppression_count'])
        value = track(suppressed=True)
        value['track_id'] = []
        result = analyze(frames=[frame(value, counter=1)])
        self.assertIn('invalid_track_identity', result['runtime_suppression_evidence']['issues'])
        value = track(suppressed=True)
        value['final_gate_decision'] = []
        result = analyze(frames=[frame(value, counter=1)])
        self.assertIsNone(result['actual_suppression_count'])

    def test_nonfinite_policy_evidence_is_unknown_and_json_serializable(self):
        value = track(suppressed=True)
        value['endpoint_precision_suppression']['projection'] = float('nan')
        result = analyze(frames=[frame(value, counter=1)])
        self.assertIsNone(result['actual_suppression_count'])
        self.assertIsNone(result['runtime_suppression_evidence']['suppressions'][0]['policy']['projection'])
        json.dumps(result, allow_nan=False)

    def test_missing_geometry_is_unknown_instead_of_non_candidate(self):
        report = {'benchmark': {'id': 1}, 'session_id': 2, 'matched': 0, 'missed': 0,
                  'false_positives': 0, 'matched_items': [], 'false_positive_items': []}
        result = AUDIT.analyze_trace(report, [event()], [], [metadata(), frame(track())])
        self.assertEqual(result['event_evidence'][0]['status'], 'missing-geometry-evidence')
        self.assertEqual(result['unknown_event_evidence_count'], 1)

    def test_null_persisted_track_identity_is_unknown(self):
        value = event()
        value['tracking_id'] = None
        result = analyze([value], [frame(track())])
        self.assertEqual(result['event_evidence'][0]['status'], 'missing-track-identity')
        self.assertEqual(result['unknown_event_evidence_count'], 1)
        self.assertEqual(result['flagged_event_count'], 0)

    def test_policy_import_does_not_depend_on_existing_service_app_namespace(self):
        with patch.dict(sys.modules, {'app': types.ModuleType('backend_app')}):
            spec = importlib.util.spec_from_file_location('endpoint_audit_namespace_regression',
                                                         ROOT / 'scripts/audit-endpoint-precision.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            result = module.endpoint_precision_rejection(LINE, (.343, .479), 0,
                                                        'out', 'motorcycle', 'interpolated')
            self.assertIsNotNone(result)

    def test_missing_or_contradictory_suppression_evidence_is_retained(self):
        for kind in ['missing_policy', 'wrong_producer', 'wrong_clock', 'wrong_center', 'wrong_scope']:
            with self.subTest(kind=kind):
                value = track(suppressed=True)
                if kind == 'missing_policy':
                    del value['endpoint_precision_suppression']
                elif kind == 'wrong_producer':
                    value['crossing_clock_audit']['producer_decision'] = 'committed_before_submit'
                elif kind == 'wrong_clock':
                    value['crossing_clock_audit']['selected_frame_index'] -= 1
                elif kind == 'wrong_center':
                    value['center_signed'] = -.06
                else:
                    value['crossing_clock_audit']['vehicle_type'] = 'truck'
                result = analyze(frames=[frame(value, counter=1)])
                self.assertIsNone(result['actual_suppression_count'])
                runtime = result['runtime_suppression_evidence']
                self.assertEqual(runtime['observed_suppression_rows'], 1)
                self.assertEqual(runtime['suppressions'][0]['evidence_status'], 'inconsistent')

    def test_suppression_under_disabled_or_missing_runtime_provenance_is_unknown(self):
        for meta in [metadata(False), {'kind': 'session_metadata'},
                     {**metadata(), 'worker_source_sha256': 'bad'}]:
            with self.subTest(meta=meta):
                result = analyze(frames=[frame(track(suppressed=True), counter=1)], meta=meta)
                self.assertIsNone(result['actual_suppression_count'])

    def test_persisted_event_cannot_be_linked_to_suppressed_proposal(self):
        result = analyze([event()], [frame(track(suppressed=True), counter=1)])
        self.assertEqual(result['event_evidence'][0]['status'], 'persisted-suppressed-conflict')
        self.assertEqual(result['flagged_event_count'], 0)
        self.assertIsNone(result['actual_suppression_count'])
        self.assertIn('suppressed_crossing_persisted', result['runtime_suppression_evidence']['issues'])

    def test_input_report_events_gt_and_trace_are_unchanged(self):
        report = {'benchmark': {'id': 1}, 'session_id': 2, 'matched': 0, 'missed': 1,
                  'false_positives': 1, 'matched_items': [], 'false_positive_items': [{'ai_event_id': 1}]}
        inputs = [report, [event()], [{'time': 123}],
                  [metadata(), {'kind': 'geometry_metadata', 'line': LINE}, frame(track())]]
        before = copy.deepcopy(inputs)
        AUDIT.analyze_trace(*inputs)
        self.assertEqual(inputs, before)

    def test_zip_entry_verifies_before_projection_and_writes_separate_sections(self):
        with tempfile.TemporaryDirectory() as folder:
            export = Path(folder) / 'export.zip'
            report = {'benchmark': {'id': 1}, 'session_id': 2, 'matched': 0, 'missed': 0,
                      'false_positives': 0, 'matched_items': [], 'false_positive_items': []}
            rows = [metadata(), {'kind': 'geometry_metadata', 'line': LINE},
                    frame(track(suppressed=True), counter=1)]
            with ZipFile(export, 'w') as archive:
                for name, content in [('report.json', report), ('events.json', []), ('ground-truth.json', [])]:
                    archive.writestr(name, json.dumps(content))
                archive.writestr('benchmark-trace.jsonl.gz', gzip.compress(
                    ''.join(json.dumps(value) + '\n' for value in rows).encode()))
            original = export.read_bytes()
            with patch.object(AUDIT, '_verify_export', return_value={}) as verify:
                result = AUDIT.analyze(export)
                verify.assert_called_once_with(export)
            AUDIT.write_report(result, Path(folder) / 'reports')
            text = (Path(folder) / 'reports/endpoint-precision.md').read_text()
            self.assertIn('Actual recorded endpoint suppressions: **1**', text)
            self.assertIn('## Recorded producer suppressions', text)
            self.assertIn('## Remaining persisted-event counterfactual', text)
            self.assertEqual(export.read_bytes(), original)
            with patch.object(AUDIT, '_verify_export', side_effect=ValueError('bad digest')):
                with self.assertRaisesRegex(ValueError, 'bad digest'):
                    AUDIT.analyze(export)


if __name__ == '__main__':
    unittest.main()
