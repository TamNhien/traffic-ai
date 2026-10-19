#!/usr/bin/env python3
"""Verified endpoint audit: persisted-event counterfactual and producer evidence.

The two groups are deliberately separate. A successfully suppressed proposal
does not exist in events.json. Neither group proves physical vehicle identity
or changes GT, events, matching, or the worker counting policy.
"""
from __future__ import annotations

import argparse
import gzip
import importlib.util
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parent.parent
_POLICY_SPEC = importlib.util.spec_from_file_location(
    'endpoint_precision_policy', ROOT / 'ai-service' / 'app' / 'finite_endpoint_guard.py')
if _POLICY_SPEC is None or _POLICY_SPEC.loader is None:
    raise ValueError('Endpoint precision policy module missing')
_POLICY_MODULE = importlib.util.module_from_spec(_POLICY_SPEC)
_POLICY_SPEC.loader.exec_module(_POLICY_MODULE)
endpoint_precision_rejection = _POLICY_MODULE.endpoint_precision_rejection

SUPPRESSED = 'finite_endpoint_center_uncertain_suppressed'
ACCEPTED = ('primary-accepted', 'secondary-accepted')
TWO_WHEEL = ('motorcycle', 'bicycle')


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _json_safe(value):
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _valid_line(value):
    return (isinstance(value, (list, tuple)) and len(value) == 2
            and all(isinstance(point, (list, tuple)) and len(point) == 2
                    and all(_finite(n) for n in point) for point in value)
            and sum((value[1][i] - value[0][i]) ** 2 for i in (0, 1)) >= 1e-8)


def _verify_export(export):
    util = ROOT / 'scripts' / 'audit-gate-coverage.py'
    spec = importlib.util.spec_from_file_location('endpoint_verified_audit', util)
    if spec is None or spec.loader is None:
        raise ValueError('Benchmark verification module missing')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module._verify(export)  # Complete trace/digest and event/GT integrity first.


def _runtime_provenance(metadata):
    version = metadata.get('ai_runtime_version')
    digest = metadata.get('worker_source_sha256')
    valid = (isinstance(version, str) and re.fullmatch(r'\d+\.\d+\.\d+', version) is not None
             and tuple(map(int, version.split('.'))) >= (0, 5, 105)
             and isinstance(digest, str) and re.fullmatch(r'[0-9a-f]{64}', digest) is not None
             and metadata.get('gate_decision_schema_version') == 1
             and metadata.get('gate_decision_scope') == 'per-gate-track-v1')
    declared = any(name in metadata for name in (
        'ai_runtime_version', 'worker_source_sha256',
        'gate_decision_schema_version', 'gate_decision_scope'))
    return {'status': 'verified-schema' if valid else 'inconsistent' if declared else 'legacy-unattested',
            'runtime_version': version if valid else None,
            'worker_source_sha256': digest if valid else None}


