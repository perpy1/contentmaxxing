"""Seed an isolated fictional long-transcript trial; no candidate answers are seeded."""
import argparse
import json
from pathlib import Path

import yaml

from contentmaxxing.engine import Engine
from contentmaxxing.installation import install
from contentmaxxing.store import Store, atomic_json, atomic_text


def seed(workspace):
    root = Path(workspace).resolve()
    if root.exists():
        raise ValueError('Use a new isolated trial folder; existing work is preserved.')
    store = Store(root)
    store.init()
    engine = Engine(root)
    engine.onboard({'name': 'Dana Demo', 'niche': 'Independent ceramics teaching studio',
        'audience': 'Small workshop teachers and studio helpers',
        'content_goals': ['Share practical working notes from teaching preparation'],
        'expertise': ['Teaching beginner hand-building practice classes'],
        'platforms': ['x', 'linkedin', 'tiktok', 'substack'],
        'desired_tone': 'Measured, practical and specific. Normal sentence case.',
        'restrictions': ['Fictional trial only. No restoration advice, identifiable attendees, invented outcomes or borrowed personal stories.'],
        'excluded_topics': ['Antique restoration and conservation advice']})
    config = store.config
    config['mining'] = {'chunk_chars': 4000, 'overlap_chars': 500, 'chunks_per_call': 1}
    atomic_text(root / 'config.yaml', yaml.safe_dump(config, sort_keys=False))
    fixture = Path(__file__).resolve().parents[1] / 'tests/fixtures/mining-workshop.txt'
    source = engine.capture(fixture, consent='fictional', notes='Fictional interview; Dana is the creator, Remy interviews, Sol is a guest. Private examples remain restricted within the story.')
    install('codex', root)
    result = {'workspace': str(root), 'source_id': source['id'], 'characters': len(store.source_text(source['id'])),
              'notice': 'Fictional source/profile. No model responses, mined topics, drafts or quality grades are seeded.'}
    atomic_json(root / 'TRIAL.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', required=True)
    print(json.dumps(seed(parser.parse_args().workspace), indent=2))
