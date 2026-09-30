"""Offline journey with fictional fixtures and literal external-task results."""
import argparse
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from contentmaxxing.engine import Engine
from contentmaxxing.overview import overview
from contentmaxxing.planning import Planning
from contentmaxxing.store import Store, atomic_json, atomic_text


def demo(workspace):
    root = Path(workspace)
    fixtures = Path(__file__).resolve().parents[1] / 'tests/fixtures'
    stages = [overview(root)['stage']]
    Store(root).init('extractive')
    engine = Engine(root)
    engine.onboard(json.loads((fixtures / 'creator.json').read_text()))
    source = engine.capture(fixtures / 'transcript.txt', consent='Fictional demo')
    ideas = engine.mine(source['id'])
    for idea in ideas:
        engine.select(idea['id'], format_name='short post', job='Bookmarks / Saves')
    stages.append(overview(root)['stage'])
    cfg = yaml.safe_load((root / 'workflows.yaml').read_text())
    cfg['counts'] = {'x': 5}
    atomic_text(root / 'workflows.yaml', yaml.safe_dump(cfg))
    plan = Planning(engine).plan()  # Explicit offline heuristic; this demo tests navigation.
    engine = Engine(root, provider_name='external')
    planning = Planning(engine)
    result = planning.create(plan['id'])
    stages.append(overview(root)['stage'])
    waiting = result['run']['status']
    # Stand in for the host with disclosed literal-source results; no model/API call.
    for task in engine.store.list('tasks'):
        if task['status'] == 'COMPLETED':
            continue
        ref = task['inputs']['idea']['source_reference'][0]
        engine.complete_task(task['id'], {'body': ref['quote'], 'title': '',
            'claims': [{'claim': ref['quote'], 'source_reference': ref}],
            'quality_notes': ['Demo source excerpt, not native creative writing.'], 'framework': None})
    result = planning.create(plan['id'])
    stages.append(overview(root)['stage'])
    posts = engine.store.list('content')
    for post in posts:
        engine.transition(post['id'], 'APPROVED')  # Simulated creator decisions in demo only.
    stages.append(overview(root)['stage'])
    for index, post in enumerate(posts):
        engine.transition(post['id'], 'PUBLISHED', url='https://example.com/fictional/' + str(index))
    stages.append(overview(root)['stage'])
    for index, post in enumerate(posts):
        engine.manual_metrics(post['id'], {'impressions': 1000, 'bookmarks': 40 if index == 0 else 4})
    nav = overview(root)
    stages.append(nav['stage'])
    opportunities = Engine(root, provider_name='extractive').compound(nav['next_action']['arguments']['content_ids'][0])
    stages.append(overview(root)['stage'])
    planning.create(plan['id'])
    assert len(engine.store.list('content')) == 5, 'Resume must not create another batch'
    result = {'workspace': str(root.resolve()), 'stages': stages, 'plan_id': plan['id'],
              'external_task_checkpoint': waiting, 'drafts': len(posts),
              'compound_opportunities': len(opportunities), 'repeat_create_duplicate_drafts': 0,
              'notice': 'Fictional creator/metrics, simulated approvals/publication, literal source excerpts. No live model or publishing calls.'}
    atomic_json(root / 'journey-demo-result.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', required=True)
    print(json.dumps(demo(parser.parse_args().workspace), indent=2))