def _event_evidence(event, records, *, modern):
    """Match the selected crossing clock, never the nearest confirmation frame."""
    event_time = event.get('source_time_seconds')
    if not _finite(event_time):
        return None, 'missing-event-clock', 0
    exact = []
    for record in records:
        clock = record.get('clock')
        if not isinstance(clock, dict):
            continue
        if (clock.get('direction') == event.get('direction')
                and clock.get('vehicle_type') == event.get('vehicle_type')
                and clock.get('crossing_method') == event.get('crossing_method')
                and _finite(clock.get('source_time_seconds'))
                # DB exports round source_time_seconds to four decimals.
                and abs(clock['source_time_seconds'] - event_time) <= .00011
                and (event.get('source_frame_index') is None
                     or event.get('source_frame_index') == clock.get('source_frame_index'))):
            exact.append(record)
    if len(exact) == 1:
        producer = exact[0]['clock'].get('producer_decision')
        if producer == 'human_guard_pending':
            return None, 'pending-producer-evidence', 1
        if producer not in ('committed_before_submit', SUPPRESSED):
            return None, 'uncommitted-producer-evidence', 1
        return exact[0], 'exact-clock', 1
    if exact:
        return None, 'ambiguous-clock', len(exact)
    # Older exports lack the selected clock. Preserve a marked approximation
    # only for such exports, never silently fall back after modern mismatch.
    if modern:
        return None, 'missing-clock-evidence', 0
    legacy = [r for r in records if not isinstance(r.get('clock'), dict)
              and _finite(r.get('time')) and abs(r['time'] - event_time) <= .75
              and r.get('direction') == event.get('direction')
              and r.get('label') == event.get('vehicle_type')]
    legacy.sort(key=lambda r: abs(r['time'] - event_time))
    if not legacy:
        return None, 'missing-legacy-evidence', 0
    nearest = abs(legacy[0]['time'] - event_time)
    tied = [r for r in legacy if abs(abs(r['time'] - event_time) - nearest) <= 1e-8]
    if len(tied) != 1:
        return None, 'ambiguous-legacy-evidence', len(tied)
    return legacy[0], 'legacy-approximation', len(legacy)


def _suppression_record(observation, track, fps):
    """Retain producer claims, including incomplete/contradictory claims."""
    clock = track.get('crossing_clock_audit')
    policy = track.get('endpoint_precision_suppression')
    errors = []
    if not isinstance(clock, dict) or clock.get('producer_decision') != SUPPRESSED:
        errors.append('missing_or_conflicting_producer_decision')
    if not isinstance(policy, dict):
        errors.append('missing_endpoint_policy_evidence')
    clock = clock if isinstance(clock, dict) else {}
    policy = policy if isinstance(policy, dict) else {}
    direction = clock.get('direction')
    if direction not in ('in', 'out') or clock.get('vehicle_type') not in TWO_WHEEL \
            or clock.get('crossing_method') != 'interpolated':
        errors.append('unsupported_crossing_scope')
    if track.get('final_gate_decision') not in ACCEPTED:
        errors.append('missing_accepted_geometry_decision')
    if not _integer(track.get('track_id')):
        errors.append('missing_canonical_id')
    if (not _integer(clock.get('source_frame_index')) or clock['source_frame_index'] < 1
            or not _finite(clock.get('source_time_seconds')) or clock['source_time_seconds'] < 0
            or not _finite(clock.get('selected_frame_index'))
            or not _integer(observation.get('frame_index'))
            or clock.get('selected_frame_index', math.inf) > observation.get('frame_index', -1)):
        errors.append('invalid_crossing_clock')
    if (not _finite(fps) or fps <= 0
            or not _finite(clock.get('selected_frame_index'))
            or not _finite(clock.get('source_time_seconds'))
            or abs((clock.get('selected_frame_index', 1) - 1) / fps
                   - clock.get('source_time_seconds', 0)) > .000002
            or clock.get('source_frame_index') != max(1, int(round(clock['selected_frame_index'])))):
        errors.append('inconsistent_selected_source_clock')
    projection, signed = policy.get('projection'), policy.get('center_signed')
    edge, stable = policy.get('edge_fraction'), policy.get('stable_center_side')
    if (policy.get('kind') != 'finite_endpoint_center_uncertain'
            or policy.get('direction') != direction or policy.get('method') != 'interpolated'
            or not all(_finite(v) for v in (projection, signed, edge, stable))
            or not (0 < edge <= .15 and 0 < stable <= .08 and 0 <= projection < edge)
            or (signed if direction == 'in' else -signed) >= stable):
        errors.append('invalid_or_conflicting_policy_evidence')
    if not _finite(track.get('center_signed')) or not _finite(signed) \
            or abs(track.get('center_signed', 0) - signed) > .000002:
        errors.append('conflicting_center_observation')
    return {'tracking_id': track.get('track_id'), 'raw_tracking_id': track.get('raw_track_id'),
            'observed_frame_index': observation.get('frame_index'),
            'observed_time_seconds': observation.get('source_time_seconds'),
            'source_frame_index': clock.get('source_frame_index'),
            'source_time_seconds': clock.get('source_time_seconds'),
            'direction': direction, 'vehicle_type': clock.get('vehicle_type'),
            'crossing_method': clock.get('crossing_method'),
            'evidence_status': 'recorded-consistent' if not errors else 'inconsistent',
            'evidence_issues': errors, 'policy': policy,
            'physical_identity_proven': False}


