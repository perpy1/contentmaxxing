import contextlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from contentmaxxing.cli import main
from contentmaxxing.engine import Engine
from contentmaxxing.export import export_workspace
from contentmaxxing.feedback import Feedback
from contentmaxxing.overview import overview
from contentmaxxing.providers import PendingTask
from contentmaxxing.revisions import Revisions
from test_vertical import WorkspaceFixture


class RevisionTests(WorkspaceFixture, unittest.TestCase):
    def revision_task(self, post, direction='Make the opening more concrete.'):
        engine = Engine(self.temp.name, provider_name='external')
        with self.assertRaises(PendingTask) as pending:
            engine.revise(post['id'], direction)
        return engine.store.get('tasks', pending.exception.task_id)

    def output(self, task):
        ref = task['inputs']['idea']['source_reference'][0]
        return {'body': 'Client questions were getting lost across folders. That was the problem to fix.',
                'title': 'A clearer handoff', 'framework': None,
                'claims': [{'claim': 'Client questions were getting lost across folders.', 'source_reference': ref}],
                'quality_notes': ['Simplified the opening; factual and voice review required.']}

    def test_revise_same_content_preserves_history_and_invalidates_approval(self):
        post = self.engine.transition(self.post()['id'], 'APPROVED')
        feedback = Feedback(self.engine.store).add(post['id'], 'Start with the actual problem.', 'Demo')
        task = self.revision_task(post, '')
        self.assertEqual(task['inputs']['creator_feedback'][0]['id'], feedback['id'])
        self.assertEqual(self.engine.store.get('content', post['id']), post)
        revised = self.engine.complete_task(task['id'], self.output(task))[0]
        self.assertEqual(revised['id'], post['id'])
        self.assertEqual(revised['created_at'], post['created_at'])
        self.assertEqual(revised['revision'], 2)
        self.assertEqual(revised['status'], 'NEEDS_REVIEW')
        self.assertIsNone(revised['approved_at'])
        history = Revisions(self.engine.store).history(post['id'])
        self.assertEqual(history[0]['before'], post)
        self.assertEqual(history[0]['after']['body'], revised['body'])
        self.assertEqual(history[0]['status'], 'APPLIED')
        self.assertEqual(len(self.engine.store.list('content')), 1)
        self.assertEqual(self.engine.complete_task(task['id'], {})[0], revised)
        self.assertEqual(len(Revisions(self.engine.store).history(post['id'])), 1)

    def test_resume_pending_revision_reuses_task_and_cannot_overwrite_newer_edit(self):
        post = self.post()
        task = self.revision_task(post)
        with self.assertRaises(PendingTask) as repeated:
            Engine(self.temp.name, provider_name='external').revise(post['id'])
        self.assertEqual(repeated.exception.task_id, task['id'])
        edited = self.engine.edit(post['id'], 'Creator edited this while the agent was working.')
        with self.assertRaisesRegex(ValueError, 'Draft changed'):
            self.engine.complete_task(task['id'], self.output(task))
        self.assertEqual(self.engine.store.get('content', post['id']), edited)
        Revisions(self.engine.store).cancel(task['id'], 'Replace the obsolete revision request.')
        with self.assertRaisesRegex(ValueError, 'cancelled'):
            self.engine.complete_task(task['id'], self.output(task))
        self.assertEqual(overview(self.temp.name)['pending_tasks'], [])
        next_task = self.revision_task(edited)
        self.assertEqual(next_task['inputs']['revision_target']['body'], edited['body'])

    def test_new_approval_and_publication_make_pending_revision_stale(self):
        post = self.post()
        task = self.revision_task(post)
        self.engine.transition(post['id'], 'APPROVED')
        with self.assertRaisesRegex(ValueError, 'Draft changed'):
            self.engine.complete_task(task['id'], self.output(task))
        published = self.engine.transition(post['id'], 'PUBLISHED', url='https://example.com/fictional')
        with self.assertRaisesRegex(ValueError, 'Draft changed'):
            self.engine.complete_task(task['id'], self.output(task))
        self.assertEqual(self.engine.store.get('content', post['id']), published)

    def test_requested_platform_and_job_survive_later_idea_selection(self):
        post = self.post()
        self.engine.select(post['idea_id'], platform='linkedin', job='Trust')
        task = self.revision_task(post)
        self.assertEqual(task['inputs']['platform'], 'x')
        self.assertEqual(task['inputs']['idea']['format'], post['format'])
        self.assertEqual(task['inputs']['idea']['primary_job'], post['primary_job'])
        revised = self.engine.complete_task(task['id'], self.output(task))[0]
        self.assertEqual(revised['platform'], 'x')
        self.assertEqual(self.engine.store.get('ideas', post['idea_id'])['best_platform'], 'linkedin')

    def test_claim_validation_failure_leaves_content_and_history_untouched(self):
        post = self.post()
        task = self.revision_task(post)
        result = self.output(task)
        result['claims'][0]['source_reference']['quote'] = 'Invented quote'
        with self.assertRaisesRegex(ValueError, 'does not match'):
            self.engine.complete_task(task['id'], result)
        self.assertEqual(self.engine.store.get('content', post['id']), post)
        self.assertEqual(Revisions(self.engine.store).history(post['id']), [])

    def test_commit_recovers_after_journal_before_content_write(self):
        post = self.post()
        task = self.revision_task(post)
        original = self.engine.store.put
        def fail(collection, value):
            if collection == 'content':
                raise OSError('Crash before content write')
            return original(collection, value)
        with patch.object(self.engine.store, 'put', side_effect=fail):
            with self.assertRaises(OSError):
                self.engine.complete_task(task['id'], self.output(task))
        self.assertEqual(self.engine.store.get('content', post['id']), post)
        changed_output = {**self.output(task), 'body': 'Retry must not replace the already prepared candidate.'}
        recovered = Engine(self.temp.name).complete_task(task['id'], changed_output)[0]
        self.assertEqual(recovered['body'], self.output(task)['body'])
        self.assertEqual(len(Revisions(self.engine.store).history(post['id'])), 1)

    def test_crash_after_content_write_preserves_subsequent_creator_edit(self):
        post = self.post()
        task = self.revision_task(post)
        original = self.engine.store.put
        def fail(collection, value):
            if collection == 'revisions' and value['status'] == 'APPLIED':
                raise OSError('Crash after content write')
            return original(collection, value)
        with patch.object(self.engine.store, 'put', side_effect=fail):
            with self.assertRaises(OSError):
                self.engine.complete_task(task['id'], self.output(task))
        edited = self.engine.edit(post['id'], 'A newer creator edit that must survive recovery.')
        recovered = Engine(self.temp.name).complete_task(task['id'], {})[0]
        self.assertEqual(recovered['body'], edited['body'])
        self.assertEqual(recovered['revision'], 3)
        self.assertEqual(len(Revisions(self.engine.store).history(post['id'])), 2)
        self.assertIn(edited['body'], (self.engine.store.data / 'content' / (post['id'] + '.md')).read_text())

    def test_crash_after_content_write_preserves_subsequent_approval(self):
        post = self.post()
        task = self.revision_task(post)
        original = self.engine.store.put
        def fail(collection, value):
            if collection == 'tasks' and value['status'] == 'COMPLETED' and value['id'] == task['id']:
                raise OSError('Crash before task completion')
            return original(collection, value)
        with patch.object(self.engine.store, 'put', side_effect=fail):
            with self.assertRaises(OSError):
                self.engine.complete_task(task['id'], self.output(task))
        approved = self.engine.transition(post['id'], 'APPROVED')
        result = Revisions(self.engine.store).cancel(task['id'], 'Caller thought it was unfinished')
        self.assertEqual(result['status'], 'COMPLETED')
        self.assertEqual(self.engine.store.get('content', post['id'])['approved_at'], approved['approved_at'])

    def test_prepared_conflict_can_be_abandoned_without_erasing_newer_work(self):
        post = self.post()
        task = self.revision_task(post)
        original = self.engine.store.put
        with patch.object(self.engine.store, 'put', side_effect=lambda c, v: (_ for _ in ()).throw(OSError()) if c == 'content' else original(c, v)):
            with self.assertRaises(OSError):
                self.engine.complete_task(task['id'], self.output(task))
        self.engine.edit(post['id'], 'New work supersedes the pending candidate.')
        Revisions(self.engine.store).cancel(task['id'], 'Creator changed the draft first.')
        changes = Revisions(self.engine.store).history(post['id'])
        self.assertEqual(changes[0]['status'], 'ABANDONED')
        self.assertEqual(self.engine.store.get('content', post['id'])['body'], 'New work supersedes the pending candidate.')

    def test_revision_requires_direction_and_local_editable_content(self):
        post = self.post()
        with self.assertRaisesRegex(ValueError, 'Supply revision direction'):
            self.engine.revise(post['id'])
        post['remote'] = {'draft_id': 'remote-demo'}
        self.engine.store.put('content', post)
        with self.assertRaisesRegex(ValueError, 'local unscheduled'):
            self.engine.revise(post['id'], 'Change the opening')

    def test_pending_revision_is_not_reused_as_new_platform_draft(self):
        post = self.post()
        revision = self.revision_task(post)
        with self.assertRaises(PendingTask) as pending:
            Engine(self.temp.name, provider_name='external').draft(post['idea_id'])
        self.assertNotEqual(pending.exception.task_id, revision['id'])
        self.assertNotIn('revision_target', self.engine.store.get('tasks', pending.exception.task_id)['inputs'])

    def test_refresh_includes_content_specific_feedback_and_freezes_prepared_revision(self):
        post = self.post()
        task = self.revision_task(post)
        feedback = Feedback(self.engine.store).add(post['id'], 'Remove this post opening.', 'Demo')
        refreshed = self.engine.refresh_feedback(task['id'])
        self.assertEqual(refreshed['inputs']['creator_feedback'][0]['id'], feedback['id'])
        self.engine.complete_task(task['id'], self.output(task))
        with self.assertRaisesRegex(ValueError, 'uncommitted pending'):
            self.engine.refresh_feedback(task['id'])

    def test_cli_revision_and_history_survive_export_to_another_folder(self):
        post = self.post()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(['--workspace', self.temp.name, '--provider', 'external', 'revise', post['id'], '--direction', 'Clarify the opening.'])
        self.assertEqual(code, 0)
        task_id = json.loads(output.getvalue())['task_id']
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / 'portable.zip'
            export_workspace(self.engine.store, archive)
            with zipfile.ZipFile(archive) as bundle:
                bundle.extractall(Path(folder) / 'moved')
            moved = Engine(Path(folder) / 'moved')
            task = moved.store.get('tasks', task_id)
            revised = moved.complete_task(task_id, self.output(task))[0]
            self.assertEqual(revised['id'], post['id'])
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = main(['--workspace', str(moved.store.root), 'revisions', post['id']])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(output.getvalue())[0]['before']['body'], post['body'])

    def test_older_workspace_can_revise_without_replacing_creator_files(self):
        post = self.post()
        schema = self.engine.store.assets / 'schemas/revision.schema.json'
        skill = self.engine.store.assets / 'skills/content-revision/SKILL.md'
        schema.unlink()
        skill.unlink()
        brain = self.engine.store.brain()
        task = self.revision_task(post)
        revised = self.engine.complete_task(task['id'], self.output(task))[0]
        self.assertEqual(revised['revision'], 2)
        self.assertEqual(self.engine.store.brain(), brain)
        self.assertFalse(schema.exists())
        self.assertFalse(skill.exists())

    def test_prepared_revision_rechecks_evidence_before_first_content_write(self):
        post = self.post()
        task = self.revision_task(post)
        original = self.engine.store.put
        def fail(collection, value):
            if collection == 'content':
                raise OSError('Interrupted before first content write')
            return original(collection, value)
        with patch.object(self.engine.store, 'put', side_effect=fail):
            with self.assertRaises(OSError):
                self.engine.complete_task(task['id'], self.output(task))
        (self.engine.store.root / self.source['path']).write_text('Original evidence was edited.')
        with self.assertRaisesRegex(ValueError, 'Original source changed'):
            Engine(self.temp.name).complete_task(task['id'], {})
        self.assertEqual(self.engine.store.get('content', post['id']), post)


if __name__ == '__main__':
    unittest.main()
