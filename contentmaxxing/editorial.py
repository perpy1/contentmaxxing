"""Shared editorial judgment contract. Hosts choose; the engine validates/persists."""
import json
from collections import Counter
from copy import deepcopy

from jsonschema import Draft202012Validator

from .analytics import latest_snapshots, metric_status, score
from .feedback import Feedback
from .experiments import Experiments
from .providers import PendingTask
from .retrieval import bounded_integer
from .store import record


REFERENCE = {'type': 'object', 'additionalProperties': False,
    'required': ['source_id', 'quote', 'start_line', 'end_line'], 'properties': {
        'source_id': {'type': 'string'}, 'quote': {'type': 'string', 'minLength': 1},
        'start_line': {'type': 'integer', 'minimum': 1}, 'end_line': {'type': 'integer', 'minimum': 1}}}
TEXT = {'type': 'string', 'minLength': 1, 'maxLength': 1500}
PLAN_CONTRACT = {'type': 'object', 'additionalProperties': False,
    'required': ['strategy', 'slots', 'deferred', 'questions'], 'properties': {
        'strategy': TEXT, 'questions': {'type': 'array', 'items': TEXT},
        'deferred': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False,
            'required': ['idea_id', 'reason'], 'properties': {'idea_id': {'type': 'string'}, 'reason': TEXT}}},
        'slots': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False,
            'required': ['idea_id', 'platform', 'format', 'job', 'angle', 'reader_payoff', 'reason',
                         'source_reference', 'basis', 'performance_ids', 'experiment_id'],
            'properties': {'idea_id': {'type': 'string'}, 'platform': {'type': 'string'},
                'format': {'type': 'string'}, 'job': {'type': 'string'},
                'angle': TEXT, 'reader_payoff': TEXT, 'reason': TEXT,
                'source_reference': {'type': 'array', 'minItems': 1, 'items': REFERENCE},
                'basis': {'enum': ['source', 'performance', 'experiment']},
                'performance_ids': {'type': 'array', 'uniqueItems': True, 'items': {'type': 'string'}},
                'experiment_id': {'type': ['string', 'null']}}}}}}


def provider_name(engine):
    return engine.provider_name or engine.store.config['provider']


def validate_brief(store, brief, idea, platform):
    if brief is None:
        return
    if (brief.get('idea_id'), brief.get('platform'), brief.get('format'), brief.get('job')) != (
            idea['id'], platform, idea['format'], idea['primary_job']):
        raise ValueError('Editorial brief must match the selected idea, platform, format and job.')
    for ref in brief['source_reference']:
        if ref not in idea['source_reference']:
            raise ValueError('Editorial brief evidence is no longer attached to the idea.')
        store.validate_reference(ref)
    if brief.get('experiment_id'):
        store.get('experiments', brief['experiment_id'])


