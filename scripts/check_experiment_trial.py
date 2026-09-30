"""Inspect a completed fictional native experiment trial without grading prose."""
import argparse
import hashlib
import json
from pathlib import Path

from contentmaxxing.engine import Engine


def check(workspace, evidence):
    root, evidence = Path(workspace), Path(evidence)
    engine = Engine(root)
    baseline = json.loads((evidence / 'before.json').read_text())
    original = json.loads((root / 'experiment-demo.json').read_text())
    identifier = original['experiment_id']
    allowed = {'data/experiments/' + identifier + '.json', 'data/creator/LEARNINGS.md'}
    changed = [name for name, digest in baseline.items()
               if not (root / name).exists() or hashlib.sha256((root / name).read_bytes()).hexdigest() != digest]
    assert set(changed) == allowed, changed
    current = engine.measure_experiment(identifier, original['as_of'])
    assert {k:v for k,v in current.items() if k != 'recorded_interpretation'} == {
        k:v for k,v in original.items() if k != 'recorded_interpretation'}
    assert all(current['recorded_interpretation'].values()), 'All three requested interpretation fields must be saved.'
    data_before = {str(p.relative_to(root)):p.read_bytes() for p in engine.store.data.rglob('*') if p.is_file()}
    unexpected_new = [name for name in data_before if name not in baseline
                      and not name.startswith(('data/reports/', 'data/task-results/'))]
    assert not unexpected_new, unexpected_new
    engine.experiment({'id': identifier})
    assert data_before == {str(p.relative_to(root)):p.read_bytes() for p in engine.store.data.rglob('*') if p.is_file()}
    events = [json.loads(line) for line in (evidence / 'review.events.jsonl').read_text().splitlines()]
    assert events[-1]['type'] == 'turn.completed', events[-1]
    failures = [event['item']['command'] for event in events if event['type'] == 'item.completed'
                and event.get('item', {}).get('type') == 'command_execution' and event['item']['exit_code'] != 0]
    return {'experiment_id': identifier, 'content_count': current['content_count'], 'sample_size': current['sample_size'],
        'changed_existing_files': sorted(changed), 'observations_and_membership_preserved': True,
        'identity_sources_content_preserved': True, 'repeated_save_data_unchanged': True,
        'new_content_or_observations': False,
        'recorded_interpretation': current['recorded_interpretation'], 'trace_events': len(events),
        'recoverable_command_failures': failures, 'usage': events[-1].get('usage'),
        'human_grades': 0, 'editorial_status': 'NEEDS_HUMAN_REVIEW',
        'notice': 'One native Codex response to a fictional experiment. Structural checks do not grade the interpretation.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--evidence', required=True)
    args = parser.parse_args()
    result = check(args.workspace, args.evidence)
    (Path(args.evidence) / 'checks.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
