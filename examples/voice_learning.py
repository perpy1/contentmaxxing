"""Fictional samples → portable voice analysis → preserved guidance → review draft."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from contentmaxxing.engine import Engine
from contentmaxxing.providers import PendingTask
from contentmaxxing.store import Store, atomic_json, atomic_text
from contentmaxxing.voice import Voice


def pending(call):
    try:
        call()
    except PendingTask as exc:
        return exc.task_id
    raise AssertionError('Expected a saved task for the current host.')


def demo(workspace):
    fixtures = Path(__file__).resolve().parents[1] / 'tests/fixtures'
    Store(workspace).init()
    engine = Engine(workspace)
    engine.onboard(json.loads((fixtures / 'creator.json').read_text()))
    voice = Voice(engine)
    creator_note = '\n## Creator correction\n\nKeep sentence case. Do not add urgency CTAs.\n'
    atomic_text(voice.document, voice.document.read_text() + creator_note)
    task_id = pending(voice.request)
    task = engine.store.get('tasks', task_id)
    sample = task['inputs']['samples'][0]
    output = {'summary': 'One fictional sample suggests action-first writing; this remains provisional.',
        'observations': [{'dimension': 'syntax', 'pattern': 'Names a concrete next action before explaining its consequence.',
            'guidance': 'Start with the actual action and attach its practical consequence. Avoid abstract openings.',
            'certainty': 'tentative', 'platform': None, 'medium': 'writing',
            'evidence': [{'sample_id': sample['id'], 'quote': sample['text']}]}],
        'unknowns': ['Humor and CTAs need more creator examples.'], 'conflicts': []}
    atomic_json(engine.store.data / 'task-results/voice.json', output)
    proposal = engine.complete_task(task_id, output)[0]
    voice.apply(proposal['id'])
    assert creator_note in voice.document.read_text()
    assert voice.request()['id'] == proposal['id']
    source = engine.capture(fixtures / 'transcript.txt', consent='Fictional fixture')
    # Literal extraction is deliberately a demo shortcut; the voice task is not extractive.
    ideas = Engine(workspace, provider_name='extractive').mine(source['id'])
    handoff = next(i for i in ideas if i['source_reference'][0]['start_line'] == 4)
    idea = engine.select(handoff['id'], format_name='short post', job='Bookmarks / Saves')
    draft_task = pending(lambda: engine.draft(idea['id']))
    saved = engine.store.get('tasks', draft_task)
    assert proposal['block'] in saved['inputs']['creator']['VOICE.md']
    ref = idea['source_reference'][0]
    draft = {'title': 'Name the next owner', 'body': 'Name the next owner before passing the work along.\n\nA handoff with no owner is just another place for a request to wait.',
             'claims': [{'claim': 'A handoff needs an owner.', 'source_reference': ref}], 'framework': None,
             'quality_notes': ['Fictional scripted example. Voice and meaning require creator review; no publication occurred.']}
    atomic_json(engine.store.data / 'task-results/draft.json', draft)
    content = engine.complete_task(draft_task, draft)[0]
    return {'workspace': str(engine.store.root), 'voice_proposal': proposal['id'], 'voice_task': task_id,
        'proposal_status': voice.get(proposal['id'])['status'], 'creator_correction_preserved': True,
        'content_id': content['id'], 'content_status': content['status'], 'body': content['body'],
        'notice': 'Fictional creator, scripted model responses; no real creator voice trial or publishing.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', required=True)
    args = parser.parse_args()
    print(json.dumps(demo(args.workspace), indent=2))