class Editorial:
    def __init__(self, engine):
        self.engine, self.store = engine, engine.store

    def context(self, counts, timezone, report, scope):
        config = self.store.config.get('editorial', {})
        limit = bounded_integer(config.get('candidate_limit', 48), 'editorial.candidate_limit', 1, 300)
        budget = bounded_integer(config.get('candidate_chars', 40000), 'editorial.candidate_chars', 2000, 300000)
        profile = json.loads((self.store.data / 'creator/profile.json').read_text())
        platforms = self.store.registry['platforms']
        unknown = set(counts) - set(platforms)
        if unknown:
            raise ValueError('Unknown editorial platform: ' + ', '.join(sorted(unknown)))
        active = {p: n for p, n in counts.items() if n and
                  {'x_article': 'x', 'substack_note': 'substack'}.get(p, p) in profile['platforms']}
        content = self.store.list('content')
        used = {(c['idea_id'], c['platform']) for c in content}
        pending = {(t['inputs']['idea']['id'], t['inputs']['platform']) for t in self.store.list('tasks')
                   if t['operation'] == 'draft' and not t['inputs'].get('revision_target') and t['status'] == 'PENDING'}
        ideas = sorted((i for i in self.store.list('ideas') if i['status'] != 'ARCHIVED'),
                       key=lambda i: (i['status'] != 'SELECTED', -i['priority'], i['created_at'], i['id']))
        candidates, omitted, eligible, used_chars = [], [], 0, 0
        for idea in ideas:
            available = [p for p in active if (idea['id'], p) not in used | pending and
                         (p not in ('x_article', 'substack') or idea['article_candidate'])]
            if not available:
                continue
            eligible += 1
            value = {k: idea[k] for k in ('id', 'topic', 'category', 'content_pillar', 'priority',
                'notes', 'source_reference', 'article_candidate', 'parent_content_id', 'addition')}
            value['available_platforms'] = available
            if idea.get('development'):
                value['development'] = idea['development']
            value['selected_choice'] = ({'platform': idea['best_platform'], 'format': idea['format'],
                                         'job': idea['primary_job']} if idea['status'] == 'SELECTED' else None)
            size = len(json.dumps(value, ensure_ascii=False))
            if len(candidates) == limit or used_chars + size > budget:
                if len(omitted) < 20:
                    omitted.append(idea['id'])
                continue
            for ref in idea['source_reference']:
                self.store.validate_reference(ref)
            candidates.append(value)
            used_chars += size
        recent = sorted(content, key=lambda c: (c['updated_at'], c['id']), reverse=True)[:20]
        latest = latest_snapshots(self.store, report['end_date'])
        performance = []
        for item in sorted(content, key=lambda c: c.get('published_at') or '', reverse=True):
            if item['id'] not in latest or not item['published_at']:
                continue
            measurement = latest[item['id']]
            performance.append({'content_id': item['id'], 'topic': item['topic'], 'platform': item['platform'],
                'format': item['format'], 'job': item['primary_job'], 'job_score': score(item, measurement, self.store.registry),
                'metric': self.store.registry['job_metrics'].get(item['primary_job']),
                'published_at': item['published_at'], 'observed_at': measurement['observed_at'],
                'measurement_ids': measurement['measurement_ids'], 'origins': measurement['origins'],
                'conflicts': measurement['conflicts'],
                'metric_status': metric_status(measurement, self.store.registry['job_metrics'].get(item['primary_job']))})
            if len(performance) == 30:
                break
        summary = {k: report[k] for k in ('id', 'sample_size', 'start_date', 'end_date', 'growth', 'limitations', 'editorial_brief')}
        for key in ('winning_topics', 'winning_formats', 'winning_jobs', 'combinations', 'posting_windows', 'compound'):
            summary[key] = report[key][:20]
        summary['coverage'] = 'At most 20 rows per findings table; full report remains at data/reports/' + report['id'] + '.json'
        return {'scope': scope, 'counts': dict(counts), 'active_counts': active, 'timezone': timezone,
            'creator': self.store.brain(), 'formats': {p: platforms[p] for p in active},
            'jobs': self.store.registry['jobs'], 'candidates': candidates,
            'candidate_coverage': {'eligible': eligible, 'supplied': len(candidates), 'omitted': eligible - len(candidates),
                'first_omitted_ids': omitted, 'chars': used_chars, 'max_chars': budget,
                'order': 'Explicit selection, priority, then creation time. This is a bounded pool, not proof of the best ideas in the whole library.'},
            'editorial_report': summary, 'performance': performance,
            'recent_content': [{**{k: c[k] for k in ('id', 'idea_id', 'topic', 'platform', 'format', 'primary_job', 'status')},
                                'body_excerpt': c['body'][:600], 'body_truncated': len(c['body']) > 600} for c in recent],
            'feedback': {p: Feedback(self.store).context(p) for p in active},
            **Experiments(self.store).context(report['end_date'],
                bounded_integer(config.get('experiment_chars', 16000), 'editorial.experiment_chars', 0, 200000)),
            'source_metadata': {r['source_id']: self.store.get('sources', r['source_id'])
                                for i in candidates for r in i['source_reference']}}

    def request(self, counts, timezone, report=None, scope='standalone', fresh=False):
        from .planning import Planning
        previous = [t for t in self.store.list('tasks') if t['operation'] == 'plan' and t['inputs']['scope'] == scope]
        if previous and not fresh:
            task = previous[-1]
            path = Planning(self.engine).directory / ('plan_' + task['id'][5:] + '.json')
            if path.exists():
                plan = self.complete(task, None)
                if scope != 'standalone' or plan['status'] != 'COMPLETED':
                    return plan
            if task['status'] == 'PENDING':
                raise PendingTask(task['id'])
        report = report or self.engine.report(timezone_name=timezone)
        inputs = self.context(counts, timezone, report, scope)
        task = self.engine.task('plan', 'editorial-planning', inputs, PLAN_CONTRACT)
        return self.engine.execute(task)[0]

    def validate(self, inputs, output):
        Draft202012Validator(PLAN_CONTRACT).validate(output)
        candidates = {i['id']: i for i in inputs['candidates']}
        performance = {p['content_id']: p for p in inputs['performance']}
        experiments = {e['id'] for e in inputs['experiments']}
        seen, selected, counts = set(), set(), Counter()
        for slot in output['slots']:
            idea = candidates.get(slot['idea_id'])
            if idea is None or slot['platform'] not in idea['available_platforms']:
                raise ValueError('Editorial choice was not supplied as an eligible idea/platform.')
            from .compounding import require_ready
            require_ready(idea)
            pair = (slot['idea_id'], slot['platform'])
            if pair in seen:
                raise ValueError('Editorial plan repeats an idea on the same platform.')
            seen.add(pair); selected.add(slot['idea_id']); counts[slot['platform']] += 1
            if counts[slot['platform']] > inputs['active_counts'][slot['platform']]:
                raise ValueError('Editorial plan exceeds the configured platform ceiling.')
            if slot['format'] not in inputs['formats'][slot['platform']] or slot['job'] not in inputs['jobs']:
                raise ValueError('Editorial plan has an unregistered native format or job.')
            choice = idea['selected_choice']
            if choice and choice['platform'] == slot['platform'] and (choice['format'], choice['job']) != (slot['format'], slot['job']):
                raise ValueError('Preserve the creator-selected format/job or defer the idea with a reason.')
            for ref in slot['source_reference']:
                if ref not in idea['source_reference']:
                    raise ValueError('Plan evidence must be an exact supplied reference for the selected idea.')
                self.store.validate_reference(ref)
            if slot['basis'] == 'performance':
                if not slot['performance_ids']:
                    raise ValueError('A performance-based choice needs supplied measured examples.')
                for identifier in slot['performance_ids']:
                    metric = performance.get(identifier)
                    if not metric or metric['platform'] != slot['platform'] or metric['job'] != slot['job'] or metric['job_score'] is None:
                        raise ValueError('Performance evidence must have a known metric for this platform/job.')
            elif slot['performance_ids']:
                raise ValueError('Use performance basis when citing measured examples.')
            if slot['experiment_id'] is not None and slot['experiment_id'] not in experiments:
                raise ValueError('Unknown supplied experiment.')
            if slot['basis'] == 'experiment' and slot['experiment_id'] is None:
                raise ValueError('Experiment-based choices must reference a saved experiment.')
        deferred = [d['idea_id'] for d in output['deferred']]
        if len(deferred) != len(set(deferred)) or set(deferred) != set(candidates) - selected:
            raise ValueError('Explain every supplied idea not selected exactly once; selected ideas cannot also be deferred.')

    def complete(self, task, output):
        from .planning import Planning
        planning = Planning(self.engine)
        plan_id = 'plan_' + task['id'][5:]
        path = planning.directory / (plan_id + '.json')
        if path.exists():
            plan = planning.get(plan_id)
            if plan.get('planning_task_id') != task['id']:
                raise ValueError('Plan checkpoint belongs to another editorial task.')
            planning.save(plan)  # Restore a sidecar after a partial write.
        else:
            self.validate(task['inputs'], output)
            inputs = task['inputs']
            plan = {**record('plan'), 'id': plan_id, 'status': 'PLANNED', 'timezone': inputs['timezone'],
                'counts': inputs['counts'], 'stages': [], 'run_id': None, 'planning_task_id': task['id'],
                'planning_mode': task['provider'], 'strategy': output['strategy'], 'deferred': output['deferred'],
                'questions': output['questions'], 'candidate_coverage': inputs['candidate_coverage'],
                'report_id': inputs['editorial_report']['id'],
                'origin_run_id': inputs['scope'][4:] if inputs['scope'].startswith('run:') else None}
            for platform, maximum in inputs['counts'].items():
                slots = []
                for index, choice in enumerate(output['slots']):
                    if choice['platform'] != platform:
                        continue
                    brief = {**deepcopy(choice), 'id': plan_id + ':' + str(index), 'report_id': plan['report_id']}
                    slots.append({'idea_id': choice['idea_id'], 'format': choice['format'], 'job': choice['job'],
                                  'task_id': None, 'content_id': None, 'editorial_brief': brief})
                stage = {'name': platform, 'slots': slots,
                         'shortfall': max(0, maximum - len(slots)) if platform in inputs['active_counts'] else 0}
                if platform not in inputs['active_counts']:
                    stage['skipped_reason'] = 'Platform not selected or cadence is zero'
                plan['stages'].append(stage)
            planning.save(plan)
        task.update(status='COMPLETED', result_ids=[plan_id], error=None)
        self.store.put('tasks', task)
        return plan
