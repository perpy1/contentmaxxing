"""Read-only creator progress, separate from content status mutations."""
import json
from collections import Counter

from .store import Store
from .journey import navigation
from .mining import source_progress
from .compounding import needs_capture


def overview(workspace):
    store = Store(workspace)
    if not (store.root / 'config.yaml').is_file():
        state = {'workspace': str(store.root), 'initialized': False, 'next': 'start'}
        return {**state, **navigation(store, state)}
    state_path = store.data / 'creator/kickoff.json'
    kickoff = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else None
    content = store.list('content')
    tasks = [t for t in store.list('tasks') if t['status'] == 'PENDING']
    runs = [r for r in store.list('runs') if r['status'] != 'COMPLETED']
    capture_requests = [{'idea_id': i['id'], 'topic': i['topic'],
        'gaps': [{'gap': index + 1, 'question': gap['question']} for index, gap in enumerate(i['development']['gaps']) if gap['resolution'] is None]}
        for i in store.list('ideas') if i['status'] != 'ARCHIVED' and needs_capture(i)]
    state = {'workspace': str(store.root), 'initialized': True,
            'onboarded': (store.data / 'creator/profile.json').is_file(),
            'kickoff_phase': kickoff.get('phase') if kickoff else None,
            'mining_progress': source_progress(store),
            'capture_requests': capture_requests,
            'counts': {key: len(store.list(key)) for key in ('sources', 'ideas', 'content', 'analytics')},
            'content_statuses': dict(Counter(c['status'] for c in content)),
            'review_queue': [c['id'] for c in content if c['status'] == 'NEEDS_REVIEW'],
            'pending_tasks': [{'id': t['id'], 'skill': t['skill'], 'status': t['status']} for t in tasks],
            'unfinished_runs': [{'id': r['id'], 'status': r['status']} for r in runs]}
    return {**state, **navigation(store, state)}
