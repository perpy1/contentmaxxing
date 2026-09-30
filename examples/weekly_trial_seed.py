"""Seed fictional history for a fresh-host weekly trial, without writing its plan.

Run with the installed engine. The host must mine the new source, choose a plan,
write native drafts and develop the winner itself. Metrics and publication URLs
are explicitly synthetic test setup, never real creator results.
"""
import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from contentmaxxing.engine import Engine
from contentmaxxing.feedback import Feedback
from contentmaxxing.installation import install
from contentmaxxing.scheduler import Scheduler
from contentmaxxing.store import Store, atomic_json, atomic_text


def seed(workspace):
    root = Path(workspace).resolve()
    if root.exists():
        raise ValueError('Use a new workspace; this seed never replaces existing data.')
    fixtures = Path(__file__).resolve().parents[1] / 'tests/fixtures'
    Store(root).init('extractive')
    engine = Engine(root)
    profile = json.loads((fixtures / 'voice-creator.json').read_text())
    profile['platforms'].append('substack')
    profile['posting_cadence'] = {'x': 2, 'linkedin': 1, 'tiktok': 1, 'substack': 1}
    engine.onboard(profile)
    voice = root / 'data/creator/VOICE.md'
    atomic_text(voice, voice.read_text() + '\n## My editing preference\n\n'
                'Keep a dry joke only when it grows out of the actual object. '
                'Do not turn every repair into a life lesson.\n')

    history = engine.capture(fixtures / 'weekly-history.txt', kind='old posts',
                             consent='Fictional public QA history')
    # Historical posts are supplied records, one per line. They are not a test
    # of the extractive miner (which may split a line into several candidates).
    ideas = [engine.persist_idea(engine.idea_from(
        {'topic': quote.split('. ')[0], 'quote': quote, 'start_line': index,
         'end_line': index, 'category': 'fictional published history'},
        history['id'], 'scripted historical QA record'))
        for index, quote in enumerate((fixtures / 'weekly-history.txt').read_text().splitlines(), 1)]
    current = datetime.now(timezone.utc)
    posts = []
    for index, idea in enumerate(ideas):
        engine.select(idea['id'], platform='x', format_name='short post', job='Bookmarks / Saves')
        post = engine.draft(idea['id'])[0]
        engine.transition(post['id'], 'APPROVED')
        engine.transition(post['id'], 'PUBLISHED',
                          url='https://example.invalid/fictional-qa/' + post['id'],
                          published_at=(current - timedelta(days=6 - index)).isoformat())
        # The first item wins on save rate despite another having more reach.
        impressions, bookmarks = [(1000, 40), (10000, 40), (1000, 4), (1000, 4)][index]
        engine.manual_metrics(post['id'], {'impressions': impressions, 'bookmarks': bookmarks},
                              observed_at=(current - timedelta(hours=1)).isoformat())
        posts.append(post['id'])
    Feedback(engine.store).add(posts[0],
        'For future X posts, humor is optional. Do not append a standalone joke at the end.',
        'Fictional QA reviewer', 'platform', 'voice')
    source = engine.capture(fixtures / 'weekly-workshop.txt', kind='work log',
                            consent='Fictional public QA workshop notes')
    cfg = engine.store.config
    cfg.update(provider='external', article_words=[450, 650], timezone='America/New_York')
    atomic_text(root / 'config.yaml', yaml.safe_dump(cfg, sort_keys=False))
    flows = Scheduler(engine).config()
    flows['timezone'] = 'America/New_York'
    flows['counts'] = {'x': 2, 'linkedin': 1, 'tiktok': 1, 'x_article': 1,
                       'substack': 1, 'substack_note': 1}
    atomic_text(root / 'workflows.yaml', yaml.safe_dump(flows, sort_keys=False))
    install('codex', path=root)
    result = {'workspace': str(root), 'history_posts': posts, 'expected_winner': posts[0],
              'fresh_source': source['id'], 'counts': flows['counts'],
              'notice': 'All source, metrics, review direction and publication records are fictional. '
                        'No connector called. New-source mining, editorial plan and weekly writing are not seeded.'}
    atomic_json(root / 'trial-seed.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', required=True)
    print(json.dumps(seed(parser.parse_args().workspace), indent=2))
