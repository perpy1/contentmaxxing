import json
import shutil
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock, patch

import yaml
from jsonschema import ValidationError

from contentmaxxing.analytics import winners
from contentmaxxing.compounding import needs_capture
from contentmaxxing.engine import Engine
from contentmaxxing.evaluation import Evaluation, prepare
from contentmaxxing.export import export_workspace
from contentmaxxing.overview import overview
from contentmaxxing.planning import Planning
from contentmaxxing.providers import PendingTask
from contentmaxxing.retrieval import validate_task_reference
from contentmaxxing.scheduler import Scheduler
from contentmaxxing.store import PACKAGE, atomic_text
from test_vertical import WorkspaceFixture
from editorial_helpers import plan_output


def compound_output(task):
    ref = task['inputs']['parent_content']['source_reference'][0]
    return {'assessment': 'The saves metric is above a matched median. Utility is a hypothesis, not a proven cause.',
        'opportunities': [
            {'topic': 'A reusable decision-context field for the next client handoff',
             'addition': 'utility', 'new_value': 'A question-and-decision pair to include in a handoff record.',
             'rationale': 'Develop the documented habit into a reusable action without claiming a measured outcome.',
             'platform': 'x', 'format': 'checklist', 'job': 'Bookmarks / Saves',
             'source_reference': [deepcopy(ref)], 'evidence_gaps': []},
            {'topic': 'What the team did when the assigned owner was absent',
             'addition': 'story', 'new_value': 'The actual fallback action and what happened after the owner was absent.',
             'rationale': 'The source establishes an ownership problem, but does not supply this missing episode.',
             'platform': 'tiktok', 'format': 'TikTok story', 'job': 'Trust',
             'source_reference': [deepcopy(ref)], 'evidence_gaps': ['Capture the real absent-owner episode and outcome.']}]}


