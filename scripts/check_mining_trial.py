"""Check saved mining mechanics and surface a rubric for separate editorial review."""
import argparse
import hashlib
import json
from pathlib import Path

from contentmaxxing.engine import Engine
from contentmaxxing.mining import source_progress, validate_window
from contentmaxxing.store import normalize


def snapshot(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


def check(workspace, evidence=None):
    root = Path(workspace).resolve()
    trial = json.loads((root / 'TRIAL.json').read_text())
    engine = Engine(root, provider_name='external')
    store = engine.store
    source_id = trial['source_id']
    status = source_progress(store, source_id)
    assert status['status'] == 'COMPLETED', status
    assert status['completed_chunks'] == status['total_chunks'] >= 3
    assert status['covered_chars'] == status['source_chars']
    tasks = [t for t in store.list('tasks') if t['operation'] == 'mine' and t['inputs']['source_id'] == source_id]
    assert len(tasks) == status['total_chunks']
    for task in tasks:
        assert task['status'] == 'COMPLETED'
        for identifier in task['result_ids']:
            matching = []
            for ref in store.get('ideas', identifier)['source_reference']:
                if ref['source_id'] != source_id:
                    continue
                try:
                    validate_window(task['inputs'], ref)
                    matching.append(ref)
                except ValueError:
                    pass  # A merged idea may also retain evidence from another window.
            assert matching, 'Saved result has no surviving evidence in its originating window: ' + identifier
    ideas = [store.get('ideas', identifier) for identifier in status['result_ids']]
    assert ideas and len({normalize(i['topic']) for i in ideas}) == len(ideas)
    assert all(i['status'] == 'BACKLOG' and i['format'] is None for i in ideas)
    assert not store.list('content')
    for idea in ideas:
        for ref in idea['source_reference']:
            store.validate_reference(ref)
    before = snapshot(store.data)
    resumed = engine.mine(source_id)
    assert {i['id'] for i in resumed} == {i['id'] for i in ideas}
    assert snapshot(store.data) == before, 'Completed source resume must preserve all creator data.'
    rubric = json.loads((Path(__file__).resolve().parents[1] / 'tests/fixtures/mining-workshop-rubric.json').read_text())
    review = []
    for family in rubric['topic_families']:
        candidates = [{'id': i['id'], 'topic': i['topic'], 'notes': i['notes'], 'proof': i['proof'],
                       'article_candidate': i['article_candidate'], 'source_reference': i['source_reference']}
                      for i in ideas if any(r['source_id'] == source_id and any(r['start_line'] <= line <= r['end_line'] for line in family['lines'])
                                           for r in i['source_reference'])]
        review.append({**family, 'candidates': candidates, 'human_verdict': None})
    trace = None
    if evidence:
        events = [json.loads(line) for line in (Path(evidence) / 'mine.events.jsonl').read_text().splitlines() if line.strip()]
        assert events[-1]['type'] == 'turn.completed', 'Host trace has no terminal success.'
        trace = {'events': len(events), 'terminal_event': events[-1]['type'], 'usage': events[-1].get('usage'),
                 'failed_commands': sum(e.get('item', {}).get('type') == 'command_execution' and
                                        e.get('item', {}).get('exit_code') not in (None, 0) for e in events)}
    return {'verdict': 'mechanical_checks_passed', 'workspace': str(root), 'source_id': source_id,
            'coverage': status, 'ideas': len(ideas), 'article_candidates': sum(i['article_candidate'] for i in ideas),
            'resume_data_changes': 0, 'drafts_created': 0, 'trace': trace,
            'editorial_review': {'status': 'NEEDS_HUMAN_REVIEW', 'rubric': rubric['id'], 'families': review,
                                 'whole_bank': rubric['whole_bank_review']},
            'notice': 'Fictional native mining trial. Exact quotations, span matches and coverage do not prove semantic completeness, speaker truth or a useful nonredundant bank.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--evidence')
    parser.add_argument('--output')
    args = parser.parse_args()
    result = check(args.workspace, args.evidence)
    text = json.dumps(result, indent=2, ensure_ascii=False) + '\n'
    if args.output:
        Path(args.output).write_text(text)
    print(text, end='')
