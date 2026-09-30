"""Inspectable editorial plans executed by the shared, resumable scheduler."""
import json
import re

from .engine import mutation
from .scheduler import Scheduler
from .store import atomic_json, atomic_text, now, record
from .editorial import Editorial, provider_name, validate_brief


def choices(stages):
    return [(s['name'], [(v['idea_id'], v['format'], v['job'], v.get('editorial_brief')) for v in s['slots']])
            for s in stages if s['name'] not in ('analytics', 'compound')]


class Planning:
    def __init__(self, engine):
        self.engine, self.store = engine, engine.store
        self.directory = self.store.data / 'reports/plans'

    def list(self):
        return sorted((json.loads(p.read_text(encoding='utf-8')) for p in self.directory.glob('plan_*.json')),
                      key=lambda p: (p['created_at'], p['id']))

    def get(self, plan_id):
        if not re.fullmatch(r'plan_[a-f0-9]{12}', plan_id):
            raise ValueError('Invalid plan ID.')
        return json.loads((self.directory / (plan_id + '.json')).read_text(encoding='utf-8'))

    def save(self, plan):
        plan['updated_at'] = now()
        atomic_json(self.directory / (plan['id'] + '.json'), plan)
        lines = ['# Weekly content plan', '', 'Status: ' + plan.get('status', 'PLANNED'), '',
                 '| Idea | Platform | Format | Job |', '| --- | --- | --- | --- |']
        for stage in plan['stages']:
            for slot in stage['slots']:
                lines.append('| %s | %s | %s | %s |' % (slot['idea_id'], stage['name'], slot['format'], slot['job']))
        if plan.get('strategy'):
            lines += ['', '## Editorial strategy', '', plan['strategy']]
        for stage in plan['stages']:
            for slot in stage['slots']:
                brief = slot.get('editorial_brief')
                if brief:
                    lines += ['', '## ' + stage['name'] + ': ' + brief['angle'], '',
                              'Reader payoff: ' + brief['reader_payoff'], '',
                              'Why this choice: ' + brief['reason'], '',
                              'Basis: ' + brief['basis']]
        if plan.get('deferred'):
            lines += ['', '## Deferred ideas', ''] + ['- ' + d['idea_id'] + ': ' + d['reason'] for d in plan['deferred']]
        if plan.get('questions'):
            lines += ['', '## Open questions', ''] + ['- ' + q for q in plan['questions']]
        if plan.get('candidate_coverage'):
            lines += ['', 'Candidate coverage: ' + json.dumps(plan['candidate_coverage'])]
        lines += ['', 'Source shortfalls: ' + ', '.join('%s: %s' % (s['name'], s['shortfall']) for s in plan['stages'])]
        if plan.get('run_id'):
            lines += ['', 'Execution checkpoint: `data/runs/' + plan['run_id'] + '.json`']
        atomic_text(self.directory / (plan['id'] + '.md'), '\n'.join(lines) + '\n')
        return plan

    @mutation
    def plan(self, fresh=False):
        self.store.brain()
        scheduler = Scheduler(self.engine)
        cfg = scheduler.config()
        if provider_name(self.engine) != 'extractive':
            return Editorial(self.engine).request(cfg['counts'], cfg['timezone'], fresh=fresh)
        plan = {**record('plan'), 'status': 'PLANNED', 'timezone': cfg['timezone'],
                'counts': cfg['counts'], 'stages': [], 'run_id': None,
                'planning_mode': 'extractive heuristic; priority and default mix, not editorial judgment'}
        for platform in cfg['counts']:
            stage = {'name': platform, 'slots': [], 'shortfall': 0}
            scheduler.plan_stage(stage, plan)
            plan['stages'].append(stage)
        return self.save(plan)

    @mutation
    def create(self, plan_id=None):
        if plan_id is None:
            plans = [p for p in self.list() if p.get('status') != 'COMPLETED']
            if len(plans) != 1:
                raise ValueError('Choose a saved plan with --plan <id>; found %s unfinished plans.' % len(plans))
            plan_id = plans[0]['id']
        plan = self.get(plan_id)
        if plan.get('origin_run_id'):
            # A weekly plan belongs to its original run, including the interval
            # between importing its result and the scheduler adopting its slots.
            run = self.store.get('runs', plan['origin_run_id'])
            task = self.store.get('tasks', plan['planning_task_id'])
            if task['inputs']['scope'] != 'run:' + run['id']:
                raise ValueError('Editorial plan belongs to another workflow.')
            if run.get('editorial_plan_id'):
                if run['editorial_plan_id'] != plan_id or choices(plan['stages']) != choices(run['stages']):
                    raise ValueError('Plan changed after execution began; restore its choices or create a new plan.')
            run = Scheduler(self.engine).run(run['workflow'], run['id'])
            return {'plan': self.get(plan_id), 'run': run}
        # Deterministic mapping recovers a run saved before its plan was checkpointed.
        run_id = 'run_' + plan_id[5:]
        run_path = self.store.data / 'runs' / (run_id + '.json')
        if run_path.exists():
            run = self.store.get('runs', run_id)
            if run.get('plan_id') != plan_id:
                raise ValueError('Plan execution checkpoint belongs to another plan.')
            if choices(plan['stages']) != choices(run['stages']):
                raise ValueError('Plan changed after execution began; restore its choices or create a new plan.')
        else:
            self.store.brain()
            seen = set()
            for stage in plan['stages']:
                platform = stage['name']
                if platform not in self.store.registry['platforms']:
                    raise ValueError('Unsupported plan platform: ' + platform)
                for slot in stage['slots']:
                    key = (platform, slot['idea_id'])
                    if key in seen:
                        raise ValueError('A plan cannot repeat an idea on the same platform.')
                    seen.add(key)
                    idea = self.store.get('ideas', slot['idea_id'])
                    if idea['status'] == 'ARCHIVED':
                        raise ValueError('Plan contains an archived idea; revise the plan first.')
                    if slot['format'] not in self.store.registry['platforms'][platform] or slot['job'] not in self.store.registry['jobs']:
                        raise ValueError('Plan contains an invalid format or job.')
                    validate_brief(self.store, slot.get('editorial_brief'),
                                   {**idea, 'format': slot['format'], 'primary_job': slot['job']}, platform)
                    # An incompatible pending draft must not silently replace this plan's choices.
                    for task in self.store.list('tasks'):
                        if task['operation'] == 'draft' and not task['inputs'].get('revision_target') and task['status'] == 'PENDING' and task['inputs']['platform'] == platform and task['inputs']['idea']['id'] == idea['id']:
                            saved = task['inputs']['idea']
                            if saved['format'] != slot['format'] or saved['primary_job'] != slot['job']:
                                raise ValueError('Finish the existing draft task before creating this changed plan.')
                            if slot.get('editorial_brief') is not None and task['inputs'].get('editorial_brief') != slot['editorial_brief']:
                                raise ValueError('Finish the pending draft with its different editorial brief first.')
            run = {**record('run'), 'id': run_id, 'plan_id': plan_id, 'workflow': 'planned-week',
                   'status': 'RUNNING', 'timezone': plan['timezone'], 'cadence': None,
                   'counts': plan.get('counts', {}), 'report_id': plan.get('report_id'),
                   'stages': [{'name': 'analytics', 'status': 'COMPLETED' if plan.get('report_id') else 'PLANNED',
                               'slots': [], 'results': [plan['report_id']] if plan.get('report_id') else [], 'shortfall': 0}] +
                             [{**s, 'status': 'READY', 'results': []} for s in plan['stages']]}
            self.store.put('runs', run)
        plan['run_id'] = run_id
        plan['status'] = run['status']
        self.save(plan)
        run = Scheduler(self.engine).run('planned-week', run_id)
        plan['status'] = run['status']
        plan['content_ids'] = [slot['content_id'] for stage in run['stages'] for slot in stage['slots'] if slot.get('content_id')]
        self.save(plan)
        return {'plan': plan, 'run': run}
