"""Reproducible editorial workflow with disclosed fictional, scripted responses."""
import argparse
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from contentmaxxing.engine import Engine
from contentmaxxing.overview import overview
from contentmaxxing.planning import Planning
from contentmaxxing.scheduler import Scheduler
from contentmaxxing.store import Store, atomic_json, atomic_text


def demo(workspace):
    root = Path(workspace)
    fixtures = Path(__file__).resolve().parents[1] / 'tests/fixtures'
    Store(root).init('extractive')
    engine = Engine(root)
    engine.onboard(json.loads((fixtures / 'creator.json').read_text()))
    source = engine.capture(fixtures / 'transcript.txt', consent='Fictional demonstration')
    ideas = engine.mine(source['id'])
    checklist = next(i for i in ideas if i['source_reference'][0]['start_line'] == 3)
    checklist['priority'] = 100
    engine.store.put('ideas', checklist)
    cfg = Scheduler(engine).config()
    cfg['counts'] = {'x': 3, 'linkedin': 1}
    atomic_text(root / 'workflows.yaml', yaml.safe_dump(cfg))
    engine = Engine(root, provider_name='external')
    scheduler = Scheduler(engine)
    run = scheduler.run()
    task = engine.store.get('tasks', run['editorial_task_id'])
    candidates = {i['source_reference'][0]['start_line']: i for i in task['inputs']['candidates']}
    choices = [
        (5, 'x', 'short post', 'Trust', 'Name the handoff owner before automating',
         'Spot a handoff that has no person responsible.',
         'A concrete fix from the source fits the creator’s operator positioning.',
         'The fix for our handoff problem was a shared log with one named owner per request.'),
        (2, 'x', 'short post', 'Bookmarks / Saves', 'Keep the question next to the decision',
         'A small change to where client-call questions get stored.',
         'The source gives a repeatable action without an invented productivity claim.',
         'I save the exact client question next to the decision it changed.\n\nThe next person needs the reason, not just the decision.'),
        (4, 'linkedin', 'LinkedIn post', 'Authority', 'A complete checklist can still have an unowned handoff',
         'Review the next handoff for responsibility, not just completed steps.',
         'Business context makes the documented overnight delay useful to studio owners.',
         'Our first onboarding checklist skipped the handoff owner. Requests waited overnight.\n\nBefore adding another step to an onboarding checklist, I would check whether the next request has a named owner. A complete list of actions can still leave the handoff unclear.')]
    slots = []
    for line, platform, fmt, job, angle, payoff, reason, body in choices:
        idea = candidates[line]
        slots.append({'idea_id': idea['id'], 'platform': platform, 'format': fmt, 'job': job,
                      'angle': angle, 'reader_payoff': payoff, 'reason': reason,
                      'source_reference': idea['source_reference'], 'basis': 'source',
                      'performance_ids': [], 'experiment_id': None})
    chosen = {s['idea_id'] for s in slots}
    result = {'strategy': 'Make handoff ownership and decision context useful before adding more volume. No measured performance claims yet.',
              'slots': slots,
              'deferred': [{'idea_id': i['id'], 'reason':
                  'The checklist claim needs an actual artifact or comparison to develop beyond a general opinion.'
                  if i['id'] == checklist['id'] else 'Keep this adjacent idea for a later batch instead of repeating the same point.'}
                  for i in task['inputs']['candidates'] if i['id'] not in chosen],
              'questions': ['Is there a redacted handoff log we can show in a future walkthrough?']}
    atomic_json(root / 'data/task-results/editorial.json', result)
    plan = engine.complete_task(task['id'], result)[0]
    briefs = {(c[1], candidates[c[0]]['id']): c[-1] for c in choices}
    for _ in range(10):
        run = scheduler.run(run_id=run['id'])
        if run['status'] == 'COMPLETED':
            break
        for draft in engine.store.list('tasks'):
            if draft['operation'] != 'draft' or draft['status'] != 'PENDING':
                continue
            inputs = draft['inputs']
            ref = inputs['idea']['source_reference'][0]
            output = {'body': briefs[(inputs['platform'], inputs['idea']['id'])], 'title': '', 'framework': None,
                      'claims': [{'claim': ref['quote'], 'source_reference': ref}],
                      'quality_notes': ['Scripted fictional example; creator voice and interpretation still need review.']}
            atomic_json(root / 'data/task-results' / (draft['id'] + '.json'), output)
            engine.complete_task(draft['id'], output)
    assert run['status'] == 'COMPLETED'
    saved = Planning(engine).get(plan['id'])
    assert saved['status'] == 'COMPLETED' and saved['run_id'] == run['id']
    Planning(engine).create(plan['id'])
    assert len(engine.store.list('content')) == 3
    report = {'plan_id': plan['id'], 'run_id': run['id'], 'drafts': 3,
              'deferred': len(saved['deferred']), 'unfilled_x_slots': saved['stages'][0]['shortfall'],
              'high_priority_idea_deferred': checklist['id'] in {i['idea_id'] for i in saved['deferred']},
              'resume_duplicate_drafts': 0, 'next': overview(root)['next_action']['command'],
              'statuses': [c['status'] for c in engine.store.list('content')],
              'notice': 'Fictional creator and scripted planning/writing responses. No live model, publishing, or human quality evaluation.'}
    atomic_json(root / 'editorial-demo-result.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', required=True)
    print(json.dumps(demo(parser.parse_args().workspace), indent=2))