def analyze_trace(report, events, gt, trace):
    """Pure trace projection; production entry verifies the export beforehand."""
    targets = {e['tracking_id'] for e in events
               if _integer(e.get('tracking_id')) and e.get('crossing_method') == 'interpolated'
               and e.get('vehicle_type') in TWO_WHEEL}
    target = defaultdict(list)
    metadata = None
    line = None
    suppressions = []
    provenance_issues = []
    frame_count = 0
    counter_observations = 0
    last_counter = None
    for obs in trace:
        if not isinstance(obs, dict):
            raise ValueError('Invalid trace observation')
        if obs.get('kind') == 'session_metadata':
            if metadata is not None:
                provenance_issues.append('duplicate_session_metadata')
            metadata = obs
            continue
        if obs.get('kind') == 'geometry_metadata':
            line = obs.get('line')
            continue
        if 'frame_index' not in obs:
            continue
        frame_count += 1
        if 'endpoint_precision_suppressed' in obs:
            value = obs['endpoint_precision_suppressed']
            counter_observations += 1
            if not _integer(value) or value < 0 or (last_counter is not None and value < last_counter):
                provenance_issues.append('invalid_or_nonmonotonic_suppression_counter')
            elif _integer(value):
                last_counter = value
        tracks = obs.get('gate_tracks', [])
        if not isinstance(tracks, list) or any(not isinstance(track, dict) for track in tracks):
            raise ValueError('Invalid gate-track evidence')
        for track in tracks:
            clock = track.get('crossing_clock_audit')
            decision = clock.get('producer_decision') if isinstance(clock, dict) else None
            if decision == SUPPRESSED or 'endpoint_precision_suppression' in track:
                suppressions.append(_suppression_record(obs, track, (metadata or {}).get('source_fps')))
            if not _integer(track.get('track_id')):
                provenance_issues.append('invalid_track_identity')
                continue
            if track['track_id'] in targets and track.get('final_gate_decision') in ACCEPTED:
                target[track['track_id']].append({
                    'frame': obs['frame_index'], 'time': obs.get('source_time_seconds'),
                    'center_signed': track.get('center_signed'),
                    'direction': track.get('primary_gate_direction'),
                    'label': track.get('label'), 'clock': clock,
                })
        if ('endpoint_precision_suppressed' in obs
                and _integer(obs['endpoint_precision_suppressed'])
                and obs['endpoint_precision_suppressed'] != len(suppressions)):
            provenance_issues.append('suppression_counter_frame_mismatch')
    provenance = _runtime_provenance(metadata or {})
    if not _valid_line(line):
        line = None
        if suppressions:
            provenance_issues.append('missing_geometry_for_suppression')
    enabled = (metadata or {}).get('endpoint_precision_guard_enabled')
    if provenance['status'] == 'inconsistent':
        provenance_issues.append('inconsistent_runtime_provenance')
    if enabled is not None and not isinstance(enabled, bool):
        provenance_issues.append('invalid_guard_setting')
    if suppressions and enabled is not True:
        provenance_issues.append('suppression_without_enabled_guard_metadata')
    if any(r['evidence_status'] != 'recorded-consistent' for r in suppressions):
        provenance_issues.append('inconsistent_suppression_records')
    if counter_observations and last_counter != len(suppressions):
        provenance_issues.append('suppression_counter_record_mismatch')
    if isinstance(enabled, bool) and 0 < counter_observations < frame_count:
        provenance_issues.append('incomplete_suppression_counter_evidence')
    if provenance_issues:
        suppression_status = 'inconsistent'
    elif (provenance['status'] != 'verified-schema' or not isinstance(enabled, bool)
          or (enabled and not counter_observations)):
        suppression_status = 'not-recorded'
    else:
        suppression_status = 'recorded' if enabled else 'disabled'
    actual_count = len(suppressions) if suppression_status in {'recorded', 'disabled'} else None
    matched = {e['ai_event_id'] for e in report['matched_items']}
    extra = {e['ai_event_id'] for e in report['false_positive_items']}
    rows = []
    evidence = []
    modern = provenance['status'] != 'legacy-unattested'
    for event in events:
        if event.get('crossing_method') != 'interpolated' or event.get('vehicle_type') not in TWO_WHEEL:
            continue
        if _integer(event.get('tracking_id')):
            chosen, status, count = _event_evidence(event, target.get(event['tracking_id'], []), modern=modern)
        else:
            chosen, status, count = None, 'missing-track-identity', 0
        if chosen is not None and (chosen.get('clock') or {}).get('producer_decision') == SUPPRESSED:
            chosen, status = None, 'persisted-suppressed-conflict'
            provenance_issues.append('suppressed_crossing_persisted')
            suppression_status, actual_count = 'inconsistent', None
        if chosen is not None and not _finite(chosen.get('center_signed')):
            chosen, status = None, 'missing-center-evidence'
        if line is None:
            chosen, status = None, 'missing-geometry-evidence'
        item = {'ai_event_id': event['id'], 'tracking_id': event['tracking_id'],
                'source_time_seconds': event.get('source_time_seconds'),
                'status': status, 'candidate_record_count': count,
                'gate_evidence_frame': chosen['frame'] if chosen is not None else None}
        evidence.append(item)
        if chosen is None:
            continue
        rejection = endpoint_precision_rejection(
            (tuple(line[0]), tuple(line[1])),
            (event.get('crossing_x'), event.get('crossing_y')),
            chosen['center_signed'], event['direction'], event['vehicle_type'], event['crossing_method'])
        if rejection:
            rows.append({'ai_event_id': event['id'], 'source_time_seconds': event['source_time_seconds'],
                         'tracking_id': event['tracking_id'], 'direction': event['direction'],
                         'score_assignment': 'matched' if event['id'] in matched else 'unmatched' if event['id'] in extra else 'unknown',
                         'gate_evidence_frame': chosen['frame'], 'evidence_status': status, 'policy': rejection})
    return _json_safe({
        'format': 'traffic-ai-finite-endpoint-counterfactual', 'version': 2,
        'benchmark_id': report['benchmark']['id'], 'session_id': report['session_id'],
        'observed_ai_total': len(events), 'observed_gt_total': len(gt),
        'observed_matched': report['matched'], 'observed_missed': report['missed'],
        'observed_extra': report['false_positives'],
        # Legacy keys continue to describe persisted events only.
        'flagged_event_count': len(rows),
        'flagged_previously_matched': sum(x['score_assignment'] == 'matched' for x in rows),
        'flagged_previously_unmatched': sum(x['score_assignment'] == 'unmatched' for x in rows),
        'candidates': rows,
        'runtime_provenance': provenance,
        'actual_suppression_count': actual_count,
        'runtime_suppression_evidence': {
            'status': suppression_status, 'guard_enabled': enabled if isinstance(enabled, bool) else None,
            'observed_suppression_rows': len(suppressions),
            'consistent_suppression_rows': sum(r['evidence_status'] == 'recorded-consistent' for r in suppressions),
            'final_suppression_counter': last_counter,
            'counter_observations': counter_observations,
            'verified_trace_frames': frame_count,
            'issues': sorted(set(provenance_issues)), 'suppressions': suppressions},
        'event_evidence': evidence,
        'event_evidence_status_counts': dict(sorted(Counter(r['status'] for r in evidence).items())),
        'unknown_event_evidence_count': sum(r['gate_evidence_frame'] is None for r in evidence),
        'disclaimer': 'Read-only audit. Remaining persisted-event candidates are a past-trace approximation; producer suppressions are separate recorded decisions. Missing evidence is unknown, not zero. No new inference, identity proof, or score/GT/event mutation. Re-run the identical clip to verify counting changes.'})


