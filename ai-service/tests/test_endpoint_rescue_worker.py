"""Execute the actual worker admission statements, without a detector replay."""
import ast
import copy
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.counting import CountingLine, LineCrossingCounter
from app.finite_endpoint_guard import endpoint_precision_rejection
from app.worker import PipelineWorker


def _worker_source():
    path = Path(__file__).parents[1] / 'app' / 'worker.py'
    tree = ast.parse(path.read_text(encoding='utf-8'))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'PipelineWorker')
    return path, cls


def _admission_statements():
    path, cls = _worker_source()
    run = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == 'run')
    for parent in ast.walk(run):
        for _, children in ast.iter_fields(parent):
            if not isinstance(children, list):
                continue
            for index, node in enumerate(children):
                if not isinstance(node, ast.If):
                    continue
                if (isinstance(node.test, ast.Call) and isinstance(node.test.func, ast.Name)
                        and node.test.func.id == 'getattr' and len(node.test.args) >= 2
                        and isinstance(node.test.args[1], ast.Constant)
                        and node.test.args[1].value == '_endpoint_precision_guard_enabled'):
                    # Use the contiguous production statements through event
                    # admission, including HumanGuard/context/count side effects.
                    suffix = children[index:]
                    assert isinstance(suffix[-1], ast.Expr)
                    assert isinstance(suffix[-1].value, ast.Call)
                    assert isinstance(suffix[-1].value.func, ast.Attribute)
                    assert suffix[-1].value.func.attr == 'append'
                    assert suffix[-1].value.func.value.id == 'pending_crossing_events'
                    loop = ast.For(target=ast.Name(id='_candidate', ctx=ast.Store()),
                                   iter=ast.Tuple(elts=[ast.Constant(1)], ctx=ast.Load()),
                                   body=copy.deepcopy(suffix), orelse=[])
                    return compile(ast.fix_missing_locations(ast.Module(body=[loop], type_ignores=[])),
                                   str(path), 'exec')
    raise AssertionError('Endpoint admission block missing')


def _worker_fixture():
    worker = PipelineWorker.__new__(PipelineWorker)
    worker.state = SimpleNamespace(
        total_count=0, counts_by_type={}, in_count=0, out_count=0,
        direct_crossings=0, interpolated_crossings=0, rescued_crossings=0,
        endpoint_precision_suppressed=0, endpoint_rescue_suppressed=0,
        human_guard_pending_crossings=0, rejected_outside_road=0,
    )
    worker._committed_in_count = worker._committed_out_count = 0
    worker._endpoint_precision_guard_enabled = True
    worker._endpoint_rescue_guard_enabled = True
    worker._raw_handoff_guard_enabled = False
    worker._pending_guard_crossings = {}
    worker.calls = []
    worker._observe_human_guard = lambda *args, **kwargs: (worker.calls.append('human') or ('accepted', None))
    worker._human_guard_policy = SimpleNamespace(status=lambda _: 'accepted')
    worker._commit_bicycle_context_rescue = lambda *args, **kwargs: worker.calls.append('context')
    return worker


def _admit(worker, counter, *, direction='out', method='rescued', center=-.02,
           label='motorcycle', frame=20, context=None):
    trace = {'crossing_clock_audit': {'producer_decision': 'committed_before_submit'}}
    env = {
        'self': worker, 'counter': counter,
        'endpoint_precision_rejection': endpoint_precision_rejection,
        'TWO_WHEEL_LABELS': {'motorcycle', 'bicycle'},
        'line_a': (100, 500), 'line_b': (900, 500), 'width': 1000, 'height': 1000,
        'crossing_x': .156, 'crossing_y': .5, 'center_signed': center,
        'direction': direction, 'crossing_method': method, 'event_label': label,
        'track_id': 77, 'frame_index': frame, 'event_frame_index': frame,
        'event_confidence': .8, 'source_time_seconds': (frame - 1) / 25,
        'analysis_frame': None, 'rect': (140, 450, 172, 530), 'device': 'cpu',
        'use_half': False, 'velocity': (0., -1.), 'context_trace': context or {},
        'gate_trace_track': trace, 'pending_crossing_events': [],
    }
    exec(_admission_statements(), env)
    return trace, env['pending_crossing_events']


