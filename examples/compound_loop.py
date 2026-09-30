"""Fictional winner → useful follow-ups → capture a gap → native review draft."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from contentmaxxing.engine import Engine
from contentmaxxing.compounding import needs_capture
from contentmaxxing.providers import PendingTask
from contentmaxxing.store import Store, atomic_json


def pending(call):
    try:
        call()
    except PendingTask as exc:
        return exc.task_id
    raise AssertionError('Expected the current host to supply a response.')


def demo(workspace):
    root = Path(workspace)
    fixtures = Path(__file__).resolve().parents[1] / 'tests/fixtures'
    Store(root).init('extractive')
    engine = Engine(root)
    engine.onboard(json.loads((fixtures / 'creator.json').read_text()))
    source = engine.capture(fixtures / 'transcript.txt', consent='Fictional demo')
    ideas = engine.mine(source['id'])
    published = []
    for index, idea in enumerate(ideas[:5]):
        engine.select(idea['id'], format_name='short post', job='Bookmarks / Saves')
        post = engine.draft(idea['id'])[0]
        engine.transition(post['id'], 'APPROVED')
        engine.transition(post['id'], 'PUBLISHED', url='https://example.com/fictional/' + str(index))
        engine.manual_metrics(post['id'], {'impressions': 1000, 'bookmarks': 40 if index == 0 else 4})
        published.append(post)
    host = Engine(root, provider_name='external')
    task_id = pending(lambda: host.compound(published[0]['id']))
    task = host.store.get('tasks', task_id)
    ref = {'source_id': source['id'], 'start_line': 2, 'end_line': 2,
           'quote': host.store.source_text(source['id']).splitlines()[1]}
    output = {'assessment': 'This post earned 40 saves per 1,000 impressions against a matched median of 4. The source suggests practical decision context is worth developing; that is a hypothesis, not the measured cause.',
        'opportunities': [
            {'topic': 'A two-field note for preserving decision context', 'addition': 'utility',
             'new_value': 'A reusable question/decision pair, with an example of how the fields relate.',
             'rationale': 'The source documents this habit and supports a practical teaching piece.',
             'platform': 'x', 'format': 'checklist', 'job': 'Bookmarks / Saves',
             'source_reference': [ref], 'evidence_gaps': []},
            {'topic': 'What changed in a decision after a difficult client question', 'addition': 'story',
             'new_value': 'Walk through one actual question, the decision it changed, and the reason.',
             'rationale': 'A native story could make the habit concrete, but the source does not supply an episode.',
             'platform': 'tiktok', 'format': 'TikTok story', 'job': 'Trust',
             'source_reference': [ref], 'evidence_gaps': ['Capture a real question and the decision it changed.']} ]}
    atomic_json(root / 'data/task-results/compound.json', output)
    followups = host.complete_task(task_id, output)
    story = followups[1]
    assert needs_capture(story)
    host.select(story['id'], 'tiktok', story['format'], story['primary_job'])
    blocked = False
    try:
        host.draft(story['id'])
    except ValueError as exc:
        assert 'needs captured evidence' in str(exc)
        blocked = True
    assert blocked
    # This is a disclosed fictional creator answer, not generated evidence in a real workspace.
    answer = root / 'fictional-creator-answer.txt'
    answer.write_text('Morgan: A client asked who would answer handoff questions while I was away. I changed the handoff log to name a backup owner. I have not measured the effect.\n')
    captured = host.capture(answer, consent='Scripted fictional answer for this demonstration only')
    proof = {'source_id': captured['id'], 'start_line': 1, 'end_line': 1, 'quote': answer.read_text().strip()}
    resolution = {'resolutions': [{'gap': 1, 'note': 'The fictional creator supplied the question, decision and measurement limit.', 'source_reference': [proof]}]}
    atomic_json(root / 'data/task-results/resolution.json', resolution)
    ready = host.resolve_idea(story['id'], resolution)
    assert not needs_capture(ready)
    draft_id = pending(lambda: host.draft(story['id']))
    response = {'title': 'The question that added a backup owner', 'framework': None,
        'body': 'Facecam: “A client asked who would answer handoff questions while I was away. Fair question. My log had an owner. It did not have a backup.”\n\nCut to a fictional log: add a Backup owner field.\n\nFacecam: “That question changed the log. I have not measured the effect yet. This is the decision, and that is the question behind it.”',
        'claims': [{'claim': 'The client question led to a backup-owner field; the outcome is unmeasured.', 'source_reference': proof}],
        'quality_notes': ['Scripted fictional creator and response. Use a clearly fictional/redacted log; review voice and interpretation.']}
    atomic_json(root / 'data/task-results/story.json', response)
    post = host.complete_task(draft_id, response)[0]
    repeated = host.compound(published[0]['id'])
    assert [i['id'] for i in repeated] == [i['id'] for i in followups]
    result = {'winner_id': published[0]['id'], 'compound_task_id': task_id,
        'follow_ups': [{'id': i['id'], 'topic': i['topic'], 'platform': i['best_platform']} for i in followups],
        'missing_evidence_blocked_draft': blocked, 'resolved_same_idea': ready['id'] == story['id'],
        'native_draft': post['id'], 'draft_status': post['status'], 'duplicate_follow_ups': 0,
        'notice': 'All creators, source answers, analytics, publications and model responses are fictional scripted fixtures. No live publishing, model API call or human quality grade.'}
    atomic_json(root / 'compound-demo-result.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', required=True)
    print(json.dumps(demo(parser.parse_args().workspace), indent=2))
