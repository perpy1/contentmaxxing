"""Scripted responses for contract tests, not an editorial quality oracle."""
from copy import deepcopy


def plan_output(task, limits=None):
    inputs = task['inputs']
    slots = []
    for platform, count in (limits if limits is not None else inputs['active_counts']).items():
        ideas = [i for i in inputs['candidates'] if platform in i['available_platforms']]
        for idea in ideas[:count]:
            choice = idea['selected_choice']
            selected = choice and choice['platform'] == platform
            slots.append({'idea_id': idea['id'], 'platform': platform,
                'format': choice['format'] if selected else inputs['formats'][platform][0],
                'job': choice['job'] if selected else 'Reach',
                'angle': 'The working change behind: ' + idea['topic'],
                'reader_payoff': 'A concrete action to try at the next client handoff.',
                'reason': 'The source describes a specific workflow and its limits.',
                'source_reference': deepcopy(idea['source_reference']),
                'basis': 'source', 'performance_ids': [], 'experiment_id': None})
    chosen = {s['idea_id'] for s in slots}
    return {'strategy': 'Use the actual handoff evidence. These are scripted test choices.',
            'slots': slots, 'questions': [],
            'deferred': [{'idea_id': i['id'], 'reason': 'Keep for a later batch; the current batch has enough source-backed choices.'}
                         for i in inputs['candidates'] if i['id'] not in chosen]}


def draft_output(task):
    ref = task['inputs']['idea']['source_reference'][0]
    return {'body': ref['quote'], 'title': 'Working notes',
            'claims': [{'claim': ref['quote'], 'source_reference': ref}],
            'framework': 'FREDERICK' if task['inputs']['platform'] in ('x_article', 'substack') else None,
            'quality_notes': ['Fictional literal excerpt used to test workflow, not native writing quality.']}