def test_v05118_endpoint_rescue_flags_require_video_base_guard_and_extension():
    path, cls = _worker_source()
    init = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == '__init__')
    names = {'_endpoint_precision_guard_enabled', '_endpoint_rescue_guard_enabled'}
    body = [node for node in init.body if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Attribute) and target.attr in names for target in node.targets)]
    assert len(body) == 2
    compiled = compile(ast.fix_missing_locations(ast.Module(body=body, type_ignores=[])), str(path), 'exec')
    for source, base, extension, expected in [
        ('video', '1', '1', True), ('video', '1', '0', False),
        ('video', 'off', '1', False), ('rtsp', '1', '1', False),
    ]:
        worker = SimpleNamespace()
        with patch.dict(os.environ, {'AI_FINITE_ENDPOINT_PRECISION_GUARD': base,
                                     'AI_ENDPOINT_RESCUE_GUARD': extension}):
            exec(compiled, {'self': worker, 'payload': SimpleNamespace(source_type=source), 'os': os})
        assert worker._endpoint_rescue_guard_enabled is expected


def test_v05118_rescue_suppression_keeps_gate_closed_without_human_context_or_event_commit():
    counter = LineCrossingCounter(CountingLine(.1, .5, .9, .5))
    assert counter.register_external_crossing(77, 'out', 20, (156, 500), mode='rescued')
    gate = counter._tracks[77]
    worker = _worker_fixture()
    context = {'method': 'weak_motor', 'audit': {'commit_status': 'proposed'}}
    trace, admitted = _admit(worker, counter, context=context)
    assert trace['endpoint_precision_suppression']['method'] == 'rescued'
    assert trace['crossing_clock_audit']['producer_decision'] == 'finite_endpoint_rescue_center_uncertain_suppressed'
    assert worker.state.endpoint_precision_suppressed == worker.state.endpoint_rescue_suppressed == 1
    assert worker.state.total_count == worker.state.in_count == worker.state.out_count == 0
    assert worker.state.rescued_crossings == 0 and worker.state.human_guard_pending_crossings == 0
    assert worker.calls == [] and worker._pending_guard_crossings == {} and admitted == []
    assert context['audit']['commit_status'] == 'proposed'
    assert gate.counted_directions == {'out'} and not gate.armed and gate.last_count_frame == 20
    # Small alternating observations cannot re-arm the gate and produce an
    # immediate replacement IN/OUT after the rejected rescue proposal.
    for frame, y in [(21, 490), (22, 510), (23, 490), (24, 510)]:
        assert counter.update(77, (156, y), 1000, 1000, frame) is None
        assert not gate.armed and gate.counted_directions == {'out'}
    # Remaining on the destination side cannot replay the suppressed OUT.
    for frame in range(25, 36):
        assert counter.update(77, (156, 450), 1000, 1000, frame) is None
    assert gate.counted_directions == {'out'}
    # A later observed return across the gate is still a distinct IN passage.
    assert counter.update(77, (156, 550), 1000, 1000, 36) == 'in'
    returned_trace, returned = _admit(worker, counter, direction='in', method='direct', center=.05, frame=36)
    assert 'endpoint_precision_suppression' not in returned_trace
    assert len(returned) == 1 and returned[0][2] == 'in'
    assert worker.calls == ['human']
    assert worker.state.total_count == worker.state.in_count == 1 and worker.state.out_count == 0
    assert worker.state.endpoint_rescue_suppressed == 1


def test_v05118_extension_optout_and_stable_center_keep_real_admission():
    for enabled, center, method in [(False, -.02, 'rescued'), (True, -.05, 'rescued'), (True, -.02, 'direct')]:
        worker = _worker_fixture()
        worker._endpoint_rescue_guard_enabled = enabled
        counter = LineCrossingCounter(CountingLine(.1, .5, .9, .5))
        trace, admitted = _admit(worker, counter, center=center, method=method)
        assert 'endpoint_precision_suppression' not in trace
        assert len(admitted) == 1 and worker.state.total_count == worker.state.out_count == 1
        assert worker.state.endpoint_precision_suppressed == worker.state.endpoint_rescue_suppressed == 0


def test_v05118_interpolation_keeps_existing_counter_and_audit_kind():
    worker = _worker_fixture()
    counter = LineCrossingCounter(CountingLine(.1, .5, .9, .5))
    trace, admitted = _admit(worker, counter, method='interpolated')
    assert admitted == [] and worker.calls == []
    assert worker.state.endpoint_precision_suppressed == 1 and worker.state.endpoint_rescue_suppressed == 0
    assert trace['endpoint_precision_suppression']['kind'] == 'finite_endpoint_center_uncertain'
    assert trace['crossing_clock_audit']['producer_decision'] == 'finite_endpoint_center_uncertain_suppressed'