class CompoundingTests(WorkspaceFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.posts = []
        for index in range(5):
            post = self.publish(self.post(index))
            self.posts.append(post)
            self.engine.manual_metrics(post['id'], {'impressions': 1000, 'bookmarks': 40 if index == 0 else 4})
        self.parent = self.posts[0]
        self.host = Engine(self.temp.name, provider_name='external')

    def pending(self, **kwargs):
        with self.assertRaises(PendingTask) as exc:
            self.host.compound(self.parent['id'], **kwargs)
        return self.host.store.get('tasks', exc.exception.task_id)

    def complete(self, task, output=None):
        return self.host.complete_task(task['id'], output if output is not None else compound_output(task))

    def test_measured_context_ready_and_capture_angles_are_persisted(self):
        task = self.pending()
        context = task['inputs']
        self.assertEqual(context['performance']['winner']['lift'], 10)
        self.assertEqual(context['performance']['winner']['peers'], 4)
        self.assertEqual(context['performance']['measurement']['metrics']['bookmarks'], 40)
        self.assertEqual(context['parent_content']['id'], self.parent['id'])
        self.assertTrue(context['creator']['VOICE.md'])
        self.assertNotEqual(context['formats']['x'], context['formats']['tiktok'])
        ideas = self.complete(task)
        self.assertEqual(len(ideas), 2)
        self.assertFalse(needs_capture(ideas[0])); self.assertTrue(needs_capture(ideas[1]))
        self.assertEqual(ideas[1]['best_platform'], 'tiktok')
        self.assertTrue(all(i['parent_content_id'] == self.parent['id'] and i['status'] == 'BACKLOG' for i in ideas))
        self.assertEqual(self.host.store.get('content', self.parent['id'])['status'], 'COMPOUND')
        self.assertEqual(len(self.host.store.list('content')), 5)

    def test_non_winner_rejected_before_task_creation(self):
        before = len(self.host.store.list('tasks'))
        with self.assertRaisesRegex(ValueError, 'Not a measured winner'):
            self.host.compound(self.posts[1]['id'])
        self.assertEqual(len(self.host.store.list('tasks')), before)

    def test_duplicate_and_invalid_follow_ups_do_not_partially_write(self):
        task = self.pending()
        good = compound_output(task)
        before = len(self.host.store.list('ideas'))
        cases = []
        for field, value in [('topic', self.parent['topic']), ('format', 'Substack Note'),
                             ('job', 'viral'), ('platform', 'instagram'), ('addition', 'hook'),
                             ('new_value', self.parent['body'])]:
            bad = deepcopy(good); bad['opportunities'][1][field] = value; cases.append(bad)
        bad = deepcopy(good); bad['opportunities'][1] = deepcopy(bad['opportunities'][0]); cases.append(bad)
        bad = deepcopy(good); bad['opportunities'][1]['topic'] = self.ideas[5]['topic']; cases.append(bad)
        bad = deepcopy(good); bad['opportunities'][1]['source_reference'][0]['quote'] = 'Never said this'; cases.append(bad)
        for bad in cases:
            with self.subTest(bad=bad):
                with self.assertRaises((ValueError, ValidationError)):
                    self.complete(task, bad)
                self.assertEqual(len(self.host.store.list('ideas')), before)
                self.assertEqual(self.host.store.get('tasks', task['id'])['status'], 'PENDING')
        self.complete(task)

    def test_same_format_hook_is_not_a_format_addition(self):
        task = self.pending()
        result = compound_output(task)
        result['opportunities'][0].update(addition='format', platform=self.parent['platform'], format=self.parent['format'])
        with self.assertRaisesRegex(ValueError, 'change the native container'):
            self.complete(task, result)
        result['opportunities'][0].update(platform='linkedin', format='LinkedIn post')
        self.assertEqual(self.complete(task, result)[0]['addition'], 'format')

    def test_only_creator_selected_platforms_can_receive_followups(self):
        path = self.host.store.data / 'creator/profile.json'
        profile = json.loads(path.read_text()); profile['platforms'] = ['linkedin']
        path.write_text(json.dumps(profile))
        task = self.pending()
        self.assertEqual(set(task['inputs']['formats']), {'linkedin'})
        with self.assertRaisesRegex(ValueError, 'creator-selected platform'):
            self.complete(task)
        output = compound_output(task); output['opportunities'] = output['opportunities'][:1]
        output['opportunities'][0].update(platform='linkedin', format='LinkedIn post')
        self.assertEqual(self.complete(task, output)[0]['best_platform'], 'linkedin')

    def test_new_native_container_can_preserve_original_topic(self):
        task = self.pending()
        output = compound_output(task)
        output['opportunities'] = output['opportunities'][:1]
        output['opportunities'][0].update(topic=self.parent['topic'], addition='format',
            platform='linkedin', format='LinkedIn post', new_value='Explain the business context and give a reusable decision log.')
        idea = self.complete(task, output)[0]
        self.assertEqual(idea['topic'], self.parent['topic'])
        self.assertNotEqual(idea['id'], self.parent['idea_id'])
        self.assertEqual(idea['parent_content_id'], self.parent['id'])
        another = self.pending(fresh=True)
        with self.assertRaisesRegex(ValueError, 'duplicates'):
            self.complete(another, output)

    def test_related_library_evidence_is_available_but_unseen_quotes_are_rejected(self):
        path = self.host.store.root / 'followup.txt'
        path.write_text('Morgan: The client handoff now has a backup owner when the assigned person is absent.\n')
        source = self.host.capture(path)
        task = self.pending(query='backup owner client handoff')
        self.assertIn(source['id'], task['inputs']['sources'])
        ref = {'source_id': source['id'], 'start_line': 1, 'end_line': 1, 'quote': path.read_text().strip()}
        output = compound_output(task)
        output['opportunities'][1].update(source_reference=[ref], evidence_gaps=[])
        late = self.host.store.root / 'late-evidence.txt'
        late.write_text('Morgan: A new observation after the task was saved.\n')
        new = self.host.capture(late)
        bad = deepcopy(output)
        bad['opportunities'][0]['source_reference'] = [{'source_id': new['id'], 'start_line': 1, 'end_line': 1, 'quote': late.read_text().strip()}]
        with self.assertRaisesRegex(ValueError, 'not supplied'):
            self.complete(task, bad)
        self.assertFalse(needs_capture(self.complete(task, output)[1]))

    def test_pending_and_completed_reuse_frozen_evidence_without_duplicate_learning(self):
        task = self.pending()
        self.assertEqual(self.pending()['id'], task['id'])
        with self.assertRaisesRegex(ValueError, 'pending compound task'):
            self.host.compound(self.parent['id'], fresh=True)
        ideas = self.complete(task)
        learning = self.host.store.data / 'creator/LEARNINGS.md'
        before = learning.read_bytes()
        self.engine.manual_metrics(self.parent['id'], {'impressions': 1000, 'bookmarks': 1})
        self.assertFalse(winners(self.host.store))
        self.assertEqual([i['id'] for i in self.host.compound(self.parent['id'])], [i['id'] for i in ideas])
        self.assertEqual([i['id'] for i in self.complete(task, {})], [i['id'] for i in ideas])
        self.assertEqual(learning.read_bytes(), before)

    def test_explicit_compound_citation_preserves_prior_context_and_frozen_measurement(self):
        task = self.pending()
        path = self.host.store.root / 'late-evidence.txt'
        path.write_text('Morgan: We recorded the named backup accepting the handoff on the same log.\n')
        source = self.host.capture(path)
        ref = {'source_id': source['id'], 'start_line': 1, 'end_line': 1, 'quote': path.read_text().strip()}
        output = compound_output(task)
        output['opportunities'][1].update(source_reference=[ref], evidence_gaps=[])
        with self.assertRaisesRegex(ValueError, 'not supplied'):
            self.complete(task, output)
        self.engine.manual_metrics(self.parent['id'], {'impressions': 1000, 'bookmarks': 1})
        parent_before = self.host.store.get('content', self.parent['id'])
        enriched = self.host.cite_task(task['id'], **ref)
        for key in set(task['inputs']) - {'sources', 'source_metadata', 'source_context'}:
            self.assertEqual(enriched['inputs'][key], task['inputs'][key], key)
        self.assertEqual(enriched['inputs']['performance']['winner']['lift'], 10)
        self.assertEqual(enriched['inputs']['extra_source_reference'], [ref])
        self.assertEqual(self.host.cite_task(task['id'], **ref), enriched)
        for passages in task['inputs']['sources'].values():
            for passage in passages:
                validate_task_reference(enriched['inputs'], {k: passage[k] for k in ref})
        validate_task_reference(enriched['inputs'], ref)
        self.assertEqual(self.host.store.get('content', self.parent['id']), parent_before)
        self.assertEqual(self.pending()['id'], task['id'])
        self.assertFalse(needs_capture(self.complete(enriched, output)[1]))

    def test_compound_citation_budget_and_bad_quote_leave_snapshot_unchanged(self):
        task = self.pending()
        before = self.host.store.path('tasks', task['id']).read_bytes()
        with self.assertRaises(ValueError):
            self.host.cite_task(task['id'], self.source['id'], 1, 1, 'Invented')
        path = self.host.store.root / 'oversized-evidence.txt'
        path.write_text('Complete evidence ' * 2000)
        source = self.host.capture(path)
        with self.assertRaisesRegex(ValueError, 'budget'):
            self.host.cite_task(task['id'], source['id'], 1, 1, path.read_text())
        self.assertEqual(self.host.store.path('tasks', task['id']).read_bytes(), before)
        original = task['inputs']['parent_content']['source_reference'][0]
        subset = {**original, 'quote': original['quote'][:20]}
        enriched = self.host.cite_task(task['id'], **subset)
        passages = [p for values in enriched['inputs']['sources'].values() for p in values]
        self.assertEqual(enriched['inputs']['source_context']['returned_chars'], sum(len(p['quote']) for p in passages))
        self.assertLessEqual(sum(len(p['quote']) for p in passages), enriched['inputs']['source_context']['max_chars'])
        for index, passage in enumerate(passages):
            for other in passages[index + 1:]:
                if other['source_id'] == passage['source_id']:
                    self.assertFalse(max(passage['start_offset'], other['start_offset']) < min(passage['end_offset'], other['end_offset']))

    def test_compound_citation_rejects_prepared_completed_and_cancelled_tasks(self):
        task = self.pending()
        ref = task['inputs']['parent_content']['source_reference'][0]
        put = self.host.store.put
        def interrupt(collection, value):
            if collection == 'ideas':
                raise OSError('Interrupted after preparation')
            return put(collection, value)
        with patch.object(self.host.store, 'put', side_effect=interrupt):
            with self.assertRaises(OSError):
                self.complete(task)
        with self.assertRaisesRegex(ValueError, 'uncommitted pending'):
            self.host.cite_task(task['id'], **ref)
        self.complete(task)
        with self.assertRaisesRegex(ValueError, 'uncommitted pending'):
            self.host.cite_task(task['id'], **ref)
        another = self.pending(fresh=True)
        self.host.cancel_task(another['id'], 'Fictional reviewer stops this pass.')
        with self.assertRaisesRegex(ValueError, 'uncommitted pending'):
            self.host.cite_task(another['id'], **ref)

    def test_attached_compound_evidence_survives_export_and_completion(self):
        task = self.pending()
        path = self.host.store.root / 'captured-answer.txt'
        path.write_text('Morgan: The backup owner accepted the request and recorded the next action.\n')
        source = self.host.capture(path)
        ref = {'source_id': source['id'], 'start_line': 1, 'end_line': 1, 'quote': path.read_text().strip()}
        enriched = self.host.cite_task(task['id'], **ref)
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / 'portable.zip'
            export_workspace(self.host.store, archive)
            destination = Path(folder) / 'restored'; shutil.unpack_archive(str(archive), str(destination))
            restored = Engine(destination, provider_name='external')
            self.assertEqual(restored.store.get('tasks', task['id'])['inputs'], enriched['inputs'])
            output = compound_output(enriched)
            output['opportunities'][1].update(source_reference=[ref], evidence_gaps=[])
            ideas = restored.complete_task(task['id'], output)
            self.assertEqual(ideas[1]['source_reference'], [ref])
            self.assertFalse(needs_capture(ideas[1]))

    def test_new_pass_includes_existing_angles_and_does_not_overwrite_them(self):
        task = self.pending(); first = self.complete(task)
        second = self.pending(fresh=True)
        self.assertEqual(len(second['inputs']['existing_follow_ups']), 2)
        saved = second['inputs']['existing_follow_ups'][1]
        self.assertEqual(saved['best_platform'], 'tiktok')
        self.assertEqual(saved['format'], 'TikTok story')
        self.assertTrue(saved['needs_capture'])
        with self.assertRaisesRegex(ValueError, 'duplicates'):
            self.complete(second)
        self.assertEqual(self.host.store.get('ideas', first[0]['id']), first[0])
        self.complete(second, {'assessment': 'No useful unused angle in the supplied evidence.', 'opportunities': []})
        self.assertEqual(self.host.compound(self.parent['id']), [])

    def test_gap_blocks_drafting_then_cited_resolution_unlocks_same_idea(self):
        task = self.pending(); idea = self.complete(task)[1]
        self.host.select(idea['id'], platform='tiktok', format_name='TikTok story', job='Trust')
        with self.assertRaisesRegex(ValueError, 'needs captured evidence'):
            self.host.draft(idea['id'])
        path = self.host.store.root / 'owner-story.txt'
        path.write_text('Morgan: When the owner was absent, we assigned a backup and the request moved that morning.\n')
        source = self.host.capture(path)
        ref = {'source_id': source['id'], 'quote': path.read_text().strip(), 'start_line': 1, 'end_line': 1}
        supplied = {'resolutions': [{'gap': 1, 'note': 'The creator documented the missing episode.', 'source_reference': [ref]}]}
        resolved = self.host.resolve_idea(idea['id'], supplied)
        self.assertFalse(needs_capture(resolved))
        self.assertEqual(resolved['id'], idea['id'])
        before = self.host.store.path('ideas', idea['id']).read_bytes()
        self.host.resolve_idea(idea['id'], supplied)
        self.assertEqual(self.host.store.path('ideas', idea['id']).read_bytes(), before)
        with self.assertRaises(PendingTask) as exc:
            self.host.draft(idea['id'])
        writing = self.host.store.get('tasks', exc.exception.task_id)
        self.assertIn(source['id'], writing['inputs']['sources'])
        self.assertEqual(writing['inputs']['parent_content']['id'], self.parent['id'])
        self.assertEqual(writing['inputs']['idea']['development']['new_value'], idea['follow_up_angle'])

    def test_gap_resolution_validates_all_before_writing_and_preserves_existing(self):
        idea = self.complete(self.pending())[1]
        ref = deepcopy(idea['source_reference'][0])
        before = self.host.store.path('ideas', idea['id']).read_bytes()
        with self.assertRaisesRegex(ValueError, 'existing development gap'):
            self.host.resolve_idea(idea['id'], {'resolutions': [
                {'gap': 1, 'note': 'Evidence', 'source_reference': [ref]},
                {'gap': 2, 'note': 'Not a real gap', 'source_reference': [ref]}]})
        self.assertEqual(self.host.store.path('ideas', idea['id']).read_bytes(), before)
        ref['quote'] = 'Invented source'
        with self.assertRaises(ValueError):
            self.host.resolve_idea(idea['id'], {'resolutions': [{'gap': 1, 'note': 'Evidence', 'source_reference': [ref]}]})
        self.assertEqual(self.host.store.path('ideas', idea['id']).read_bytes(), before)

    def test_planning_rejects_unresolved_gap_and_offline_mix_excludes_it(self):
        idea = self.complete(self.pending())[1]
        self.host.select(idea['id'], platform='tiktok', format_name='TikTok story', job='Trust')
        cfg = Scheduler(self.host).config(); cfg['counts'] = {'tiktok': 1}
        atomic_text(self.host.store.root / 'workflows.yaml', yaml.safe_dump(cfg))
        with self.assertRaises(PendingTask) as exc:
            Planning(self.host).plan()
        task = self.host.store.get('tasks', exc.exception.task_id)
        self.assertEqual(task['inputs']['candidates'][0]['id'], idea['id'])
        with self.assertRaisesRegex(ValueError, 'needs captured evidence'):
            self.host.complete_task(task['id'], plan_output(task))
        heuristic = Planning(self.engine).plan()
        self.assertNotIn(idea['id'], [s['idea_id'] for stage in heuristic['stages'] for s in stage['slots']])

    def test_partial_import_recovers_ids_and_preserves_intervening_edits(self):
        task = self.pending()
        put = self.host.store.put
        count = 0
        def interrupt(collection, value):
            nonlocal count
            if collection == 'ideas':
                count += 1
                if count == 2:
                    raise OSError('Crash during compound import')
            return put(collection, value)
        with patch.object(self.host.store, 'put', side_effect=interrupt):
            with self.assertRaises(OSError):
                self.complete(task)
        prepared = self.host.store.get('tasks', task['id'])['prepared_compound']['ideas']
        first = self.host.store.get('ideas', prepared[0]['id'])
        first['notes'] = 'Creator edited this after the interruption.'
        self.host.store.put('ideas', first)
        recovered = self.host.compound(self.parent['id'])
        self.assertEqual([i['id'] for i in recovered], [i['id'] for i in prepared])
        self.assertEqual(recovered[0]['notes'], first['notes'])
        self.assertEqual(len([i for i in self.host.store.list('ideas') if i['parent_content_id'] == self.parent['id']]), 2)

    def test_no_opportunities_is_a_completed_assessment_not_endless_navigation(self):
        task = self.pending()
        self.assertEqual(overview(self.temp.name)['next_action']['command'], 'compound')
        self.complete(task, {'assessment': 'Capture something new; a hook rewrite adds no utility.', 'opportunities': []})
        self.assertNotEqual(overview(self.temp.name)['next_action']['command'], 'compound')

    def test_weekly_winner_watch_waits_then_resumes_same_compound_task(self):
        scheduler = Scheduler(self.host)
        run = scheduler.run('winner_compound_watch')
        stage = run['stages'][1]
        self.assertEqual(run['status'], 'WAITING')
        self.assertEqual(stage['status'], 'WAITING')
        task = self.host.store.get('tasks', stage['tasks'][self.parent['id']])
        count = len(self.host.store.list('tasks'))
        scheduler.run('winner_compound_watch', run['id'])
        self.assertEqual(len(self.host.store.list('tasks')), count)
        ideas = self.complete(task)
        done = scheduler.run('winner_compound_watch', run['id'])
        self.assertEqual(done['status'], 'COMPLETED')
        self.assertEqual(set(done['stages'][1]['results']), {i['id'] for i in ideas})

    def test_internal_failure_can_be_completed_externally_without_retry(self):
        provider = Mock(); provider.analyze.side_effect = ValueError('Provider unavailable')
        host = Engine(self.temp.name, provider=provider, provider_name='openai-compatible')
        scheduler = Scheduler(host)
        run = scheduler.run('winner_compound_watch')
        task = host.store.get('tasks', run['stages'][1]['tasks'][self.parent['id']])
        scheduler.run('winner_compound_watch', run['id'])
        provider.analyze.assert_called_once(); provider.generate.assert_not_called()
        host.complete_task(task['id'], compound_output(task))
        self.assertEqual(scheduler.run('winner_compound_watch', run['id'])['status'], 'COMPLETED')

    def test_export_and_legacy_schema_preserve_pending_compound_and_resolutions(self):
        schema_path = self.host.store.assets / 'schemas/idea.schema.json'
        schema = json.loads(schema_path.read_text()); schema['properties'].pop('development')
        schema_path.write_text(json.dumps(schema)); original = schema_path.read_bytes()
        task = self.pending()
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / 'portable.zip'
            export_workspace(self.host.store, archive)
            destination = Path(folder) / 'restored'; shutil.unpack_archive(str(archive), str(destination))
            restored = Engine(destination, provider_name='external')
            ideas = restored.complete_task(task['id'], compound_output(task))
            self.assertTrue(needs_capture(ideas[1]))
            self.assertEqual((restored.store.assets / 'schemas/idea.schema.json').read_bytes(), original)
            for name in ('VOICE.md', 'BRAND_BRAIN.md', 'CONTENT_PILLARS.md', 'OFFER.md'):
                self.assertEqual(restored.store.brain()[name], self.host.store.brain()[name])
            self.assertIn(task['id'], restored.store.brain()['LEARNINGS.md'])

    def test_archiving_parent_during_pending_analysis_prevents_new_derivatives(self):
        task = self.pending()
        self.engine.transition(self.parent['id'], 'ARCHIVED')
        with self.assertRaisesRegex(ValueError, 'no longer active'):
            self.complete(task)
        self.assertFalse(any(i['parent_content_id'] for i in self.host.store.list('ideas')))

    def test_compound_evaluation_uses_real_winner_and_requires_human_judgment(self):
        root = self.host.store.root / 'compound-evaluation'
        prepare(root, 'fixture', PACKAGE / 'evals/compounding-v1.json')
        task = json.loads((root / 'cases/develop-winner/packet.json').read_text())['task']
        self.assertEqual(task['inputs']['performance']['winner']['lift'], 10)
        evaluation = Evaluation(root)
        report = evaluation.submit('develop-winner', compound_output(task))
        self.assertEqual(report['summary'], {'NEEDS_HUMAN_REVIEW': 1})
        self.assertEqual(report['cases'][0]['attempts'][0]['human'], 'PENDING')
        checks = {c['id']: c['status'] for c in report['cases'][0]['attempts'][0]['checks']}
        self.assertEqual(checks['repeat_import'], 'PASS')
        self.assertEqual(checks['no_automatic_drafts'], 'PASS')

    def test_cancelled_analysis_is_not_restarted_by_winner_watch(self):
        scheduler = Scheduler(self.host)
        run = scheduler.run('winner_compound_watch')
        task_id = run['stages'][1]['tasks'][self.parent['id']]
        self.host.cancel_task(task_id, 'Creator wants to leave this topic for now.')
        with self.assertRaisesRegex(ValueError, 'cancelled'):
            self.host.complete_task(task_id, {})
        done = scheduler.run('winner_compound_watch', run['id'])
        self.assertEqual(done['status'], 'COMPLETED')
        self.assertIn(self.parent['id'], done['stages'][1]['skipped'])
        with self.assertRaisesRegex(ValueError, 'Use --new'):
            self.host.compound(self.parent['id'])
        self.assertNotEqual(self.pending(fresh=True)['id'], task_id)

    def test_cancel_partial_import_preserves_committed_ideas_only(self):
        task = self.pending()
        original = self.host.store.put
        written = []
        def interrupt(collection, value):
            if collection == 'ideas':
                if written:
                    raise OSError('Interrupted second idea')
                written.append(value['id'])
            return original(collection, value)
        with patch.object(self.host.store, 'put', side_effect=interrupt):
            with self.assertRaises(OSError):
                self.complete(task)
        cancelled = self.host.cancel_task(task['id'], 'Keep the first idea and stop this analysis.')
        self.assertEqual(cancelled['status'], 'CANCELLED')
        self.assertEqual(cancelled['result_ids'], written)
        self.assertEqual(len([i for i in self.host.store.list('ideas') if i['parent_content_id'] == self.parent['id']]), 1)
        with self.assertRaisesRegex(ValueError, 'cancelled'):
            self.complete(task)

    def test_cancel_reconciles_already_committed_import_without_duplicate_learning(self):
        task = self.pending()
        original = self.host.store.put
        def interrupt(collection, value):
            if collection == 'tasks' and value['operation'] == 'compound' and value['status'] == 'COMPLETED':
                raise OSError('Interrupted task checkpoint')
            return original(collection, value)
        with patch.object(self.host.store, 'put', side_effect=interrupt):
            with self.assertRaises(OSError):
                self.complete(task)
        path = self.host.store.data / 'creator/LEARNINGS.md'
        before = path.read_bytes()
        recovered = self.host.cancel_task(task['id'], 'Stop if this has not already committed.')
        self.assertEqual(recovered['status'], 'COMPLETED')
        self.assertEqual(len(recovered['result_ids']), 2)
        self.assertEqual(path.read_bytes(), before)
