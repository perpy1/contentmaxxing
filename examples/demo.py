"""Offline vertical slice. All creator details and performance figures are fictional."""
import argparse
import csv
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from contentmaxxing.analytics import winners
from contentmaxxing.engine import Engine
from contentmaxxing.store import Store


def demo(workspace):
    fixtures = Path(__file__).resolve().parents[1] / 'tests/fixtures'
    Store(workspace).init(provider='extractive')
    engine = Engine(workspace)
    engine.onboard(json.loads((fixtures / 'creator.json').read_text()))
    source = engine.capture(fixtures / 'transcript.txt', consent='fictional demo; cleared')
    ideas = engine.mine(source['id'])
    posts = []
    published = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    for index, idea in enumerate(ideas):
        engine.select(idea['id'], format_name='short post', job='Bookmarks / Saves')
        post = engine.draft(idea['id'])[0]
        engine.transition(post['id'], 'APPROVED')
        engine.transition(post['id'], 'PUBLISHED', url='https://example.com/fictional-post/' + str(index), published_at=published)
        posts.append(post)
    csv_path = Path(workspace) / 'fictional-analytics.csv'
    with csv_path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['content_id', 'observed_at', 'impressions', 'bookmarks', 'profile_visits'])
        writer.writeheader()
        for index, post in enumerate(posts):
            writer.writerow({'content_id': post['id'], 'observed_at': datetime.now(timezone.utc).isoformat(),
                             'impressions': 1000, 'bookmarks': 40 if index == 0 else 4,
                             'profile_visits': 8})
    engine.import_csv(csv_path)
    report = engine.report()
    winner = winners(engine.store)[0]
    opportunities = engine.compound(winner['content_id'])
    result = {'workspace': str(Path(workspace).resolve()), 'source': source['id'],
              'ideas_mined': len(ideas), 'x_source_excerpt_drafts': len(posts),
              'analytics_imported': len(posts), 'winner': winner,
              'compound_opportunities': [{'id': i['id'], 'addition': i['addition'], 'topic': i['topic']} for i in opportunities],
              'report_id': report['id'], 'notice': 'Fictional metrics; extractive retrieval, no live model or publishing calls.'}
    (Path(workspace) / 'demo-result.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', required=True)
    print(json.dumps(demo(parser.parse_args().workspace), indent=2))
