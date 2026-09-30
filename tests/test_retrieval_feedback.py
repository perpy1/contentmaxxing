import contextlib
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import yaml

from contentmaxxing.cli import main
from contentmaxxing.engine import Engine
from contentmaxxing.export import export_workspace
from contentmaxxing.feedback import Feedback
from contentmaxxing.providers import PendingTask
from contentmaxxing.retrieval import SourceLibrary, validate_task_reference
from contentmaxxing.store import Store, atomic_text
from test_vertical import FIXTURES, WorkspaceFixture


class RetrievalFeedbackTest(WorkspaceFixture, unittest.TestCase):
    def capture_text(self, text, name='work-notes.txt', kind='work log'):
        path = Path(self.temp.name) / name
        path.write_text(text, encoding='utf-8')
        return self.engine.capture(path, kind=kind, consent='fictional')

    def configure(self, **sections):
        config = self.engine.store.config
        config.update(sections)
        atomic_text(self.engine.store.root / 'config.yaml', yaml.safe_dump(config))

    def pending(self, idea_id):
        engine = Engine(self.temp.name, provider_name='external')
        with self.assertRaises(PendingTask) as raised:
            engine.draft(idea_id)
        return self.engine.store.get('tasks', raised.exception.task_id)

    def response(self, task, ref=None):
        ref = ref or task['inputs']['idea']['source_reference'][0]
        return {'body': 'A source-backed working note.', 'title': '', 'framework': None,
                'claims': [{'claim': 'A claim for human review', 'source_reference': ref}], 'quality_notes': []}

    def cli(self, *args):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = main(['--workspace', self.temp.name, *args])
        self.assertEqual(code, 0, errors.getvalue())
        return json.loads(output.getvalue())

    def test_search_finds_specific_evidence_without_writes(self):
        self.capture_text('Routine design feedback without the incident.\n' * 200, 'noise.txt')
        evidence = self.capture_text('Client: The launch seemed faster.\nCreator: We have not measured launch time.\n'
            'Creator: The handoff template now has a named backup owner.\n', 'handoff.txt')
        root = self.engine.store.root
        before = {str(p): p.read_bytes() for p in root.rglob('*') if p.is_file()}
        result = SourceLibrary(self.engine.store).search('handoff backup owner')
        self.assertEqual(result['results'][0]['source_id'], evidence['id'])
        self.assertIn('not measured', result['results'][0]['quote'])
        for passage in result['results']:
            self.engine.store.validate_reference(passage)
        self.assertEqual(before, {str(p): p.read_bytes() for p in root.rglob('*') if p.is_file()})
        self.assertEqual(SourceLibrary(self.engine.store).search('unfindabletoken')['results'], [])

    def test_filters_long_lines_and_original_line_numbers(self):
        source = self.capture_text('Preface\r\n' + 'detail ' * 3000 + ' café ownership backed by a checklist.\r\nEnd', kind='research')
        library = SourceLibrary(self.engine.store)
        result = library.search('café ownership', [source['id']], kind='research', limit=2, max_chars=600)
        self.assertTrue(result['results'])
        self.assertLessEqual(result['returned_chars'], 600)
        for passage in result['results']:
            self.engine.store.validate_reference(passage)
            self.assertEqual(passage['start_line'], 2)
        self.assertEqual(library.search('ownership', [source['id']], kind='transcript')['results'], [])
        with self.assertRaisesRegex(ValueError, 'exceed'):
            library.read(source['id'], 2, 2, max_chars=100)
        for options in ({'max_chars': 0}, {'limit': 0}, {'limit': True}):
            with self.assertRaises(ValueError):
                library.search('ownership', **options)

    def test_stable_passages_after_export_move_and_source_mutation_detected(self):
        first = SourceLibrary(self.engine.store).search('client questions')
        with tempfile.TemporaryDirectory() as target:
            archive = Path(target) / 'workspace.zip'
            export_workspace(self.engine.store, archive)
            with zipfile.ZipFile(archive) as bundle:
                bundle.extractall(Path(target) / 'moved')
            moved = Store(Path(target) / 'moved')
            self.assertEqual(first, SourceLibrary(moved).search('client questions'))
            atomic_text(moved.root / self.source['path'], 'Changed original')
            with self.assertRaisesRegex(ValueError, 'Original source changed'):
                SourceLibrary(moved).search('client')

    def test_bounded_draft_keeps_cited_evidence_and_rejects_unseen_quote(self):
        source = self.capture_text('unrelated detail about supplies\n' * 900 +
            'Creator: We name a backup owner in every handoff.\n' +
            'unrelated detail about supplies\n' * 900 + 'Creator: The launch has not been measured.\n')
        ref = {'quote': 'Creator: We name a backup owner in every handoff.', 'start_line': 901, 'end_line': 901}
        idea = self.engine.persist_idea(self.engine.idea_from(
            {**ref, 'topic': 'Name a backup owner', 'category': 'process'}, source['id'], 'external'))
        self.engine.select(idea['id'])
        self.configure(retrieval={'draft_source_chars': 800, 'draft_source_passages': 3})
        task = self.pending(idea['id'])
        context = task['inputs']['source_context']
        self.assertLessEqual(context['returned_chars'], 800)
        self.assertGreater(context['available_chars'], 50000)
        passages = task['inputs']['sources'][source['id']]
        self.assertTrue(any(ref['quote'] in p['quote'] for p in passages))
        # A quote can be real yet not be present in the actual task context.
        invisible = {'source_id': source['id'], 'start_line': 1802, 'end_line': 1802,
                     'quote': 'Creator: The launch has not been measured.'}
        with self.assertRaisesRegex(ValueError, 'not supplied in the task excerpts'):
            self.engine.complete_task(task['id'], self.response(task, invisible))
        self.assertEqual(self.engine.store.list('content'), [])
        post = self.engine.complete_task(task['id'], self.response(task))[0]
        self.assertEqual(post['status'], 'NEEDS_REVIEW')

    def test_short_workshop_source_keeps_complete_context_within_budget(self):
        # Native Codex read this small source, but the old context builder clipped
        # lines 1 and 9 from the writer snapshot and caused two avoidable retries.
        source = self.engine.capture(FIXTURES / 'voice-source.txt', consent='fictional')
        text = self.engine.store.source_text(source['id']).rstrip('\n')
        lines = text.splitlines()
        reference = {'source_id': source['id'], 'start_line': 7, 'end_line': 7, 'quote': lines[6]}
        context = SourceLibrary(self.engine.store).context([reference], 'three fields practice repair notes')
        passages = context['sources'][source['id']]
        self.assertEqual(len(passages), 1)
        self.assertEqual(passages[0]['quote'], text)
        self.assertEqual(context['source_context']['returned_chars'], len(text))
        for number in (1, 3, 7, 9):
            ref = {'source_id': source['id'], 'start_line': number, 'end_line': number, 'quote': lines[number-1]}
            validate_task_reference(context, ref)

    def test_overlapping_citation_neighborhoods_are_counted_and_supplied_once(self):
        source = self.capture_text(''.join('Creator: Detail number %d belongs to this working note.\n' % n for n in range(100)))
        lines = self.engine.store.source_text(source['id']).splitlines()
        refs = [{'source_id': source['id'], 'start_line': n, 'end_line': n, 'quote': lines[n-1]} for n in (25, 27)]
        context = SourceLibrary(self.engine.store).context(refs, '', max_chars=1600, max_passages=2)
        passages = context['sources'][source['id']]
        for left, right in zip(passages, passages[1:]):
            self.assertFalse(SourceLibrary.overlap(left, right))
        self.assertEqual(context['source_context']['returned_chars'], sum(len(p['quote']) for p in passages))
        self.assertLessEqual(context['source_context']['returned_chars'], 1600)
        for ref in refs:
            validate_task_reference(context, ref)

    def test_short_source_expansion_reserves_every_other_required_citation(self):
        sources = [self.capture_text(('Creator: Some nearby detail.\n' * 17) + 'Creator: Unique proof %d.' % n,
                                     name='proof-%d.txt' % n) for n in range(2)]
        refs = []
        for source in sources:
            lines = self.engine.store.source_text(source['id']).splitlines()
            refs.append({'source_id': source['id'], 'start_line': len(lines), 'end_line': len(lines), 'quote': lines[-1]})
        context = SourceLibrary(self.engine.store).context(refs, 'proof', max_chars=600, max_passages=2)
        self.assertLessEqual(context['source_context']['returned_chars'], 600)
        self.assertEqual(set(context['sources']), {s['id'] for s in sources})
        for ref in refs:
            validate_task_reference(context, ref)

    def test_required_proof_is_not_silently_truncated(self):
        source = self.capture_text('long exact source quote ' * 100)
        quote = self.engine.store.source_text(source['id'])
        idea = self.engine.persist_idea(self.engine.idea_from({'topic': 'Broad citation', 'category': 'proof',
            'quote': quote, 'start_line': 1, 'end_line': 1}, source['id'], 'external'))
        self.engine.select(idea['id'])
        self.configure(retrieval={'draft_source_chars': 256})
        before = self.engine.store.list('tasks')
        with self.assertRaisesRegex(ValueError, 'Cited evidence exceeds'):
            self.engine.draft(idea['id'])
        self.assertEqual(self.engine.store.get('ideas', idea['id'])['status'], 'SELECTED')
        self.assertEqual(before, self.engine.store.list('tasks'))

    def test_repeated_quote_cannot_be_attributed_to_an_unseen_occurrence(self):
        source = self.capture_text('Client: The next step is clear.\n' + 'Unrelated administrative notes.\n' * 800 +
                                   'Creator: The next step is clear.\n')
        idea = self.engine.persist_idea(self.engine.idea_from({'topic': 'Clarity of next steps',
            'category': 'customer language', 'quote': 'The next step is clear.',
            'start_line': 1, 'end_line': 1}, source['id'], 'external'))
        self.engine.select(idea['id'])
        self.configure(retrieval={'draft_source_chars': 256})
        task = self.pending(idea['id'])
        ref = {'source_id': source['id'], 'start_line': 802, 'end_line': 802,
               'quote': 'The next step is clear.'}
        self.engine.store.validate_reference(ref)
        with self.assertRaisesRegex(ValueError, 'at the cited lines'):
            self.engine.complete_task(task['id'], self.response(task, ref))

    def test_attach_other_source_before_draft_and_preserve_existing_snapshots(self):
        source = self.capture_text('Creator: The next action field is now required.\n')
        idea = self.engine.select(self.ideas[0]['id'])
        ref = {'source_id': source['id'], 'start_line': 1, 'end_line': 1,
               'quote': 'Creator: The next action field is now required.'}
        cited = self.engine.cite_idea(idea['id'], **ref)
        self.assertEqual(len(cited['source_reference']), 2)
        self.assertEqual(self.engine.cite_idea(idea['id'], **ref)['source_reference'], cited['source_reference'])
        task = self.pending(idea['id'])
        self.assertEqual(set(task['inputs']['sources']), {self.source['id'], source['id']})
        with self.assertRaisesRegex(ValueError, 'already snapshots'):
            self.engine.cite_idea(idea['id'], source['id'], 1, 1, 'next action field')
        post = self.engine.complete_task(task['id'], self.response(task, ref))[0]
        self.assertEqual(post['claims'][0]['source_reference'], ref)

    def test_preexisting_whole_source_task_remains_completable(self):
        idea = self.engine.select(self.ideas[0]['id'])
        task = self.pending(idea['id'])
        task['inputs'].pop('source_context')
        task['inputs']['sources'] = {self.source['id']: self.engine.store.source_text(self.source['id'])}
        self.engine.store.put('tasks', task)
        self.assertEqual(self.engine.complete_task(task['id'], self.response(task))[0]['status'], 'NEEDS_REVIEW')

    def test_pending_draft_can_add_proof_without_changing_idea_or_other_tasks(self):
        idea = self.engine.select(self.ideas[0]['id'])
        task = self.pending(idea['id'])
        source = self.capture_text('Morgan: The form now includes a backup owner.\n')
        ref = {'source_id': source['id'], 'start_line': 1, 'end_line': 1,
               'quote': 'Morgan: The form now includes a backup owner.'}
        with self.assertRaisesRegex(ValueError, 'source not supplied'):
            self.engine.complete_task(task['id'], self.response(task, ref))
        enriched = self.cli('tasks', 'cite', task['id'], '--source', source['id'],
            '--start-line', '1', '--end-line', '1', '--quote', ref['quote'])
        self.assertEqual(enriched['inputs']['idea'], task['inputs']['idea'])
        self.assertEqual(enriched['inputs']['extra_source_reference'], [ref])
        self.assertEqual(self.engine.cite_task(task['id'], **ref), enriched)
        self.assertNotIn(ref, self.engine.store.get('ideas', idea['id'])['source_reference'])
        post = self.engine.complete_task(task['id'], self.response(enriched, ref))[0]
        self.assertIn(ref, post['source_reference'])
        with self.assertRaisesRegex(ValueError, 'uncommitted pending'):
            self.engine.cite_task(task['id'], **ref)

    def test_invalid_task_evidence_does_not_damage_pending_context(self):
        self.engine.select(self.ideas[0]['id'])
        task = self.pending(self.ideas[0]['id'])
        with self.assertRaisesRegex(ValueError, 'does not match'):
            self.engine.cite_task(task['id'], self.source['id'], 1, 1, 'Invented evidence')
        self.assertEqual(self.engine.store.get('tasks', task['id']), task)
        source = self.capture_text('Large evidence sentence. ' * 100)
        self.configure(retrieval={'draft_source_chars': 256})
        with self.assertRaisesRegex(ValueError, 'Cited evidence exceeds'):
            self.engine.cite_task(task['id'], source['id'], 1, 1, self.engine.store.source_text(source['id']))
        self.assertEqual(self.engine.store.get('tasks', task['id']), task)

    def test_feedback_is_explicit_scoped_and_does_not_modify_identity_or_approve(self):
        post = self.post()
        feedback = Feedback(self.engine.store)
        voice = (self.engine.store.data / 'creator/VOICE.md').read_bytes()
        local = feedback.add(post['id'], 'Remove the opening from this post.', 'Demo creator')
        platform = feedback.add(post['id'], 'On X, skip engagement-bait questions.', 'Demo creator', 'platform', 'cta')
        global_rule = feedback.add(post['id'], 'Use concrete nouns in all my writing.', 'Demo creator', 'creator', 'voice')
        self.assertEqual({f['id'] for f in feedback.context('x')}, {platform['id'], global_rule['id']})
        self.assertEqual([f['id'] for f in feedback.context('linkedin')], [global_rule['id']])
        self.assertEqual(len(feedback.context('x', post['id'])), 3)
        self.assertEqual(local['scope'], 'content')
        self.assertEqual(self.engine.store.get('content', post['id']), post)
        self.assertEqual((self.engine.store.data / 'creator/VOICE.md').read_bytes(), voice)
        self.assertEqual(self.engine.store.get('content', post['id'])['status'], 'NEEDS_REVIEW')

    def test_feedback_revision_snapshot_exact_excerpt_and_retry(self):
        post = self.post()
        feedback = Feedback(self.engine.store)
        note = feedback.add(post['id'], 'Use a specific owner.', 'Demo', 'creator', 'voice', post['body'], 'Name the next owner.')
        retry = feedback.add(post['id'], 'Use a specific owner.', 'Demo', 'creator', 'voice', post['body'], 'Name the next owner.')
        self.assertEqual(note, retry)
        with self.assertRaisesRegex(ValueError, 'match the current'):
            feedback.add(post['id'], 'Incorrect example', 'Demo', excerpt='This was never in the draft')
        self.engine.edit(post['id'], 'A revised sentence from the creator.')
        saved = feedback.list()[0]
        self.assertEqual(saved['content_snapshot'], post['body'])
        self.assertEqual(saved['content_revision'], 1)
        self.assertEqual(saved['content_sha256'], hashlib.sha256(post['body'].encode()).hexdigest())
        self.assertEqual(saved['excerpt'], post['body'])

    def test_future_task_feedback_and_explicit_pending_refresh(self):
        post = self.post()
        self.engine.select(self.ideas[1]['id'])
        task = self.pending(self.ideas[1]['id'])
        self.assertEqual(task['inputs']['creator_feedback'], [])
        feedback = Feedback(self.engine.store)
        note = feedback.add(post['id'], 'Avoid blanket claims on X.', 'Demo', 'platform', 'evidence')
        self.assertEqual(self.engine.store.get('tasks', task['id'])['inputs']['creator_feedback'], [])
        refreshed = self.engine.refresh_feedback(task['id'])
        self.assertEqual(refreshed['inputs']['creator_feedback'][0]['id'], note['id'])
        feedback.retire(note['id'], 'Creator replaced this preference.')
        self.assertEqual(self.engine.refresh_feedback(task['id'])['inputs']['creator_feedback'], [])
        self.engine.complete_task(task['id'], self.response(task))
        with self.assertRaisesRegex(ValueError, 'uncommitted pending'):
            self.engine.refresh_feedback(task['id'])
        self.engine.select(self.ideas[2]['id'], 'linkedin')
        feedback.add(post['id'], 'Keep the actual sequence of events.', 'Demo', 'creator', 'structure')
        next_task = self.pending(self.ideas[2]['id'])
        self.assertEqual(next_task['inputs']['creator_feedback'][0]['note'], 'Keep the actual sequence of events.')

    def test_feedback_budget_fails_without_forgetting_active_rules(self):
        post = self.post()
        feedback = Feedback(self.engine.store)
        feedback.add(post['id'], 'Specific direction. ' * 70, 'Demo', 'creator')
        self.configure(feedback={'max_context_chars': 256})
        self.engine.select(self.ideas[1]['id'])
        with self.assertRaisesRegex(ValueError, 'feedback exceeds'):
            self.engine.draft(self.ideas[1]['id'])
        self.assertEqual(len(feedback.list(status='ACTIVE')), 1)
        self.assertEqual(self.engine.store.get('ideas', self.ideas[1]['id'])['status'], 'SELECTED')

    def test_feedback_works_with_older_workspace_snapshot_and_survives_export(self):
        schema = self.engine.store.assets / 'schemas/creator-feedback.schema.json'
        schema.unlink()  # Simulate a workspace created by the previous release.
        post = self.post()
        note = Feedback(self.engine.store).add(post['id'], 'Prefer actual steps.', 'Demo', 'creator')
        self.assertFalse(schema.exists())
        with tempfile.TemporaryDirectory() as target:
            archive = Path(target) / 'workspace.zip'
            export_workspace(self.engine.store, archive)
            with zipfile.ZipFile(archive) as bundle:
                bundle.extractall(Path(target) / 'moved')
            moved = Store(Path(target) / 'moved')
            self.assertEqual(Feedback(moved).list()[0], note)
            self.assertEqual(Feedback(moved).context('tiktok')[0]['id'], note['id'])

    def test_cli_search_attach_and_feedback_roundtrip(self):
        source = self.capture_text('Creator: The backup owner checks the next action.\n')
        hit = self.cli('sources', 'search', 'backup owner', '--source', source['id'])['results'][0]
        read = self.cli('sources', 'read', source['id'], '--start-line', '1', '--end-line', '1')
        self.assertEqual(hit['quote'], read['quote'])
        self.cli('ideas', 'cite', self.ideas[0]['id'], '--source', source['id'],
                 '--start-line', '1', '--end-line', '1', '--quote', hit['quote'])
        post = self.post()
        note = self.cli('feedback', 'add', post['id'], '--note', 'Keep next actions concrete.',
                        '--by', 'Demo', '--scope', 'platform', '--category', 'voice')
        self.assertEqual(self.cli('feedback', 'list', '--content', post['id'])[0]['id'], note['id'])
        self.cli('feedback', 'retire', note['id'], '--reason', 'Changed preference.')
        self.assertEqual(self.cli('feedback', 'list', '--status', 'ACTIVE'), [])


if __name__ == '__main__':
    unittest.main()
