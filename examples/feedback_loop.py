"""Fictional retrieval → draft → explicit preference → next draft illustration.

No API calls or human grades. Responses and reviewer direction below are demo
fixtures, not evidence of live model performance or real creator acceptance.
"""
import argparse
import json
from pathlib import Path

import yaml

from contentmaxxing.engine import Engine
from contentmaxxing.feedback import Feedback
from contentmaxxing.mining import source_progress
from contentmaxxing.providers import PendingTask
from contentmaxxing.retrieval import SourceLibrary
from contentmaxxing.store import atomic_json, atomic_text


def pending(engine, operation):
    try:
        operation()
    except PendingTask as exc:
        return engine.store.get('tasks', exc.task_id)
    raise AssertionError('Expected external task')


def run(workspace):
    engine = Engine(workspace, provider_name='external')
    engine.store.init()
    profile = json.loads((Path(__file__).parent.parent / 'tests/fixtures/creator.json').read_text())
    engine.onboard(profile)
    config = engine.store.config
    config['retrieval']['draft_source_chars'] = 1600
    atomic_text(engine.store.root / 'config.yaml', yaml.safe_dump(config))
    quote1 = 'Morgan: Shared ownership left client questions open. I added a next owner to each handoff.'
    quote2 = 'Morgan: On Friday two named owners were out. I added a backup owner field. I have not measured turnaround time.'
    text = '\n'.join(['Fictional routine work log: archived the meeting notes and checked the design board.'] * 500 + [quote1, quote2])
    source_file = engine.store.root / 'fictional-work-log.txt'
    atomic_text(source_file, text)
    source = engine.capture(source_file, kind='work log', consent='fictional')
    hits = SourceLibrary(engine.store).search('backup owner', limit=2, max_chars=1800)
    candidates = [dict(topic=topic, category='working process', quote=quote, start_line=line, end_line=line)
                  for topic, quote, line in [('A named owner closes an ambiguous handoff', quote1, 501),
                                            ('Plan for the named owner being absent', quote2, 502)]]
    while True:
        try:
            ideas = engine.mine(source['id'])
            break
        except PendingTask as exc:
            mining = engine.store.get('tasks', exc.task_id)
            visible = [c for c in candidates if c['quote'] in mining['inputs']['text']]
            engine.complete_task(mining['id'], {'ideas': visible})
    engine.select(ideas[0]['id'], job='Bookmarks / Saves')
    first_task = pending(engine, lambda: engine.draft(ideas[0]['id']))
    first_body = 'Shared ownership left client questions open. I added a next owner to each handoff.\n\nAgree?'
    first = engine.complete_task(first_task['id'], {'body': first_body, 'title': '', 'framework': None,
        'claims': [{'claim': 'I added a next owner to each handoff.', 'source_reference': ideas[0]['source_reference'][0]}],
        'quality_notes': ['Fictional, scripted illustration; no live editorial acceptance.']})[0]
    feedback = Feedback(engine.store).add(first['id'],
        'For future X posts, remove generic agreement questions. End on the useful working detail.',
        'Fictional demo reviewer', scope='platform', category='cta', excerpt='Agree?', replacement='')
    # The correction does not become a hidden write to identity or auto-approval.
    revision = pending(engine, lambda: engine.revise(first['id'], 'Remove the generic agreement question.'))
    revised = engine.complete_task(revision['id'], {'body': first_body.replace('\n\nAgree?', ''),
        'title': '', 'framework': None, 'claims': first['claims'],
        'quality_notes': ['Removed the generic agreement question; fictional scripted revision.']})[0]
    assert revised['id'] == first['id'] and revised['revision'] == 2
    engine.select(ideas[1]['id'], job='Bookmarks / Saves')
    second_task = pending(engine, lambda: engine.draft(ideas[1]['id']))
    assert second_task['inputs']['creator_feedback'][0]['id'] == feedback['id']
    second = engine.complete_task(second_task['id'], {'body':
        'A named owner helps until that person is out.\n\nTwo were out on Friday, so I added a backup owner field.\n\nNo turnaround-time claim yet. Just a handoff that accounts for someone being away.',
        'title': '', 'framework': None,
        'claims': [{'claim': 'Two owners were out on Friday; I added a backup owner field.',
                    'source_reference': ideas[1]['source_reference'][0]}],
        'quality_notes': ['Fictional scripted response uses the scoped feedback; verify usefulness with a real creator.']})[0]
    report = {'source_characters': len(text), 'task_source_characters': second_task['inputs']['source_context']['returned_chars'],
        'search_hits': len(hits['results']), 'drafts': [first['id'], second['id']],
        'feedback_id': feedback['id'], 'next_task_received_feedback': True,
        'mining': source_progress(engine.store, source['id']), 'revision': revised['revision'],
        'revision_preserved_content_id': revised['id'] == first['id'],
        'statuses': [engine.store.get('content', p['id'])['status'] for p in [first, second]],
        'notice': 'Fictional creator, scripted external responses and simulated reviewer direction. No live model, publishing, or human quality grade.'}
    atomic_json(engine.store.root / 'feedback-demo.json', report)
    atomic_text(engine.store.root / 'DEMO.md', '# Source retrieval and creator feedback\n\n' + report['notice'] + '\n\n'
        '## First draft, before correction\n\n' + first_body + '\n\n## Simulated creator direction\n\n' + feedback['note'] +
        '\n\n## Next draft\n\n' + second['body'] + '\n\nBoth drafts remain NEEDS_REVIEW.\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.workspace), indent=2))
