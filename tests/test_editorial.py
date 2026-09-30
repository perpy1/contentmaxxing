import json
import shutil
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock, patch

import yaml
from jsonschema import ValidationError

from contentmaxxing.editorial import Editorial
from contentmaxxing.engine import Engine
from contentmaxxing.export import export_workspace
from contentmaxxing.feedback import Feedback
from contentmaxxing.overview import overview
from contentmaxxing.planning import Planning
from contentmaxxing.providers import PendingTask
from contentmaxxing.scheduler import Scheduler
from contentmaxxing.store import atomic_text
from editorial_helpers import draft_output, plan_output
from test_vertical import WorkspaceFixture


class EditorialTests(WorkspaceFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.host = Engine(self.temp.name, provider_name='external')
        self.planning = Planning(self.host)
        cfg = Scheduler(self.host).config()
        cfg['counts'] = {'x': 2}
        atomic_text(self.host.store.root / 'workflows.yaml', yaml.safe_dump(cfg))

    def pending(self, fresh=False):
        with self.assertRaises(PendingTask) as exc:
            self.planning.plan(fresh=fresh)
        return self.host.store.get('tasks', exc.exception.task_id)

    def complete(self, task, output=None):
        return self.host.complete_task(task['id'], output if output is not None else plan_output(task))[0]

    def finish_drafts(self):
        for task in self.host.store.list('tasks'):
            if task['operation'] == 'draft' and task['status'] == 'PENDING':
                self.complete(task, draft_output(task))

    def test_host_selects_lower_priority_and_passes_distinct_brief_to_writer(self):
        high = self.host.store.get('ideas', self.ideas[0]['id'])
        high['priority'] = 100
        self.host.store.put('ideas', high)
        task = self.pending()
        low = task['inputs']['candidates'][-1]
        output = plan_output(task, {'x': 1})
        slot = output['slots'][0]
        slot.update(idea_id=low['id'], source_reference=low['source_reference'], format='checklist',
                    job='Bookmarks / Saves', angle='The next-owner handoff check',
                    reader_payoff='A check to run before closing the next client call.')
        output['deferred'] = [{'idea_id': i['id'], 'reason': 'This batch has a more directly usable source.'}
                              for i in task['inputs']['candidates'] if i['id'] != low['id']]
        plan = self.complete(task, output)
        self.assertEqual(plan['stages'][0]['shortfall'], 1)
        self.assertIn(high['id'], [i['idea_id'] for i in plan['deferred']])
        self.planning.create(plan['id'])
        self.assertEqual(self.planning.plan()['id'], plan['id'])
        draft = next(t for t in self.host.store.list('tasks') if t['operation'] == 'draft')
        brief = draft['inputs']['editorial_brief']
        self.assertEqual(brief['angle'], slot['angle'])
        self.assertEqual(brief['reader_payoff'], slot['reader_payoff'])
        self.assertEqual(draft['inputs']['idea']['id'], low['id'])
        self.assertEqual(draft['inputs']['editorial_report']['id'], plan['report_id'])
        self.assertIn(slot['angle'], (self.planning.directory / (plan['id'] + '.md')).read_text())
        self.finish_drafts()
        self.assertEqual(self.planning.create(plan['id'])['plan']['status'], 'COMPLETED')
        self.assertEqual(self.host.store.list('content')[0]['status'], 'NEEDS_REVIEW')

    def test_context_includes_brain_feedback_recent_history_and_job_measurements(self):
        post = self.publish(self.post())
        self.engine.manual_metrics(post['id'], {'impressions': 1000, 'bookmarks': 12})
        Feedback(self.engine.store).add(post['id'], 'Make the action specific.', 'Demo reviewer', 'creator', 'voice')
        task = self.pending()
        inputs = task['inputs']
        self.assertTrue(inputs['creator'])
        self.assertTrue(inputs['feedback']['x'])
        self.assertEqual(inputs['recent_content'][0]['id'], post['id'])
        self.assertEqual(inputs['performance'][0]['job_score'], 12)
        self.assertEqual(inputs['performance'][0]['metric'], 'bookmarks_per_1k')
        self.assertIn(self.source['id'], inputs['source_metadata'])
        self.assertNotIn(post['idea_id'], [i['id'] for i in inputs['candidates']])

    def test_bounded_candidates_keep_entire_references_and_disclose_omissions(self):
        cfg_path = self.host.store.root / 'config.yaml'
        cfg = self.host.store.config
        cfg['editorial'] = {'candidate_limit': 2, 'candidate_chars': 2000}
        atomic_text(cfg_path, yaml.safe_dump(cfg))
        oversized = self.host.store.get('ideas', self.ideas[0]['id'])
        oversized.update(priority=100, notes='source detail ' * 500)
        self.host.store.put('ideas', oversized)
        task = self.pending()
        inputs = task['inputs']
        self.assertEqual(inputs['candidate_coverage']['eligible'], 6)
        self.assertEqual(inputs['candidate_coverage']['supplied'], 2)
        self.assertEqual(inputs['candidate_coverage']['omitted'], 4)
        self.assertIn(oversized['id'], inputs['candidate_coverage']['first_omitted_ids'])
        for idea in inputs['candidates']:
            self.assertEqual(idea['source_reference'], self.host.store.get('ideas', idea['id'])['source_reference'])

    def test_invalid_decisions_write_no_partial_plan(self):
        task = self.pending()
        good = plan_output(task, {'x': 1})
        cases = []
        for field, value in [('idea_id', 'idea_000000000000'), ('platform', 'unknown'),
                             ('format', 'LinkedIn post'), ('job', 'viral'), ('experiment_id', 'exp_000000000000')]:
            bad = deepcopy(good); bad['slots'][0][field] = value; cases.append(bad)
        bad = deepcopy(good); bad['slots'].append(deepcopy(bad['slots'][0])); cases.append(bad)
        bad = deepcopy(good); bad['deferred'] = []; cases.append(bad)
        bad = deepcopy(good); bad['slots'][0]['source_reference'][0]['quote'] = 'Fabricated receipt'; cases.append(bad)
        bad = deepcopy(good); bad['slots'][0]['source_reference'] = []; cases.append(bad)
        bad = deepcopy(good); bad['slots'][0]['source_reference'] = task['inputs']['candidates'][1]['source_reference']; cases.append(bad)
        cases.append(plan_output(task, {'x': 3}))
        for bad in cases:
            with self.subTest(output=bad):
                with self.assertRaises((ValueError, ValidationError)):
                    self.complete(task, bad)
                self.assertEqual(self.planning.list(), [])
                self.assertEqual(self.host.store.list('content'), [])
                self.assertEqual(self.host.store.get('tasks', task['id'])['status'], 'PENDING')
        self.complete(task, good)

    def test_creator_selection_preserved_or_explicitly_deferred(self):
        selected = self.engine.select(self.ideas[0]['id'], format_name='contrarian take', job='Conversation')
        task = self.pending()
        output = plan_output(task, {'x': 1})
        self.assertEqual(output['slots'][0]['idea_id'], selected['id'])
        output['slots'][0]['job'] = 'Reach'
        with self.assertRaisesRegex(ValueError, 'creator-selected'):
            self.complete(task, output)
        result = self.complete(task, plan_output(task, {}))
        self.assertEqual(len(result['deferred']), 6)
        self.assertEqual(result['stages'][0]['shortfall'], 2)
        self.assertEqual(self.planning.create(result['id'])['run']['status'], 'COMPLETED')
        self.assertEqual(self.host.store.list('content'), [])

    def test_performance_basis_requires_known_metric_on_same_platform_and_job(self):
        post = self.publish(self.post())
        self.engine.manual_metrics(post['id'], {'impressions': 1000, 'bookmarks': 12})
        task = self.pending()
        output = plan_output(task, {'x': 1})
        slot = output['slots'][0]
        slot.update(basis='performance', performance_ids=[post['id']])
        with self.assertRaisesRegex(ValueError, 'known metric'):
            self.complete(task, output)  # Reach is not a Saves measurement.
        slot['job'] = 'Bookmarks / Saves'
        slot['performance_ids'] = []
        with self.assertRaisesRegex(ValueError, 'measured examples'):
            self.complete(task, output)
        slot['performance_ids'] = [post['id']]
        self.complete(task, output)

    def test_trust_cannot_be_inferred_from_impressions(self):
        post = self.publish(self.post(job='Trust'))
        self.engine.manual_metrics(post['id'], {'impressions': 100000})
        task = self.pending()
        output = plan_output(task, {'x': 1})
        output['slots'][0].update(basis='performance', performance_ids=[post['id']], job='Trust')
        with self.assertRaisesRegex(ValueError, 'known metric'):
            self.complete(task, output)

    def test_experiment_choice_attaches_draft_and_resumes_idempotently(self):
        experiment = self.engine.experiment({'hypothesis': 'A checklist increases saves', 'metric': 'bookmarks_per_1k'})
        task = self.pending()
        output = plan_output(task, {'x': 1})
        output['slots'][0].update(basis='experiment', experiment_id=experiment['id'])
        plan = self.complete(task, output)
        self.planning.create(plan['id']); self.finish_drafts()
        result = self.planning.create(plan['id'])
        self.planning.create(plan['id'])
        post = self.host.store.get('content', result['plan']['content_ids'][0])
        self.assertEqual(post['experiment'], experiment['id'])
        self.assertEqual(self.host.store.get('experiments', experiment['id'])['content_ids'], [post['id']])

    def test_pending_reused_and_completed_import_is_read_only(self):
        task = self.pending()
        self.assertEqual(self.pending()['id'], task['id'])
        plan = self.complete(task)
        paths = [self.host.store.path('tasks', task['id']), self.planning.directory / (plan['id'] + '.json')]
        before = [p.read_bytes() for p in paths]
        self.assertEqual(self.complete(task, {})['id'], plan['id'])
        self.assertEqual([p.read_bytes() for p in paths], before)
        self.assertEqual(self.planning.plan()['id'], plan['id'])
        self.assertNotEqual(self.pending(fresh=True)['id'], task['id'])

    def test_recovers_plan_committed_before_task_checkpoint(self):
        task = self.pending()
        original = self.host.store.put
        def fail_checkpoint(collection, value):
            if collection == 'tasks' and value['operation'] == 'plan' and value['status'] == 'COMPLETED':
                raise OSError('Interrupted after plan commit')
            return original(collection, value)
        with patch.object(self.host.store, 'put', side_effect=fail_checkpoint):
            with self.assertRaises(OSError):
                self.complete(task)
        saved = self.planning.list()[0]
        recovered = self.planning.plan()
        self.assertEqual(recovered['id'], saved['id'])
        self.assertEqual(len(self.planning.list()), 1)
        self.assertEqual(self.host.store.get('tasks', task['id'])['status'], 'COMPLETED')

    def test_weekly_plan_resumes_original_run_without_orphan_checkpoint(self):
        scheduler = Scheduler(self.host)
        run = scheduler.run('weekly_x_batch')
        self.assertEqual(run['stages'][0]['status'], 'COMPLETED')
        self.assertEqual(self.host.store.list('content'), [])
        task = self.host.store.get('tasks', run['editorial_task_id'])
        self.assertEqual(overview(self.temp.name)['next_action']['command'], 'week')
        plan = self.complete(task)
        # Imported plan not yet adopted: navigation still offers one checkpoint.
        self.assertEqual(len(overview(self.temp.name)['checkpoints']), 1)
        resumed = self.planning.create(plan['id'])
        self.assertEqual(resumed['run']['id'], run['id'])
        self.assertEqual(len(self.host.store.list('runs')), 1)
        self.finish_drafts()
        completed = scheduler.run('weekly_x_batch', run['id'])
        self.assertEqual(completed['status'], 'COMPLETED')
        self.assertEqual(self.planning.get(plan['id'])['status'], 'COMPLETED')
        self.assertEqual(overview(self.temp.name)['next_action']['command'], 'review')
        before = len(self.host.store.list('content'))
        self.planning.create(plan['id'])
        self.assertEqual(len(self.host.store.list('content')), before)

    def test_brief_edits_rejected_after_execution_and_mismatches_preflighted(self):
        plan = self.complete(self.pending())
        slot = plan['stages'][0]['slots'][0]
        slot['job'] = 'Trust'
        self.planning.save(plan)
        with self.assertRaisesRegex(ValueError, 'brief must match'):
            self.planning.create(plan['id'])
        self.assertEqual(self.host.store.list('runs'), [])
        slot['job'] = slot['editorial_brief']['job']
        self.planning.save(plan); self.planning.create(plan['id'])
        slot['editorial_brief']['angle'] = 'A completely different promise'
        self.planning.save(plan)
        with self.assertRaisesRegex(ValueError, 'Plan changed'):
            self.planning.create(plan['id'])

    def test_export_move_pending_plan_and_brief(self):
        task = self.pending()
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / 'kit.zip'
            export_workspace(self.host.store, archive)
            destination = Path(directory) / 'restored'
            shutil.unpack_archive(str(archive), str(destination))
            host = Engine(destination, provider_name='external')
            with patch('contentmaxxing.providers.http_json', side_effect=AssertionError('No network')):
                plan = host.complete_task(task['id'], plan_output(task))[0]
                Planning(host).create(plan['id'])
            draft = next(t for t in host.store.list('tasks') if t['operation'] == 'draft')
            self.assertEqual(draft['inputs']['editorial_brief']['id'], plan['stages'][0]['slots'][0]['editorial_brief']['id'])
            self.assertEqual(host.store.source_text(self.source['id']), self.host.store.source_text(self.source['id']))

    def test_internal_provider_uses_analyze_and_failure_stays_checkpointed(self):
        provider = Mock()
        provider.analyze.side_effect = ValueError('Model unavailable')
        host = Engine(self.temp.name, provider=provider, provider_name='openai-compatible')
        scheduler = Scheduler(host)
        run = scheduler.run('weekly_x_batch')
        self.assertEqual(run['status'], 'WAITING')
        self.assertEqual(run['error'], 'Model unavailable')
        scheduler.run('weekly_x_batch', run['id'])
        provider.analyze.assert_called_once()
        provider.generate.assert_not_called()
        task = host.store.get('tasks', run['editorial_task_id'])
        # The saved task can be fulfilled by the current host without API credentials.
        host.complete_task(task['id'], plan_output(task, {}))
        self.assertEqual(scheduler.run('weekly_x_batch', run['id'])['status'], 'COMPLETED')

    def test_old_running_batch_keeps_its_existing_slots(self):
        scheduler = Scheduler(self.host)
        # Emulate an older run that already reached drafting without a plan task.
        old = Scheduler(self.engine).run('weekly_x_batch')
        old['status'] = 'WAITING'
        old.pop('editorial_planning', None)
        self.host.store.put('runs', old)
        self.assertEqual(scheduler.run('weekly_x_batch', old['id'])['status'], 'COMPLETED')
        self.assertFalse(any(t['operation'] == 'plan' for t in self.host.store.list('tasks')))

    def test_standalone_pending_plan_has_correct_navigation(self):
        task = self.pending()
        nav = overview(self.temp.name)
        self.assertEqual(nav['stage'], 'PLAN')
        self.assertEqual(nav['next_action']['command'], 'plan')
        self.assertEqual(nav['next_action']['arguments']['task_id'], task['id'])

    def test_weekly_incompatible_pending_draft_never_replaces_editorial_brief(self):
        scheduler = Scheduler(self.host)
        run = scheduler.run('weekly_x_batch')
        task = self.host.store.get('tasks', run['editorial_task_id'])
        plan = self.complete(task, plan_output(task, {'x': 1}))
        slot = plan['stages'][0]['slots'][0]
        self.host.select(slot['idea_id'], format_name=slot['format'], job=slot['job'])
        with self.assertRaises(PendingTask) as exc:
            self.host.draft(slot['idea_id'])  # A separate draft has no editorial brief.
        unrelated = self.host.store.get('tasks', exc.exception.task_id)
        waiting = scheduler.run('weekly_x_batch', run['id'])
        actual = waiting['stages'][1]['slots'][0]
        self.assertIsNone(actual['task_id'])
        self.assertIn('different editorial brief', actual['error'])
        self.assertEqual(self.host.store.list('content'), [])
        self.complete(unrelated, draft_output(unrelated))
        waiting = scheduler.run('weekly_x_batch', run['id'])
        self.assertNotEqual(waiting['stages'][1]['slots'][0]['task_id'], unrelated['id'])

    def test_completed_run_repairs_plan_checkpoint_after_interruption(self):
        scheduler = Scheduler(self.host)
        run = scheduler.run('weekly_x_batch')
        plan = self.complete(self.host.store.get('tasks', run['editorial_task_id']))
        scheduler.run('weekly_x_batch', run['id']); self.finish_drafts()
        original = Planning.save
        def fail_complete(planning, value):
            if value['status'] == 'COMPLETED':
                raise OSError('Interrupted before plan checkpoint')
            return original(planning, value)
        with patch.object(Planning, 'save', fail_complete):
            with self.assertRaises(OSError):
                scheduler.run('weekly_x_batch', run['id'])
        self.assertEqual(self.host.store.get('runs', run['id'])['status'], 'COMPLETED')
        scheduler.run('weekly_x_batch', run['id'])
        self.assertEqual(self.planning.get(plan['id'])['status'], 'COMPLETED')
        self.assertEqual(len(self.host.store.list('content')), 2)

    def test_internal_provider_returns_same_plan_contract(self):
        provider = Mock()
        provider.analyze.side_effect = lambda task: plan_output(task, {'x': 1})
        host = Engine(self.temp.name, provider=provider, provider_name='openai-compatible')
        plan = Planning(host).plan()
        self.assertEqual(len(plan['stages'][0]['slots']), 1)
        self.assertEqual(plan['planning_mode'], 'openai-compatible')
        provider.analyze.assert_called_once()
        provider.generate.assert_not_called()
