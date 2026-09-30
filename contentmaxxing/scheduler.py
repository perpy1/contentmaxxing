"""Clock-independent recurring workflows. A cron/daemon/platform task calls run()."""
from pathlib import Path
import json
from zoneinfo import ZoneInfo
import yaml

from .engine import mutation
from .providers import PendingTask
from .store import record
from .editorial import Editorial, provider_name, validate_brief

STEPS = {'analytics', 'x', 'linkedin', 'tiktok', 'x_article', 'substack', 'substack_note', 'compound'}


class Scheduler:
    def __init__(self, engine):
        self.engine, self.store = engine, engine.store

    def save(self, run):
        self.store.put('runs', run)
        self.sync_plan(run)
        return run

    def sync_plan(self, run):
        plan_id = run.get('editorial_plan_id') or run.get('plan_id')
        if plan_id:
            from .planning import Planning, choices
            planning = Planning(self.engine)
            plan = planning.get(plan_id)
            if choices(plan['stages']) != choices(run['stages']):
                raise ValueError('Plan changed after execution began; restore its choices or create a new plan.')
            state = {'run_id': run['id'], 'status': run['status'],
                     'content_ids': [s['content_id'] for stage in run['stages'] for s in stage['slots'] if s.get('content_id')]}
            if any(plan.get(k) != v for k, v in state.items()):
                plan.update(state)
                planning.save(plan)

    def matches(self, task, slot, platform):
        inputs = task['inputs']
        return (task['operation'] == 'draft' and not inputs.get('revision_target') and
                inputs['idea']['id'] == slot['idea_id'] and inputs['platform'] == platform and
                inputs['idea']['format'] == slot['format'] and inputs['idea']['primary_job'] == slot['job'] and
                inputs.get('editorial_brief') == slot.get('editorial_brief'))

    def config(self):
        value = yaml.safe_load((self.store.root / 'workflows.yaml').read_text())
        ZoneInfo(value['timezone'])
        for name, flow in value['workflows'].items():
            if not flow.get('steps') or set(flow['steps']) - STEPS:
                raise ValueError('Invalid workflow steps: ' + name)
            if len(flow['steps']) != len(set(flow['steps'])):
                raise ValueError('A workflow cannot repeat stages.')
            if flow['steps'][0] != 'analytics':
                raise ValueError('Analytics must precede editorial/compound stages.')
            if len(flow['cadence'].split()) != 5:
                raise ValueError('Cadence must have five cron fields.')
        for count in value['counts'].values():
            if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                raise ValueError('Batch counts must be nonnegative integers.')
        return value

    @mutation
    def run(self, workflow='weekly-editorial', run_id=None):
        self.store.brain()
        config = self.config()
        if workflow not in config['workflows'] and not (workflow == 'planned-week' and run_id):
            raise ValueError('Unknown workflow: ' + workflow)
        if run_id:
            run = self.store.get('runs', run_id)
            if run['workflow'] != workflow:
                raise ValueError('Run ID belongs to a different workflow.')
            self.sync_plan(run)
            if run['status'] == 'COMPLETED':
                return run
        else:
            run = {**record('run'), 'workflow': workflow, 'status': 'RUNNING',
                   'timezone': config['timezone'], 'cadence': config['workflows'][workflow]['cadence'],
                   'stages': [{'name': name, 'status': 'PLANNED', 'slots': [], 'results': [], 'shortfall': 0}
                              for name in config['workflows'][workflow]['steps']], 'report_id': None,
                   'counts': dict(config['counts']),
                   'editorial_planning': provider_name(self.engine) != 'extractive'}
            self.save(run)
        run['status'] = 'RUNNING'
        for stage in run['stages']:
            if stage['status'] == 'COMPLETED':
                continue
            if stage['name'] == 'analytics':
                report = self.engine.report(timezone_name=run['timezone'])
                stage['results'] = [report['id']]
                run['report_id'] = report['id']
                stage['status'] = 'COMPLETED'
                self.save(run)
                continue
            report = self.store.get('reports', run['report_id'])
            if stage['name'] == 'compound':
                waiting = False
                for content_id in report['compound']:
                    tasks = [t for t in self.store.list('tasks') if t['operation'] == 'compound' and
                             t['inputs']['parent_content']['id'] == content_id]
                    task_id = stage.get('tasks', {}).get(content_id)
                    prior = self.store.get('tasks', task_id) if task_id else (tasks[-1] if tasks else None)
                    if prior and prior['status'] == 'CANCELLED':
                        stage.setdefault('skipped', {})[content_id] = prior['cancellation_reason']
                        stage.setdefault('errors', {}).pop(content_id, None)
                        stage['results'].extend(prior['result_ids'])
                        continue
                    try:
                        stage['results'].extend(i['id'] for i in self.engine.compound(content_id, as_of=report['end_date']))
                        stage.setdefault('errors', {}).pop(content_id, None)
                    except PendingTask as exc:
                        stage.setdefault('tasks', {})[content_id] = exc.task_id
                        waiting = True
                    except Exception as exc:
                        stage.setdefault('errors', {})[content_id] = str(exc)
                        tasks = [t for t in self.store.list('tasks') if t['operation'] == 'compound' and
                                 t['inputs']['parent_content']['id'] == content_id and t['status'] == 'PENDING']
                        if tasks:
                            stage.setdefault('tasks', {})[content_id] = tasks[-1]['id']
                        waiting = True
                stage['results'] = list(dict.fromkeys(stage['results']))
                stage['status'] = 'WAITING' if waiting else 'COMPLETED'
                if waiting:
                    run['status'] = 'WAITING'
                    return self.save(run)
                self.save(run)
                continue
            if (not run.get('plan_id') and not run.get('editorial_plan_id') and
                    run.get('editorial_planning')):
                # One editorial decision covers all requested native batches.
                requested = {s['name']: run['counts'].get(s['name'], 0) for s in run['stages']
                             if s['name'] not in ('analytics', 'compound')}
                try:
                    plan = Editorial(self.engine).request(requested, run['timezone'], report,
                                                          scope='run:' + run['id'])
                except PendingTask as exc:
                    run.update(status='WAITING', editorial_task_id=exc.task_id)
                    return self.save(run)
                except Exception as exc:
                    tasks = [t for t in self.store.list('tasks') if t['operation'] == 'plan' and
                             t['inputs']['scope'] == 'run:' + run['id']]
                    if not tasks:
                        raise
                    run.update(status='WAITING', editorial_task_id=tasks[-1]['id'], error=str(exc))
                    return self.save(run)
                # Check every brief before admitting the plan into this run.
                for planned in plan['stages']:
                    for slot in planned['slots']:
                        idea = self.store.get('ideas', slot['idea_id'])
                        idea.update(format=slot['format'], primary_job=slot['job'])
                        validate_brief(self.store, slot.get('editorial_brief'), idea, planned['name'])
                run['editorial_plan_id'] = plan['id']
                run.pop('error', None)
                for planned in plan['stages']:
                    target = next(s for s in run['stages'] if s['name'] == planned['name'])
                    target.update(planned)
                    target['status'] = 'READY'
                self.save(run)
            if stage['status'] == 'PLANNED':
                self.plan_stage(stage, run)
                stage['status'] = 'RUNNING'
                self.save(run)
            waiting = False
            for slot in stage['slots']:
                if slot.get('content_id'):
                    continue
                # Recover a task created before a process interruption saved the slot.
                tasks = [t for t in self.store.list('tasks') if self.matches(t, slot, stage['name'])]
                task = self.store.get('tasks', slot['task_id']) if slot.get('task_id') else (tasks[-1] if tasks else None)
                if task and not self.matches(task, slot, stage['name']):
                    raise ValueError('Saved draft task does not match this editorial slot.')
                if task:
                    slot.pop('error', None)
                if task and task['status'] == 'COMPLETED':
                    slot['task_id'] = task['id']
                    slot['content_id'] = task['result_ids'][0]
                    self.save(run)
                    continue
                if task:
                    slot['task_id'] = task['id']
                    waiting = True
                    self.save(run)
                    continue
                self.engine.select(slot['idea_id'], platform=stage['name'], format_name=slot['format'], job=slot['job'])
                try:
                    content = self.engine.draft(slot['idea_id'], stage['name'], editorial_report=report,
                                                editorial_brief=slot.get('editorial_brief'))[0]
                    slot['content_id'] = content['id']
                    slot.pop('error', None)
                except PendingTask as exc:
                    slot['task_id'] = exc.task_id
                    slot.pop('error', None)
                    waiting = True
                except Exception as exc:
                    slot['error'] = str(exc)
                    # Any saved provider task can be completed by an external agent, even after model failure.
                    tasks = [t for t in self.store.list('tasks') if self.matches(t, slot, stage['name'])]
                    if tasks:
                        slot['task_id'] = tasks[-1]['id']
                    waiting = True
                self.save(run)
            stage['results'] = [slot['content_id'] for slot in stage['slots'] if slot.get('content_id')]
            stage['status'] = 'WAITING' if waiting else 'COMPLETED'
            self.save(run)
            if waiting:
                run['status'] = 'WAITING'
                return self.save(run)
        run['status'] = 'COMPLETED'
        return self.save(run)

    def plan_stage(self, stage, run):
        from .compounding import needs_capture
        platform = stage['name']
        count = run['counts'].get(platform, 0)
        profile = json.loads((self.store.data / 'creator/profile.json').read_text())
        creator_platform = {'x_article': 'x', 'substack_note': 'substack'}.get(platform, platform)
        if creator_platform not in profile['platforms']:
            stage['shortfall'] = 0
            stage['skipped_reason'] = 'Platform not selected by creator'
            return
        used = {c['idea_id'] for c in self.store.list('content') if c['platform'] == platform}
        pending = {t['inputs']['idea']['id'] for t in self.store.list('tasks') if t['operation'] == 'draft' and not t['inputs'].get('revision_target') and
                   t['status'] == 'PENDING' and t['inputs']['platform'] == platform}
        candidates = [i for i in self.store.list('ideas') if i['status'] != 'ARCHIVED' and i['id'] not in used | pending and not needs_capture(i)]
        if platform in ('x_article', 'substack'):
            candidates = [i for i in candidates if i['article_candidate']]
        candidates.sort(key=lambda idea: (idea['status'] != 'SELECTED', -idea['priority'], idea['created_at']))
        for index, idea in enumerate(candidates[:count]):
            if idea['status'] == 'SELECTED' and idea['best_platform'] == platform:
                job, format_name = idea['primary_job'], idea['format']
            elif platform == 'x':
                # Mix by intent; only choose containers that text evidence can actually support.
                job, format_name = [('Reach', 'short post'), ('Bookmarks / Saves', 'bookmark list'),
                                    ('Trust', 'operator story')][index % 3]
            else:
                format_name = self.store.registry['platforms'][platform][0]
                job = {'linkedin': 'Authority', 'tiktok': 'Reach', 'x_article': 'Authority',
                       'substack': 'Trust', 'substack_note': 'Conversation'}[platform]
            stage['slots'].append({'idea_id': idea['id'], 'format': format_name, 'job': job,
                                   'task_id': None, 'content_id': None})
        stage['shortfall'] = max(0, count - len(stage['slots']))