def analyze(export: Path) -> dict:
    _verify_export(export)
    with ZipFile(export) as z:
        report = json.loads(z.read('report.json'))
        events = json.loads(z.read('events.json'))
        gt = json.loads(z.read('ground-truth.json'))
        with gzip.open(z.open('benchmark-trace.jsonl.gz'), 'rt', encoding='utf-8') as frames:
            return analyze_trace(report, events, gt, (json.loads(row) for row in frames))


def write_report(report, output_directory):
    output_directory.mkdir(parents=True, exist_ok=True)
    (output_directory / 'endpoint-precision.json').write_text(
        json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')
    runtime = report['runtime_suppression_evidence']
    actual = report['actual_suppression_count']
    lines = [f"# Endpoint audit | Benchmark #{report['benchmark_id']} / Session #{report['session_id']}", '',
             f"Observed {report['observed_gt_total']} GT / {report['observed_ai_total']} AI / {report['observed_missed']} missed / {report['observed_extra']} extra.",
             f"Runtime: {report['runtime_provenance']['runtime_version'] or 'unattested'}; producer suppression evidence: **{runtime['status']}**.",
             f"Actual recorded endpoint suppressions: **{actual if actual is not None else 'unknown'}**; observed claim rows: {runtime['observed_suppression_rows']}.", '',
             '## Recorded producer suppressions', '',
             '| Crossing time(s) | Confirmation frame | Track / raw | Direction | Evidence |',
             '|---:|---:|---|---|---|']
    for row in runtime['suppressions']:
        time = row['source_time_seconds']
        time_text = f'{time:.6f}' if _finite(time) else 'unknown'
        lines.append(f"| {time_text} | {row['observed_frame_index']} | {row['tracking_id']} / {row['raw_tracking_id']} | {row['direction']} | {row['evidence_status']} |")
    lines += ['', '## Remaining persisted-event counterfactual', '',
              f"Flagged {report['flagged_event_count']} remaining candidates: {report['flagged_previously_matched']} previously matched, {report['flagged_previously_unmatched']} previously unmatched.",
              f"Events with unknown evidence: {report['unknown_event_evidence_count']}.", '',
              '| Time(s) | Event | Track | Assignment | Projection | Center signed | Evidence |',
              '|---:|---:|---:|---|---:|---:|---|']
    for row in report['candidates']:
        lines.append(f"| {row['source_time_seconds']:.3f} | {row['ai_event_id']} | {row['tracking_id']} | {row['score_assignment']} | {row['policy']['projection']:.4f} | {row['policy']['center_signed']:.4f} | {row['evidence_status']} |")
    if runtime['issues']:
        lines += ['', 'Evidence issues: ' + ', '.join(runtime['issues']) + '.']
    lines += ['', '**Warning:** ' + report['disclaimer']]
    (output_directory / 'endpoint-precision.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--export', required=True, type=Path)
    parser.add_argument('--output-directory', required=True, type=Path)
    args = parser.parse_args()
    report = analyze(args.export)
    write_report(report, args.output_directory)
    actual = report['actual_suppression_count']
    print(f"Benchmark #{report['benchmark_id']} / Session #{report['session_id']}: "
          f"{report['flagged_event_count']} remaining endpoint candidates; "
          f"{actual if actual is not None else 'unknown'} actual producer suppressions "
          f"({report['runtime_suppression_evidence']['status']}); "
          f"{report['unknown_event_evidence_count']} events with unknown evidence; reports: {args.output_directory}")


if __name__ == '__main__':
    main()
