"""Read-only navigation derived from portable records, never chat memory."""
import json
from datetime import datetime, timezone

from .analytics import latest_snapshots, timestamp, winners
from .mining import source_progress
from .compounding import needs_capture


def action(command, reason, needs_input=False, **arguments):
    return {'command': command, 'reason': reason, 'requires_user_input': needs_input,
            'arguments': arguments}


def navigation(store, state):
    if not state['initialized'] or not state.get('onboarded'):
        return {'stage': 'SETUP', 'next_action': action('start', 'Build your creator brain and first batch.', True)}
    phase = state.get('kickoff_phase')
    if phase and phase != 'REVIEW':
        return {'stage': 'SETUP', 'next_action': action('start', 'Continue saved kickoff: ' + phase,
                phase not in ('MINING', 'DRAFTING'), phase=phase)}
    plans = [json.loads(p.read_text(encoding='utf-8')) for p in (store.data / 'reports/plans').glob('plan_*.json')]
    runs = [r for r in store.list('runs') if r['status'] != 'COMPLETED']
    checkpoints = [action('create' if r.get('plan_id') else 'week', 'Resume saved work.',
                         **({'plan_id': r['plan_id']} if r.get('plan_id') else {'run_id': r['id'], 'workflow': r['workflow']})) for r in runs]
    linked = {identifier for r in runs for identifier in (r.get('plan_id'), r.get('editorial_plan_id'))}
    linked.update(p['id'] for p in plans if p.get('origin_run_id') in {r['id'] for r in runs})
    checkpoints += [action('create', 'Create drafts from the saved Topic + Format + Job plan.', plan_id=p['id'])
                    for p in plans if p.get('status') != 'COMPLETED' and p['id'] not in linked]
    if checkpoints:
        return {'stage': 'CREATE', 'checkpoints': checkpoints,
                'next_action': checkpoints[0] if len(checkpoints) == 1 else
                action('resume', 'Choose which saved batch to continue.', True)}
    tasks = [t for t in store.list('tasks') if t['status'] == 'PENDING']
    if tasks:
        task = tasks[0]
        return {'stage': {'mine': 'CAPTURE', 'plan': 'PLAN', 'compound': 'COMPOUND', 'voice': 'VOICE'}.get(task['operation'], 'CREATE'),
                'next_action': action(task['operation'] if task['operation'] in ('mine', 'plan', 'compound', 'voice') else 'review' if task['inputs'].get('revision_target') else 'draft',
                                      'Complete the saved task before starting another.', task_id=task['id'])}
    voice_proposals = [json.loads(p.read_text(encoding='utf-8')) for p in (store.data / 'creator/voice').glob('voice_*.json')]
    voice_review = [p['id'] for p in voice_proposals if p['status'] in ('PROPOSED', 'APPLYING')]
    if voice_review:
        return {'stage': 'VOICE', 'next_action': action('voice', 'Review saved voice observations and resolve any interrupted application.', True, proposal_ids=voice_review)}
    unfinished_mining = [m for m in source_progress(store) if m['status'] == 'IN_PROGRESS']
    if unfinished_mining:
        return {'stage': 'CAPTURE', 'next_action': action('mine', 'Continue the saved source windows.',
            source_ids=[m['source_id'] for m in unfinished_mining]), 'mining_progress': unfinished_mining}
    content, ideas = store.list('content'), store.list('ideas')
    reviews = [c['id'] for c in content if c['status'] == 'NEEDS_REVIEW']
    if reviews:
        return {'stage': 'REVIEW', 'next_action': action('review', 'Drafts are ready for your judgment.', True, content_ids=reviews)}
    deliveries = [c['id'] for c in content if c['status'] == 'APPROVED' or
                  (c['status'] == 'SCHEDULED' and c.get('scheduled_at') and
                   timestamp(c['scheduled_at']) <= datetime.now(timezone.utc))]
    if deliveries:
        return {'stage': 'PUBLISH', 'next_action': action('publish', 'Choose delivery or check an existing schedule; approval alone does not publish.', True, content_ids=deliveries)}
    compounded = {i.get('parent_content_id') for i in ideas}
    compounded.update(t['inputs']['parent_content']['id'] for t in store.list('tasks')
                      if t['operation'] == 'compound' and t['status'] in ('COMPLETED', 'CANCELLED'))
    measured_winners = [w['content_id'] for w in winners(store) if w['content_id'] not in compounded]
    if measured_winners:
        return {'stage': 'COMPOUND', 'next_action': action('compound', 'Measured winners have no follow-up opportunities yet.', content_ids=measured_winners)}
    measured = set(latest_snapshots(store))
    missing = [c['id'] for c in content if c['status'] in ('PUBLISHED', 'COMPOUND') and c['id'] not in measured]
    if missing:
        return {'stage': 'MEASURE', 'next_action': action('analytics', 'Published content needs real measurements.', True, content_ids=missing)}
    mined = {t['inputs']['source_id'] for t in store.list('tasks') if t['operation'] == 'mine' and t['status'] == 'COMPLETED'}
    unmined = [s['id'] for s in store.list('sources') if s['id'] not in mined]
    if unmined:
        return {'stage': 'CAPTURE', 'next_action': action('mine', 'Find topics in saved source material.', source_ids=unmined)}
    usable = [i['id'] for i in ideas if i['status'] in ('BACKLOG', 'SELECTED') and not needs_capture(i)]
    if usable:
        return {'stage': 'PLAN', 'next_action': action('plan', 'Choose the next useful topics, formats, and jobs.', idea_ids=usable)}
    blocked = [i['id'] for i in ideas if i['status'] in ('BACKLOG', 'SELECTED') and needs_capture(i)]
    if blocked:
        return {'stage': 'CAPTURE', 'next_action': action('capture', 'Capture evidence for saved follow-up questions, then resolve their development gaps.', True, idea_ids=blocked)}
    return {'stage': 'CAPTURE', 'next_action': action('capture', 'Bring fresh work, a conversation, or a useful question.', True)}
