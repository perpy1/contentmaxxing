import contextlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import yaml

from contentmaxxing.cli import main
from contentmaxxing.engine import Engine
from contentmaxxing.export import export_workspace
from contentmaxxing.kickoff import Kickoff
from contentmaxxing.mining import MiningIncomplete, latest, source_progress
from contentmaxxing.overview import overview
from contentmaxxing.providers import ExtractiveProvider, PendingTask
from contentmaxxing.store import Store, atomic_text
from test_vertical import WorkspaceFixture, FIXTURES


class MiningTests(WorkspaceFixture, unittest.TestCase):
    def capture_large(self, text=None):
        text = text or '\r\n'.join('Morgan: Decision %03d assigns a distinct owner to request number %03d.' % (n, n) for n in range(100))
        path = self.engine.store.root / 'large-source.txt'
        path.write_bytes(text.encode())
        return self.engine.capture(path)

    def configure(self, calls=2):
        config = self.engine.store.config
        config['mining'] = {'chunk_chars': 512, 'overlap_chars': 100, 'chunks_per_call': calls}
        atomic_text(self.engine.store.root / 'config.yaml', yaml.safe_dump(config))

    def test_bounded_internal_calls_resume_all_topics_without_duplicates(self):
        self.configure()
        source = self.capture_large()
        with self.assertRaises(MiningIncomplete) as stopped:
            self.engine.mine(source['id'])
        self.assertEqual(stopped.exception.progress['completed_chunks'], 2)
        for _ in range(100):
            try:
                ideas = Engine(self.temp.name).mine(source['id'])
                break
            except MiningIncomplete:
                pass
        else:
            self.fail('Mining did not finish')
        self.assertEqual(len(ideas), 100)
        state = source_progress(self.engine.store, source['id'])
        self.assertEqual(state['status'], 'COMPLETED')
        self.assertEqual(state['covered_chars'], state['source_chars'])
        tasks = [t for t in self.engine.store.list('tasks') if t['inputs'].get('source_id') == source['id']]
        self.assertTrue(all(len(t['inputs']['text']) <= 512 for t in tasks))
        before = self.engine.store.list('ideas')
        self.assertEqual({i['id'] for i in self.engine.mine(source['id'])}, {i['id'] for i in ideas})
        self.assertEqual(self.engine.store.list('ideas'), before)

    def test_external_resume_preserves_original_line_citations_and_identity(self):
        self.configure()
        source = self.capture_large()
        engine = Engine(self.temp.name, provider_name='external')
        completed_ids = []
        for _ in range(100):
            try:
                result = engine.mine(source['id'])
                break
            except PendingTask as exc:
                task = engine.store.get('tasks', exc.task_id)
                with self.assertRaises(PendingTask) as repeated:
                    Engine(self.temp.name, provider_name='external').mine(source['id'])
                self.assertEqual(repeated.exception.task_id, task['id'])
                self.assertNotIn(task['id'], completed_ids)
                output = ExtractiveProvider().extract(task)
                engine.complete_task(task['id'], output)
                engine.complete_task(task['id'], output)
                completed_ids.append(task['id'])
        else:
            self.fail('Mining did not finish')
        self.assertEqual(len(result), 100)
        self.assertGreater(max(r['source_reference'][0]['start_line'] for r in result), 90)
        self.assertEqual(len(set(completed_ids)), source_progress(engine.store, source['id'])['total_chunks'])

    def test_mining_rejects_real_quotes_outside_supplied_window_before_any_write(self):
        self.configure()
        source = self.capture_large()
        engine = Engine(self.temp.name, provider_name='external')
        with self.assertRaises(PendingTask) as raised:
            engine.mine(source['id'])
        task = engine.store.get('tasks', raised.exception.task_id)
        output = ExtractiveProvider().extract(task)
        output['ideas'].append({'topic': 'Hidden decision', 'category': 'process',
            'quote': engine.store.source_text(source['id']).splitlines()[-1], 'start_line': 100, 'end_line': 100})
        before = engine.store.list('ideas')
        with self.assertRaisesRegex(ValueError, 'not supplied'):
            engine.complete_task(task['id'], output)
        self.assertEqual(before, engine.store.list('ideas'))
        self.assertEqual(source_progress(engine.store, source['id'])['completed_chunks'], 0)

    def test_giant_line_windows_have_full_coverage_and_bounded_text(self):
        self.configure()
        source = self.capture_large('Speaker: ' + 'very long uninterrupted turn with a recurring point ' * 600)
        engine = Engine(self.temp.name, provider_name='external')
        with self.assertRaises(PendingTask):
            engine.mine(source['id'])
        run = latest(engine.store, source['id'])
        end = 0
        for part in run['parts']:
            self.assertLessEqual(part['start_offset'], end)
            self.assertLessEqual(part['end_offset'] - part['start_offset'], 512)
            self.assertEqual(part['start_line'], 1)
            end = part['end_offset']
        self.assertEqual(end, run['source_chars'])

    def test_export_and_move_resumes_same_part_and_frozen_instructions(self):
        self.configure()
        source = self.capture_large()
        engine = Engine(self.temp.name, provider_name='external')
        with self.assertRaises(PendingTask) as first:
            engine.mine(source['id'])
        first_task = engine.store.get('tasks', first.exception.task_id)
        engine.complete_task(first_task['id'], ExtractiveProvider().extract(first_task))
        run = latest(engine.store, source['id'])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'copy.zip'
            export_workspace(engine.store, path)
            with zipfile.ZipFile(path) as archive:
                archive.extractall(Path(folder) / 'moved')
            moved = Engine(Path(folder) / 'moved', provider_name='external')
            atomic_text(moved.store.assets / 'skills/transcript-mining/SKILL.md', 'New future instructions')
            with self.assertRaises(PendingTask) as next_part:
                moved.mine(source['id'])
            self.assertEqual(next_part.exception.task_id, run['parts'][1]['task_id'])
            next_task = moved.store.get('tasks', next_part.exception.task_id)
            self.assertEqual(next_task['instructions'], first_task['instructions'])

    def test_manifest_checkpoint_recovers_missing_task_after_crash(self):
        self.configure()
        source = self.capture_large()
        engine = Engine(self.temp.name, provider_name='external')
        with patch.object(engine, 'execute', side_effect=OSError('before task write')):
            with self.assertRaises(OSError):
                engine.mine(source['id'])
        planned = latest(engine.store, source['id'])['parts'][0]['task_id']
        self.assertFalse(engine.store.path('tasks', planned).exists())
        with self.assertRaises(PendingTask) as resumed:
            Engine(self.temp.name, provider_name='external').mine(source['id'])
        self.assertEqual(resumed.exception.task_id, planned)

    def test_provider_failure_needs_explicit_retry_and_restart_requires_completion(self):
        self.configure()
        source = self.capture_large()
        provider = ExtractiveProvider()
        engine = Engine(self.temp.name, provider=provider)
        with patch.object(provider, 'extract', side_effect=ValueError('Model unavailable')):
            with self.assertRaisesRegex(ValueError, 'Model unavailable'):
                engine.mine(source['id'])
        with self.assertRaises(PendingTask):
            engine.mine(source['id'])
        with self.assertRaisesRegex(ValueError, 'Finish the saved'):
            engine.mine(source['id'], restart=True)
        with self.assertRaises(MiningIncomplete):
            engine.mine(source['id'], retry=True)
        self.assertEqual(source_progress(engine.store, source['id'])['completed_chunks'], 2)

    def test_progress_between_chunks_is_read_only_and_does_not_claim_complete(self):
        self.configure()
        source = self.capture_large()
        with self.assertRaises(MiningIncomplete):
            self.engine.mine(source['id'])
        root = self.engine.store.root
        before = {str(p): p.read_bytes() for p in root.rglob('*') if p.is_file()}
        state = overview(root)
        self.assertEqual(state['stage'], 'CAPTURE')
        self.assertEqual(state['next_action']['arguments']['source_ids'], [source['id']])
        self.assertEqual(before, {str(p): p.read_bytes() for p in root.rglob('*') if p.is_file()})
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(['--workspace', self.temp.name, 'mine', source['id']])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())['status'], 'IN_PROGRESS')

    def test_kickoff_waits_for_entire_source_not_just_first_chunk(self):
        self.configure(calls=1)
        source = self.capture_large()
        engine = Engine(self.temp.name, provider_name='external')
        launch = Kickoff(engine)
        result = launch.run()
        self.assertEqual(result['phase'], 'MINING')
        first_task = engine.store.get('tasks', result['pending_tasks'][0]['id'])
        engine.complete_task(first_task['id'], ExtractiveProvider().extract(first_task))
        next_step = launch.run()
        self.assertEqual(next_step['phase'], 'MINING')
        self.assertNotEqual(next_step['pending_tasks'][0]['id'], first_task['id'])
        progress = next(p for p in next_step['mining_progress'] if p['source_id'] == source['id'])
        self.assertEqual(progress['completed_chunks'], 1)

    def test_changed_source_leaves_saved_pass_intact(self):
        self.configure()
        source = self.capture_large()
        with self.assertRaises(MiningIncomplete):
            self.engine.mine(source['id'])
        original = self.engine.store.root / source['path']
        before = latest(self.engine.store, source['id'])
        original.write_text('Changed')
        with self.assertRaisesRegex(ValueError, 'Original source changed'):
            self.engine.mine(source['id'])
        self.assertEqual(latest(self.engine.store, source['id']), before)

    def test_older_workspace_can_mine_without_replacing_custom_instructions(self):
        self.configure()
        source = self.capture_large()
        schema = self.engine.store.assets / 'schemas/mining-run.schema.json'
        schema.unlink()
        path = self.engine.store.assets / 'skills/transcript-mining/SKILL.md'
        custom = path.read_text() + '\nCreator customization: preserve the questions.\n'
        path.write_text(custom)
        with self.assertRaises(MiningIncomplete):
            self.engine.mine(source['id'])
        self.assertFalse(schema.exists())
        self.assertEqual(path.read_text(), custom)
        self.assertEqual(source_progress(self.engine.store, source['id'])['completed_chunks'], 2)

    def test_completed_pass_restart_is_explicit_and_keeps_prior_ids(self):
        self.configure(calls=100)
        source = self.capture_large()
        first = self.engine.mine(source['id'])
        first_run = latest(self.engine.store, source['id'])
        self.engine.mine(source['id'])
        self.assertEqual(latest(self.engine.store, source['id'])['id'], first_run['id'])
        second = self.engine.mine(source['id'], restart=True)
        self.assertNotEqual(latest(self.engine.store, source['id'])['id'], first_run['id'])
        self.assertEqual({i['id'] for i in first}, {i['id'] for i in second})


if __name__ == '__main__':
    unittest.main()
