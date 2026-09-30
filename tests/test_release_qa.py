"""Regression coverage for failures found during the release QA audit."""
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from contentmaxxing.engine import Engine
from contentmaxxing.kickoff import Kickoff
from contentmaxxing.export import export_workspace
from contentmaxxing.providers import OpenAICompatibleProvider, PendingTask
from contentmaxxing.store import Store, atomic_text
from test_vertical import FIXTURES, WorkspaceFixture


class ReleaseQATests(WorkspaceFixture, unittest.TestCase):
    def test_agent_result_files_do_not_break_kickoff_resume(self):
        with tempfile.TemporaryDirectory() as folder:
            engine = Engine(folder, provider_name='external')
            kickoff = Kickoff(engine)
            profile = json.loads((FIXTURES / 'creator.json').read_text())
            state = kickoff.run(answers=profile, sources=[FIXTURES / 'transcript.txt'], mode='interview')
            self.assertEqual(state['phase'], 'MINING')
            task = engine.store.get('tasks', state['pending_tasks'][0]['id'])
            response = self.engine.get_provider().generate(task)
            result_file = engine.store.data / 'tasks/mining-result.json'
            result_file.write_text(json.dumps(response))
            engine.complete_task(task['id'], json.loads(result_file.read_text()))
            resumed = kickoff.run()
            self.assertEqual(resumed['phase'], 'CHOOSE_TOPICS')
            ids = [idea['id'] for idea in engine.store.list('ideas')]
            partial = engine.store.data / 'tasks/unfinished-result.json'
            partial.write_text('{unfinished')
            kickoff.run()
            self.assertEqual([idea['id'] for idea in engine.store.list('ideas')], ids)
            self.assertEqual(len(engine.store.list('tasks')), 1)
            self.assertEqual(json.loads(result_file.read_text()), response)
            self.assertEqual(partial.read_text(), '{unfinished')

    def test_corrupt_canonical_record_is_reported_instead_of_hidden(self):
        task = self.engine.store.list('tasks')[0]
        path = self.engine.store.path('tasks', task['id'])
        task['id'] = 'task_000000000000'
        path.write_text(json.dumps(task))
        with self.assertRaisesRegex(ValueError, 'Record ID does not match filename'):
            self.engine.store.list('tasks')

    def interrupted_draft(self, external=False):
        engine = Engine(self.temp.name, provider_name='external') if external else self.engine
        engine.select(self.ideas[0]['id'])
        if external:
            with self.assertRaises(PendingTask) as pending:
                engine.draft(self.ideas[0]['id'])
            task = engine.store.get('tasks', pending.exception.task_id)
        original = engine.store.put
        failed = [False]
        def fail_after_content(collection, value):
            result = original(collection, value)
            if collection == 'content' and not failed[0]:
                failed[0] = True
                raise OSError('Simulated interruption after saving content')
            return result
        with patch.object(engine.store, 'put', side_effect=fail_after_content):
            with self.assertRaises(OSError):
                if external:
                    engine.complete_task(task['id'], self.engine.get_provider().generate(task))
                else:
                    engine.draft(self.ideas[0]['id'])
        return engine, next(t for t in engine.store.list('tasks') if t['operation'] == 'draft')

    def test_provider_failure_preserves_checkpoint_and_does_not_duplicate(self):
        engine, task = self.interrupted_draft()
        post = engine.store.list('content')[0]
        self.assertEqual(task.get('planned_result_id'), post['id'])
        result = engine.complete_task(task['id'], engine.get_provider().generate(task))
        self.assertEqual([p['id'] for p in result], [post['id']])
        self.assertEqual(len(engine.store.list('content')), 1)

    def test_completion_recovery_preserves_creator_edits_and_approval(self):
        engine, task = self.interrupted_draft(external=True)
        post = engine.store.list('content')[0]
        edited = engine.edit(post['id'], 'The creator refined this draft during recovery.')
        approved = engine.transition(post['id'], 'APPROVED')
        result = engine.complete_task(task['id'], self.engine.get_provider().generate(task))[0]
        self.assertEqual(result['body'], edited['body'])
        self.assertEqual(result['revision'], edited['revision'])
        self.assertEqual(result['status'], 'APPROVED')
        self.assertEqual(result['approved_at'], approved['approved_at'])
        self.assertEqual(result['created_at'], post['created_at'])

    def test_onboarding_interruption_can_resume_without_missing_brain(self):
        with tempfile.TemporaryDirectory() as folder:
            Store(folder).init()
            engine = Engine(folder)
            profile = json.loads((FIXTURES / 'creator.json').read_text())
            calls = [0]
            def interrupt(path, value):
                calls[0] += 1
                if calls[0] == 2:
                    raise OSError('Simulated disk failure')
                return atomic_text(path, value)
            with patch('contentmaxxing.engine.atomic_text', side_effect=interrupt):
                with self.assertRaises(OSError):
                    engine.onboard(profile)
            self.assertFalse((Path(folder) / 'data/creator/profile.json').exists())
            engine.onboard(profile)
            self.assertTrue({'BRAND_BRAIN.md', 'VOICE.md', 'CONTENT_PILLARS.md', 'OFFER.md'} <= set(engine.store.brain()))

    def test_export_rejects_external_symlinks_before_replacing_existing_archive(self):
        with tempfile.TemporaryDirectory() as folder:
            outside = Path(folder) / 'private.txt'
            outside.write_text('Fictional outside data must not be exported.')
            (self.engine.store.data / 'creator/outside.txt').symlink_to(outside)
            destination = Path(folder) / 'backup.zip'
            destination.write_bytes(b'EXISTING BACKUP')
            with self.assertRaisesRegex(ValueError, 'symlink'):
                export_workspace(self.engine.store, destination)
            self.assertEqual(destination.read_bytes(), b'EXISTING BACKUP')

    def test_export_failure_keeps_previous_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / 'backup.zip'
            destination.write_bytes(b'EXISTING BACKUP')
            with patch.object(zipfile.ZipFile, 'write', side_effect=OSError('Simulated full disk')):
                with self.assertRaises(OSError):
                    export_workspace(self.engine.store, destination)
            self.assertEqual(destination.read_bytes(), b'EXISTING BACKUP')
            self.assertEqual(list(Path(folder).iterdir()), [destination])

    def test_provider_http_allowlist_checks_hostname_not_prefix(self):
        for address in ['http://localhost.example.test/v1', 'http://127.0.0.1.example.test/v1',
                        'http://localhost@remote.example.test/v1', 'https:///missing-host']:
            with self.subTest(address=address), self.assertRaises(ValueError):
                OpenAICompatibleProvider(address, 'model', 'fictional-key')
        for address in ['http://localhost:1234/v1', 'http://127.0.0.1:8080/v1', 'http://[::1]:8080/v1', 'https://models.example.test/v1']:
            OpenAICompatibleProvider(address, 'model', 'fictional-key')
