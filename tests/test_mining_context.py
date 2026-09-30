import copy
import json
import zipfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from contentmaxxing.engine import Engine
from contentmaxxing.export import export_workspace
from contentmaxxing.mining import existing_idea_context, latest
from contentmaxxing.providers import ExtractiveProvider, PendingTask
from contentmaxxing.store import atomic_text
from test_vertical import WorkspaceFixture


class MiningContextTests(WorkspaceFixture, unittest.TestCase):
    def capture_source(self, text, name='followup.txt'):
        path = Path(self.temp.name) / name
        path.write_text(text)
        return self.engine.capture(path, consent='fictional')

    def pending(self, source):
        engine = Engine(self.temp.name, provider_name='external')
        with self.assertRaises(PendingTask) as raised:
            engine.mine(source['id'])
        return engine.store.get('tasks', raised.exception.task_id)

    def attachment(self, task, target=None):
        target = target or task['inputs']['existing_ideas'][0]
        window = task['inputs'].get('source_window', {})
        return {'topic': target['topic'], 'category': 'source addition', 'existing_idea_id': target['id'],
                'quote': task['inputs']['text'].splitlines()[0],
                'start_line': window.get('start_line', 1), 'end_line': window.get('start_line', 1),
                'notes': 'A source-backed restatement; preserve the original editorial choices.'}

    def state(self):
        return {p.relative_to(self.engine.store.data).as_posix(): p.read_bytes()
                for p in self.engine.store.data.rglob('*') if p.is_file()}

    def test_stateless_provider_reuses_prior_window_topic_and_keeps_both_citations(self):
        config = self.engine.store.config
        config['mining'] = {'chunk_chars': 512, 'overlap_chars': 0, 'chunks_per_call': 2}
        atomic_text(self.engine.store.root / 'config.yaml', yaml.safe_dump(config))
        source = self.capture_source('Morgan: Assign a destination to each prepared tray.\n' +
                             'Moderator: ' + 'pause ' * 65 + '\n' +
                             'Morgan: Counting prepared portions does not tell the helper where to put them. The tray needs a destination before the next setup starts.\n')
        seen = []

        class Provider(ExtractiveProvider):
            def extract(self, task):
                seen.append(copy.deepcopy(task))
                if task['inputs']['source_window']['index'] == 1:
                    return {'ideas': [{'topic': 'Tray destination versus inventory count', 'category': 'process',
                                      'quote': task['inputs']['text'].splitlines()[0], 'start_line': 1, 'end_line': 1}]}
                target = next(i for i in task['inputs']['existing_ideas'] if i['topic'] == 'Tray destination versus inventory count')
                return {'ideas': [{'topic': target['topic'], 'existing_idea_id': target['id'], 'category': 'restatement',
                                  'quote': task['inputs']['text'].splitlines()[0], 'start_line': 3, 'end_line': 3}]}

        result = Engine(self.temp.name, provider=Provider()).mine(source['id'])
        self.assertEqual(len(seen), 2)
        self.assertEqual(len(result), 1)
        self.assertEqual([r['start_line'] for r in result[0]['source_reference']], [1, 3])
        self.assertEqual(result[0]['format'], None)
        self.assertEqual(result[0]['status'], 'BACKLOG')
        self.assertEqual(seen[1]['inputs']['existing_idea_context']['omitted'], 0)
        task = self.engine.store.get('tasks', seen[1]['id'])
        self.assertEqual(task['extraction_output']['ideas'][0]['existing_idea_id'], result[0]['id'])

    def test_context_budget_omissions_and_frozen_pending_packet(self):
        context = existing_idea_context(self.engine.store, self.source['id'], self.engine.store.source_text(self.source['id']), 450)
        encoded = json.dumps(context['existing_ideas'], ensure_ascii=False, separators=(',', ':'))
        self.assertLessEqual(len(encoded), 450)
        self.assertEqual(len(encoded), context['existing_idea_context']['returned_chars'])
        self.assertGreater(context['existing_idea_context']['omitted'], 0)
        self.assertEqual(len(context['existing_ideas']) + context['existing_idea_context']['omitted'], 6)
        self.assertEqual(existing_idea_context(self.engine.store, self.source['id'], 'request', 0)['existing_ideas'], [])
        task = self.pending(self.source)
        target = self.engine.store.get('ideas', task['inputs']['existing_ideas'][0]['id'])
        target['topic'] += ' — edited later'
        self.engine.store.put('ideas', target)
        self.assertEqual(self.pending(self.source), task)

    def test_attachment_preserves_selected_metadata_and_does_not_promote_new_notes(self):
        task = self.pending(self.source)
        target = task['inputs']['existing_ideas'][0]
        self.engine.select(target['id'], format_name='checklist', job='Bookmarks / Saves')
        original = self.engine.store.get('ideas', target['id'])
        candidate = self.attachment(task, target)
        candidate.update(priority=100, article_candidate=True, proof=['Model interpretation for review.'])
        imported = self.engine.complete_task(task['id'], {'ideas': [candidate]})[0]
        for name, value in original.items():
            if name not in ('source_reference', 'updated_at'):
                self.assertEqual(imported[name], value, name)
        self.assertEqual(self.engine.store.get('tasks', task['id'])['extraction_output'], {'ideas': [candidate]})

    def test_unknown_target_and_wrong_topic_reject_before_any_record_write(self):
        task = self.pending(self.source)
        first = {'topic': 'A separate draftable source topic', 'category': 'process',
                 'quote': task['inputs']['text'].splitlines()[0], 'start_line': 1, 'end_line': 1}
        for key, value in [('existing_idea_id', 'idea_f00000000000'), ('topic', 'Changed target meaning')]:
            candidate = self.attachment(task)
            candidate[key] = value
            before = self.state()
            with self.assertRaises(ValueError):
                self.engine.complete_task(task['id'], {'ideas': [first, candidate]})
            self.assertEqual(self.state(), before)

    def test_notes_are_bounded_and_changed_interpretation_invalidates_unapplied_match(self):
        current = self.engine.store.get('ideas', self.ideas[1]['id'])
        current['notes'] = 'A specific prior interpretation. ' * 50
        self.engine.store.put('ideas', current)
        task = self.pending(self.source)
        target = next(i for i in task['inputs']['existing_ideas'] if i['id'] == current['id'])
        self.assertEqual(len(target['notes']), 600)
        self.assertTrue(target['notes_truncated'])
        candidate = self.attachment(task, target)
        current['notes'] = 'The creator corrected this interpretation after the task was prepared.'
        self.engine.store.put('ideas', current)
        before = self.state()
        with self.assertRaisesRegex(ValueError, 'changed since mining'):
            self.engine.complete_task(task['id'], {'ideas': [candidate]})
        self.assertEqual(self.state(), before)

    def test_changed_target_and_new_pending_draft_do_not_get_overwritten(self):
        task = self.pending(self.source)
        candidate = self.attachment(task)
        current = self.engine.store.get('ideas', candidate['existing_idea_id'])
        # Ensure the incoming citation is new to the chosen target.
        other = next(i for i in task['inputs']['existing_ideas'] if i['id'] != self.ideas[0]['id'])
        candidate = self.attachment(task, other)
        current = self.engine.store.get('ideas', other['id'])
        old_topic = current['topic']
        current['topic'] = 'The creator renamed this topic.'
        self.engine.store.put('ideas', current)
        before = self.state()
        with self.assertRaisesRegex(ValueError, 'changed since mining'):
            self.engine.complete_task(task['id'], {'ideas': [candidate]})
        self.assertEqual(self.state(), before)
        current['topic'] = old_topic
        self.engine.store.put('ideas', current)
        self.engine.select(current['id'])
        with self.assertRaises(PendingTask):
            Engine(self.temp.name, provider_name='external').draft(current['id'])
        before = self.state()
        with self.assertRaisesRegex(ValueError, 'draft task already snapshots'):
            self.engine.complete_task(task['id'], {'ideas': [candidate]})
        self.assertEqual(self.state(), before)

    def test_recovery_of_committed_attachment_keeps_later_renaming_and_notes(self):
        task = self.pending(self.source)
        target = next(i for i in task['inputs']['existing_ideas'] if i['id'] != self.ideas[0]['id'])
        candidate = self.attachment(task, target)
        put = self.engine.store.put
        def fail_checkpoint(collection, value):
            if collection == 'tasks' and value['status'] == 'COMPLETED':
                raise OSError('checkpoint failed')
            return put(collection, value)
        with patch.object(self.engine.store, 'put', side_effect=fail_checkpoint):
            with self.assertRaisesRegex(OSError, 'checkpoint failed'):
                self.engine.complete_task(task['id'], {'ideas': [candidate]})
        current = self.engine.store.get('ideas', target['id'])
        current.update(topic='Creator renamed after attachment', notes='Preserve this newer note.')
        put('ideas', current)
        before = self.engine.store.get('ideas', target['id'])
        result = self.engine.complete_task(task['id'], {'ideas': [candidate]})[0]
        self.assertEqual(result, before)
        self.assertEqual(len(result['source_reference']), 2)
        self.assertEqual(self.engine.complete_task(task['id'], {'ideas': [candidate]})[0], before)

    def test_context_excludes_archived_compound_and_pending_draft_targets(self):
        first = self.engine.store.get('ideas', self.ideas[0]['id'])
        first['status'] = 'ARCHIVED'
        self.engine.store.put('ideas', first)
        second = self.engine.store.get('ideas', self.ideas[1]['id'])
        second['parent_content_id'] = 'post_f00000000000'
        self.engine.store.put('ideas', second)
        self.engine.select(self.ideas[2]['id'])
        with self.assertRaises(PendingTask):
            Engine(self.temp.name, provider_name='external').draft(self.ideas[2]['id'])
        ids = {i['id'] for i in self.pending(self.source)['inputs']['existing_ideas']}
        self.assertTrue(ids.isdisjoint({i['id'] for i in self.ideas[:3]}))
        self.assertEqual(ids, {i['id'] for i in self.ideas[3:]})

    def test_exported_pending_context_completes_against_the_same_idea_ids(self):
        task = self.pending(self.source)
        target = next(i for i in task['inputs']['existing_ideas'] if i['id'] != self.ideas[0]['id'])
        candidate = self.attachment(task, target)
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / 'creator.zip'
            export_workspace(self.engine.store, archive)
            moved = Path(folder) / 'moved'
            with zipfile.ZipFile(archive) as zf:
                zf.extractall(moved)
            engine = Engine(moved, provider_name='external')
            self.assertEqual(engine.store.get('tasks', task['id']), task)
            before = len(engine.store.list('ideas'))
            result = engine.complete_task(task['id'], {'ideas': [candidate]})[0]
            self.assertEqual(result['id'], target['id'])
            self.assertEqual(len(engine.store.list('ideas')), before)
            self.assertEqual(len(result['source_reference']), 2)

    def test_legacy_pass_keeps_its_original_contract_and_does_not_receive_new_context(self):
        config = self.engine.store.config
        config['mining'] = {'chunk_chars': 512, 'overlap_chars': 0, 'chunks_per_call': 1}
        atomic_text(self.engine.store.root / 'config.yaml', yaml.safe_dump(config))
        source = self.capture_source('Morgan: A source statement for the first window.\n' * 25)
        first = self.pending(source)
        self.engine.complete_task(first['id'], {'ideas': []})
        run = latest(self.engine.store, source['id'])
        run['settings'].pop('idea_context_chars')
        run['template']['output_contract']['properties']['ideas']['items']['properties'].pop('existing_idea_id')
        run['template']['instructions'] = 'Historical frozen skill instructions.'
        self.engine.store.put('mining', run)
        second = self.pending(source)
        self.assertEqual(second['instructions'], 'Historical frozen skill instructions.')
        self.assertNotIn('existing_ideas', second['inputs'])
        self.assertNotIn('existing_idea_id', second['output_contract']['properties']['ideas']['items']['properties'])
