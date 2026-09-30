import csv
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path

import yaml

from contentmaxxing.analytics import normalize_metrics, winners
from contentmaxxing.cli import main
from contentmaxxing.engine import Engine
from contentmaxxing.export import export_workspace
from contentmaxxing.providers import PendingTask
from contentmaxxing.scheduler import Scheduler
from contentmaxxing.store import Store, atomic_text
from test_vertical import WorkspaceFixture
from editorial_helpers import plan_output


class WorkflowTests(WorkspaceFixture, unittest.TestCase):
    def test_weekly_sequence_wait_resume_and_native_task_context(self):
        engine = Engine(self.temp.name, provider_name='external')
        cfg_path = engine.store.root / 'workflows.yaml'
        cfg = yaml.safe_load(cfg_path.read_text())
        cfg['counts'] = {'x': 3, 'linkedin': 1, 'tiktok': 1, 'x_article': 1, 'substack': 1, 'substack_note': 1}
        cfg['timezone'] = 'America/New_York'
        atomic_text(cfg_path, yaml.safe_dump(cfg))
        first_idea = engine.store.get('ideas', self.ideas[0]['id'])
        first_idea['article_candidate'] = True
        with engine.store.lock():
            engine.store.put('ideas', first_idea)
        scheduler = Scheduler(engine)
        run = scheduler.run()
        self.assertEqual(run['status'], 'WAITING')
        self.assertEqual(run['stages'][0]['status'], 'COMPLETED')
        self.assertEqual(run['stages'][1]['status'], 'PLANNED')
        self.assertEqual(engine.store.get('tasks', run['editorial_task_id'])['operation'], 'plan')
        self.assertEqual(run['stages'][2]['status'], 'PLANNED')
        self.assertEqual(engine.store.get('reports', run['report_id'])['timezone'], 'America/New_York')
        task_count = len(engine.store.list('tasks'))
        again = scheduler.run(run_id=run['id'])
        self.assertEqual(len(engine.store.list('tasks')), task_count)
        for attempt in range(10):
            for task in engine.store.list('tasks'):
                if task['status'] != 'PENDING':
                    continue
                self.assertIsNotNone(task['inputs']['editorial_report'])
                if task['operation'] == 'plan':
                    engine.complete_task(task['id'], plan_output(task))
                    continue
                self.assertIsNotNone(task['inputs']['editorial_brief'])
                platform = task['inputs']['platform']
                ref = task['inputs']['idea']['source_reference'][0]
                output = {'body': 'For ' + platform + ': ' + ref['quote'], 'title': 'Working notes',
                          'claims': [{'claim': ref['quote'], 'source_reference': ref}], 'quality_notes': [],
                          'framework': 'FREDERICK' if platform in ('x_article', 'substack') else None}
                engine.complete_task(task['id'], output)
            run = scheduler.run(run_id=run['id'])
            if run['status'] == 'COMPLETED':
                break
        self.assertEqual(run['status'], 'COMPLETED')
        self.assertEqual([s['name'] for s in run['stages']],
                         ['analytics', 'x', 'linkedin', 'tiktok', 'x_article', 'substack', 'substack_note', 'compound'])
        self.assertEqual(len(engine.store.list('content')), 8)
        self.assertTrue(all(c['status'] == 'NEEDS_REVIEW' for c in engine.store.list('content')))
        scheduler.run(run_id=run['id'])
        self.assertEqual(len(engine.store.list('content')), 8)

    def test_weekly_shortfall_and_validation(self):
        run = Scheduler(self.engine).run('weekly_x_batch')
        self.assertEqual(run['status'], 'COMPLETED')
        self.assertEqual(run['stages'][1]['shortfall'], 15)
        config_path = self.engine.store.root / 'workflows.yaml'
        cfg = yaml.safe_load(config_path.read_text())
        cfg['workflows']['bad'] = {'cadence': '* * * * *', 'steps': ['x', 'analytics']}
        atomic_text(config_path, yaml.safe_dump(cfg))
        with self.assertRaises(ValueError):
            Scheduler(self.engine).config()

    def test_export_and_move_retains_brain_sources_ids_and_intelligence(self):
        post = self.post()
        with tempfile.TemporaryDirectory() as destination:
            archive = Path(destination) / 'workspace.zip'
            result = export_workspace(self.engine.store, archive)
            self.assertEqual(result['records'], 7)
            restored = Path(destination) / 'restored'
            shutil.unpack_archive(str(archive), str(restored))
            engine = Engine(restored)
            self.assertEqual(engine.store.get('content', post['id'])['body'], post['body'])
            self.assertEqual(engine.store.source_text(self.source['id']), self.engine.store.source_text(self.source['id']))
            self.assertEqual(engine.store.brain(), self.engine.store.brain())
            self.assertTrue((restored / '.contentmaxxing/skills/compound/SKILL.md').exists())
            self.assertTrue((restored / '.contentmaxxing/templates/article-frameworks.md').exists())
        with self.assertRaises(ValueError):
            export_workspace(self.engine.store, self.engine.store.root / 'recursive.zip')

    def test_csv_preflight_nulls_idempotence_and_unknown_columns(self):
        post = self.publish(self.post())
        path = self.engine.store.root / 'input.csv'
        observed = datetime.now(timezone.utc).isoformat()
        path.write_text('content_id,observed_at,impressions,bookmarks\n' + post['id'] + ',' + observed + ',1000,10\n')
        self.engine.import_csv(path)
        self.engine.import_csv(path)
        self.assertEqual(len(self.engine.store.list('analytics')), 1)
        metric = self.engine.store.list('analytics')[0]
        self.assertIsNone(metric['metrics']['new_followers'])
        path.write_text('content_id,observed_at,impressions,bookmarks\n' + post['id'] + ',' + observed + ',1000,10\n' + post['id'] + ',' + observed + ',NaN,4\n')
        with self.assertRaisesRegex(ValueError, 'row 3'):
            self.engine.import_csv(path)
        self.assertEqual(len(self.engine.store.list('analytics')), 1)
        path.write_text('content_id,observed_at,viral_magic\n')
        with self.assertRaisesRegex(ValueError, 'Unknown CSV columns'):
            self.engine.import_csv(path)

    def test_external_native_draft_and_claim_validation(self):
        engine = Engine(self.temp.name, provider_name='external')
        idea = self.ideas[0]
        engine.select(idea['id'], job='Conversation')
        with self.assertRaises(PendingTask) as exc:
            engine.draft(idea['id'])
        task_id = exc.exception.task_id
        ref = idea['source_reference'][0]
        output = {'body': 'The question you forgot to save is probably tomorrow’s best working note.',
                  'title': '', 'claims': [{'claim': 'Questions were lost across folders', 'source_reference': dict(ref)}],
                  'quality_notes': ['Interpretation of source; creator should review.'], 'framework': None}
        output['claims'][0]['source_reference']['quote'] = 'Invented claim'
        with self.assertRaises(ValueError):
            engine.complete_task(task_id, output)
        self.assertEqual(engine.store.list('content'), [])
        output['claims'][0]['source_reference'] = ref
        item = engine.complete_task(task_id, output)[0]
        self.assertEqual(item['status'], 'NEEDS_REVIEW')
        self.assertEqual(item['generation_mode'], 'external')
        self.assertIn('creator', engine.store.get('tasks', task_id)['inputs'])

    def test_experiment_roundtrip_and_update(self):
        post = self.post()
        exp = self.engine.experiment({'hypothesis': 'Working-note utility improves saves',
                                      'metric': 'bookmarks_per_1k', 'content_ids': [post['id']]})
        self.assertEqual(self.engine.store.get('content', post['id'])['experiment'], exp['id'])
        updated = self.engine.experiment({'id': exp['id'], 'learning': 'Sample still too small', 'next_action': 'Collect another week'})
        self.assertEqual(updated['created_at'], exp['created_at'])
        self.assertEqual(updated['content_ids'], [post['id']])
        self.assertIn('Sample still too small', (self.engine.store.data / 'creator/LEARNINGS.md').read_text())

    def test_no_artificial_mining_cap(self):
        path = self.engine.store.root / 'long-call.txt'
        path.write_text('\n'.join('Operator: Topic %03d contains a distinct concrete question about case number %03d.' % (i, i) for i in range(150)))
        source = self.engine.capture(path)
        result = self.engine.mine(source['id'])
        self.assertEqual(len(result), 150)

    def test_cli_error_exit_and_external_task_reporting(self):
        output, error = StringIO(), StringIO()
        with redirect_stdout(output), redirect_stderr(error):
            code = main(['--workspace', self.temp.name, 'status', 'invalid-id', 'PUBLISHED'])
        self.assertEqual(code, 1)
        self.assertIn('Invalid record ID', error.getvalue())
        with redirect_stdout(output):
            code = main(['--workspace', self.temp.name, '--provider', 'external', 'mine', self.source['id']])
        self.assertEqual(code, 0)
        self.assertIn('PENDING', output.getvalue())

    def test_lock_rejects_second_writer(self):
        other = Store(self.temp.name)
        with self.engine.store.lock():
            with self.assertRaisesRegex(ValueError, 'Workspace busy'):
                with other.lock():
                    pass
        self.assertFalse((self.engine.store.root / '.writer.lock').exists())

    def test_compound_draft_cannot_repeat_parent(self):
        ids = []
        for index in range(5):
            post = self.publish(self.post(index))
            ids.append(post['id'])
            self.engine.manual_metrics(post['id'], {'impressions': 1000, 'bookmarks': 40 if index == 0 else 4})
        opportunity = self.engine.compound(ids[0])[0]
        parent = self.engine.store.get('content', ids[0])
        engine = Engine(self.temp.name, provider_name='external')
        engine.select(opportunity['id'], format_name='checklist', job='Bookmarks / Saves')
        with self.assertRaises(PendingTask) as exc:
            engine.draft(opportunity['id'])
        with self.assertRaisesRegex(ValueError, 'repeats its parent'):
            engine.complete_task(exc.exception.task_id, {'body': parent['body'], 'title': 'A new hook',
                'claims': [], 'quality_notes': [], 'framework': None})

    def test_unselected_platforms_are_not_batched(self):
        profile_path = self.engine.store.data / 'creator/profile.json'
        profile = json.loads(profile_path.read_text())
        profile['platforms'] = ['x']
        profile_path.write_text(json.dumps(profile))
        run = Scheduler(self.engine).run('weekly_linkedin')
        self.assertEqual(run['status'], 'COMPLETED')
        self.assertEqual(run['stages'][1]['slots'], [])
        self.assertEqual(run['stages'][1]['skipped_reason'], 'Platform not selected by creator')

    def test_future_observation_does_not_become_current_winner(self):
        for index in range(5):
            post = self.publish(self.post(index))
            self.engine.manual_metrics(post['id'], {'impressions': 1000, 'bookmarks': 40 if index == 0 else 4},
                observed_at=(datetime.now(timezone.utc) + timedelta(days=2)).isoformat())
        self.assertEqual(winners(self.engine.store), [])

    def test_crlf_source_bytes_survive_capture_and_move(self):
        path = self.engine.store.root / 'windows-call.txt'
        original = b'Morgan: Name the next owner before the handoff.\r\nMorgan: Keep the original question next to the decision.\r\n'
        path.write_bytes(original)
        source = self.engine.capture(path)
        self.assertEqual((self.engine.store.root / source['path']).read_bytes(), original)
        self.assertEqual(self.engine.store.source_text(source['id']).encode(), original)
        ref = {'source_id': source['id'], 'start_line': 1, 'end_line': 2, 'quote': original.decode().rstrip('\r\n')}
        self.engine.store.validate_reference(ref)

    def test_metric_alias_collisions_and_boolean_counts_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Duplicate metric'):
            normalize_metrics({'bookmarks': 4, 'saves': 8})
        with self.assertRaisesRegex(ValueError, 'not boolean'):
            normalize_metrics({'impressions': True})
