"""Create a fictional experiment with unequal observation ages and missing data.

Uses offline literal excerpts; publications and metrics are simulated. Nothing
is sent to a platform or model. No interpretation is pre-filled.
"""
import argparse
import json
from pathlib import Path

from contentmaxxing.engine import Engine
from contentmaxxing.store import Store, atomic_json, atomic_text


def seed(workspace):
    fixtures = Path(__file__).resolve().parents[1] / 'tests/fixtures'
    Store(workspace).init('extractive')
    engine = Engine(workspace)
    engine.onboard(json.loads((fixtures / 'creator.json').read_text()))
    source = engine.capture(fixtures / 'transcript.txt', consent='fictional QA fixture')
    ideas = engine.mine(source['id'])
    posts = []
    for index, idea in enumerate(ideas):
        engine.select(idea['id'], format_name='short post' if index < 3 else 'checklist', job='Bookmarks / Saves')
        post = engine.draft(idea['id'])[0]
        engine.transition(post['id'], 'APPROVED')
        engine.transition(post['id'], 'PUBLISHED', url='https://example.com/fictional/' + post['id'],
                          published_at='2026-09-20T12:00:00Z' if index < 3 else '2026-09-23T12:00:00Z')
        bookmarks = [8, 10, 12, 15, 21, None][index]
        engine.manual_metrics(post['id'], {'impressions': 1000, 'bookmarks': bookmarks}, '2026-09-24T12:00:00Z')
        posts.append(post['id'])
    experiment = engine.experiment({'hypothesis': 'Checklists help this audience save a working process more often than short posts.',
        'start_date': '2026-09-20', 'end_date': '2026-09-23', 'metric': 'bookmarks_per_1k', 'content_ids': posts})
    view = engine.measure_experiment(experiment['id'], '2026-09-25T00:00:00Z')
    atomic_json(engine.store.root / 'experiment-demo.json', view)
    atomic_text(engine.store.root / 'DEMO.md', '# Fictional experiment demo\n\n'
        'Morgan and all six posts, publication URLs and metric observations are test fixtures.\n'
        'Nothing was actually published. Drafts are literal source excerpts, not a writing-quality trial.\n'
        'Experiment: ' + experiment['id'] + '\n'
        'Inspect experiment-demo.json or run experiments measure with --as-of 2026-09-25T00:00:00Z.\n')
    return {'workspace': str(engine.store.root), 'experiment_id': experiment['id'],
            'sample_size': view['sample_size'], 'groups': view['groups'], 'statuses': view['statuses']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True)
    print(json.dumps(seed(parser.parse_args().workspace), indent=2))
