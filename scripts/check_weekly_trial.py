"""Check saved weekly-trial behavior without grading voice or editorial taste.

Run with the installed engine after the native host exits. Requires the fixture
seed from examples/weekly_trial_seed.py and the host's JSONL event trace. Repeats
the completed run/plan to verify that resuming does not change creator data.
"""
import argparse
import hashlib
import json
from pathlib import Path

from contentmaxxing.analytics import winners
from contentmaxxing.planning import Planning
from contentmaxxing.engine import Engine, FRAMEWORKS
from contentmaxxing.retrieval import validate_task_reference
from contentmaxxing.scheduler import Scheduler


def check(workspace, events_file):
    root = Path(workspace).resolve()
    seed = json.loads((root / 'trial-seed.json').read_text())
    events = [json.loads(line) for line in Path(events_file).read_text().splitlines() if line.strip()]
    assert events[-1]['type'] == 'turn.completed', 'The native host did not finish its turn.'
    engine = Engine(root, provider_name='external')
    store = engine.store
    runs = [r for r in store.list('runs') if r['workflow'] == 'weekly-editorial']
    assert len(runs) == 1, 'Expected one weekly run, not a regenerated batch.'
    run = runs[0]
    assert run['status'] == 'COMPLETED', 'Weekly execution is not complete.'
    assert all(s['status'] == 'COMPLETED' for s in run['stages'])
    plan = Planning(engine).get(run['editorial_plan_id'])
    assert plan['status'] == 'COMPLETED' and plan['run_id'] == run['id']
    assert plan['origin_run_id'] == run['id']
    plan_task = store.get('tasks', plan['planning_task_id'])
    report = store.get('reports', run['report_id'])
    assert plan_task['inputs']['editorial_report']['id'] == report['id']
    assert seed['expected_winner'] in report['compound']
    measured = {w['content_id']: w for w in winners(store, report['end_date'])}
    assert measured[seed['expected_winner']]['metric'] == 'bookmarks_per_1k'
    assert measured[seed['expected_winner']]['lift'] == 10

    historical = set(seed['history_posts'])
    posts = {p['id']: p for p in store.list('content') if p['id'] not in historical}
    assert posts, 'No review drafts were saved.'
    seen, coverage = set(), {}
    for stage in plan['stages']:
        platform = stage['name']
        assert len(stage['slots']) <= seed['counts'][platform]
        coverage[platform] = {'drafts': len(stage['slots']), 'unfilled': stage['shortfall']}
        for slot in stage['slots']:
            # Runtime slot IDs live in the run; the saved plan retains briefs.
            actual = next(s for s in next(s for s in run['stages'] if s['name'] == platform)['slots']
                          if s['idea_id'] == slot['idea_id'])
            post = posts[actual['content_id']]
            assert post['id'] not in seen, 'One saved draft appears in multiple slots.'
            seen.add(post['id'])
            task = store.get('tasks', actual['task_id'])
            assert task['status'] == 'COMPLETED'
            assert task['inputs']['editorial_brief'] == slot['editorial_brief']
            assert (post['platform'], post['format'], post['primary_job']) == (platform, slot['format'], slot['job'])
            assert post['status'] == 'NEEDS_REVIEW'
            assert not any(post.get(k) for k in ['approved_at', 'scheduled_at', 'published_at', 'published_urls', 'remote'])
            if platform in ('x_article', 'substack'):
                assert post['framework'] in FRAMEWORKS
            for ref in post['source_reference']:
                store.validate_reference(ref)
            for claim in post['claims']:
                store.validate_reference(claim['source_reference'])
                validate_task_reference(task['inputs'], claim['source_reference'])
    assert seen == set(posts), 'Unexpected new drafts exist outside the saved week.'
    assert len({p['body'] for p in posts.values()}) == len(posts), 'Exact copied drafts across slots.'
    assert all(t['status'] == 'COMPLETED' for t in store.list('tasks')), 'Unfinished tasks remain.'
    followups = [i for i in store.list('ideas') if i['parent_content_id'] == seed['expected_winner']]
    for idea in followups:
        assert idea['addition'] in {'context', 'proof', 'story', 'format', 'argument', 'utility'}
        compound_task = store.get('tasks', idea['development']['task_id'])
        for ref in idea['source_reference']:
            store.validate_reference(ref)
            validate_task_reference(compound_task['inputs'], ref)
    def data_hashes():
        return {str(p.relative_to(store.data)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in store.data.rglob('*') if p.is_file()}
    before = data_hashes()
    Scheduler(engine).run(run_id=run['id'])
    Planning(engine).create(plan['id'])
    assert before == data_hashes(), 'Resuming a completed week changed saved data.'
    failures = [e['item'] for e in events if e.get('item', {}).get('exit_code', 0)]
    return {'verdict': 'mechanical_checks_passed', 'run_id': run['id'], 'plan_id': plan['id'],
            'report_id': report['id'], 'review_drafts': len(posts), 'coverage': coverage,
            'deferred': len(plan['deferred']), 'questions': plan['questions'],
            'winner': measured[seed['expected_winner']], 'followups': len(followups),
            'resume_data_changes': 0, 'events': len(events), 'failed_commands': len(failures),
            'usage': events[-1].get('usage'),
            'notice': 'Fictional history and sources; native model-generated week. '
                      'Exact citations and lifecycle checks do not grade meaning, voice, novelty or usefulness. '
                      'Initial failed commands remain in the trace.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--events', required=True)
    args = parser.parse_args()
    print(json.dumps(check(args.workspace, args.events), indent=2))
