import json
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch

import yaml

from contentmaxxing.cli import main
from contentmaxxing.engine import Engine
from contentmaxxing.export import export_workspace
from contentmaxxing.feedback import Feedback
from contentmaxxing.overview import overview
from contentmaxxing.providers import PendingTask, OpenAICompatibleProvider
from contentmaxxing.store import Store, atomic_json, atomic_text
from contentmaxxing.voice import OPEN, Voice, read_text


def answer(task):
    samples = task['inputs']['samples']
    return {'summary': 'Fictional sample analysis; editorial usefulness still needs creator judgment.',
        'observations': [{'dimension': 'syntax', 'pattern': 'Starts with a concrete action and explains the failure it prevents.',
            'guidance': 'Lead with the actual action. Keep the explanation attached to that action.',
            'certainty': 'tentative', 'platform': samples[0]['platform'], 'medium': samples[0]['medium'],
            'evidence': [{'sample_id': samples[0]['id'], 'quote': samples[0]['text']}]}],
        'unknowns': ['Humor and preferred CTA need more samples.'], 'conflicts': []}


class VoiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'creator'
        Store(self.root).init()
        self.engine = Engine(self.root)
        self.profile = json.loads((Path(__file__).parent / 'fixtures/creator.json').read_text())
        self.profile['writing_samples'].append('Name the reviewer before sending the draft. A shared inbox is not an owner.')
        self.engine.onboard(self.profile)
        self.voice = Voice(self.engine)

    def tearDown(self):
        self.temp.cleanup()

    def pending(self, **kwargs):
        with self.assertRaises(PendingTask) as exc:
            self.voice.request(**kwargs)
        return self.engine.store.get('tasks', exc.exception.task_id)

    def complete(self, task=None):
        task = task or self.pending()
        return self.engine.complete_task(task['id'], answer(task))[0]

    def cli(self, *args):
        stream = StringIO()
        with redirect_stdout(stream):
            code = main(['--workspace', str(self.root), *args])
        self.assertEqual(code, 0, stream.getvalue())
        return json.loads(stream.getvalue())

    def configure(self, value):
        config = self.engine.store.config
        config['voice'].update(value)
        atomic_text(self.root / 'config.yaml', yaml.safe_dump(config))

    def captured(self, text='Morgan: Name the owner before the handoff.', medium='speech', platform=None):
        path = Path(self.temp.name) / 'sample.txt'
        path.write_text(text)
        source = self.engine.capture(path)
        return {'source_reference': {'source_id': source['id'], 'start_line': 1, 'end_line': 1, 'quote': text},
                'platform': platform, 'medium': medium, 'attribution': 'creator', 'speaker': 'Morgan'}

    def test_proposal_then_apply_loads_into_new_writing_tasks_and_preserves_manual_text(self):
        manual = '# My voice\r\n\r\nNo urgency CTAs. Keep sentence case.\r\n'
        atomic_text(self.voice.document, manual)
        task = self.pending()
        self.assertEqual(overview(self.root)['next_action']['command'], 'voice')
        self.assertEqual(overview(self.root)['next_action']['arguments']['task_id'], task['id'])
        proposal = self.complete(task)
        self.assertEqual(read_text(self.voice.document), manual)
        self.assertEqual(overview(self.root)['next_action']['arguments']['proposal_ids'], [proposal['id']])
        self.assertTrue(self.voice.path(proposal['id']).with_suffix('.md').exists())
        applied = self.voice.apply(proposal['id'])
        self.assertEqual(applied['status'], 'APPLIED')
        self.assertTrue(read_text(self.voice.document).startswith(manual))
        sample = self.captured()
        source_id = sample['source_reference']['source_id']
        idea = self.engine.persist_idea(self.engine.idea_from({'topic': 'Ownership before handoff', 'category': 'process',
            **{k: sample['source_reference'][k] for k in ('quote', 'start_line', 'end_line')}}, source_id, 'external'))
        self.engine.select(idea['id'])
        with self.assertRaises(PendingTask) as exc:
            self.engine.draft(idea['id'])
        writing_task = self.engine.store.get('tasks', exc.exception.task_id)
        self.assertIn(proposal['block'], writing_task['inputs']['creator']['VOICE.md'])
        self.assertEqual(writing_task['status'], 'PENDING')

    def test_invalid_evidence_scope_medium_and_recurrence_do_not_commit(self):
        task = self.pending()
        for field, value, error in [('evidence', [{'sample_id': 'missing', 'quote': 'invented'}], 'exact supplied'),
                                    ('medium', 'speech', 'speech evidence'),
                                    ('platform', 'x', 'platform observation'),
                                    ('certainty', 'recurring', 'independent samples')]:
            with self.subTest(field=field):
                output = answer(task)
                output['observations'][0][field] = value
                with self.assertRaisesRegex(ValueError, error):
                    self.engine.complete_task(task['id'], output)
                self.assertEqual(self.voice.list(), [])
                self.assertEqual(self.engine.store.get('tasks', task['id'])['status'], 'PENDING')
        output = answer(task)
        output['observations'][0]['certainty'] = 'recurring'
        output['observations'][0]['evidence'].append({'sample_id': task['inputs']['samples'][1]['id'],
                                                    'quote': task['inputs']['samples'][1]['text']})
        self.assertEqual(self.engine.complete_task(task['id'], output)[0]['status'], 'PROPOSED')

    def test_reference_creators_links_duplicates_and_omitted_samples_are_not_evidence(self):
        profile = deepcopy(self.profile)
        profile['reference_creators'] = ['COMPETITOR VOICE SHOULD NOT LEAK']
        profile['writing_samples'] += [profile['writing_samples'][0], 'https://example.com/post', '[Article](https://example.com/article)']
        atomic_json(self.root / 'data/creator/profile.json', profile)
        # The manually maintained document is direction, not source evidence.
        self.configure({'max_samples': 1})
        task = self.pending()
        inputs = task['inputs']
        self.assertEqual(len(inputs['samples']), 1)
        self.assertEqual(len(inputs['coverage']['omitted']), 4)
        self.assertNotIn('COMPETITOR VOICE SHOULD NOT LEAK', json.dumps(inputs))
        self.assertEqual(inputs['samples'][0]['text'], self.profile['writing_samples'][0])
        output = answer(task)
        output['observations'][0]['evidence'][0]['sample_id'] = 'profile:writing_samples:1'
        with self.assertRaisesRegex(ValueError, 'exact supplied'):
            self.engine.complete_task(task['id'], output)

    def test_no_samples_keeps_voice_provisional_and_creates_no_task(self):
        profile = deepcopy(self.profile)
        profile['writing_samples'] = ['https://example.com/post']
        profile['desired_tone'] = 'Be loud and funny'
        atomic_json(self.root / 'data/creator/profile.json', profile)
        before = self.voice.document.read_bytes()
        self.assertEqual(self.voice.request()['status'], 'NEEDS_SAMPLES')
        self.assertEqual(self.engine.store.list('tasks'), [])
        self.assertEqual(self.voice.document.read_bytes(), before)
        self.assertNotEqual(overview(self.root)['stage'], 'VOICE')

    def test_captured_samples_require_exact_quotes_and_explicit_speaker(self):
        sample = self.captured(platform='x')
        selected = deepcopy(sample)
        selected['speaker'] = None
        with self.assertRaisesRegex(ValueError, 'speaker label'):
            self.voice.request([selected])
        selected['speaker'] = 'Morgan'
        selected['source_reference']['quote'] = 'A guest said something else.'
        with self.assertRaisesRegex(ValueError, 'does not match'):
            self.voice.request([selected])
        task = self.pending(selected=[sample])
        self.assertEqual(task['inputs']['samples'][0]['medium'], 'speech')
        output = answer(task)
        self.assertEqual(output['observations'][0]['platform'], 'x')
        proposal = self.engine.complete_task(task['id'], output)[0]
        source_path = self.root / self.engine.store.get('sources', sample['source_reference']['source_id'])['path']
        source_path.write_text('Morgan: A later edit.')
        with self.assertRaisesRegex(ValueError, 'Original source changed'):
            self.voice.apply(proposal['id'])

    def test_two_excerpts_from_one_source_do_not_establish_recurrence(self):
        text = 'Morgan: Name the owner first.\nMorgan: Name the reviewer next.'
        path = Path(self.temp.name) / 'conversation.txt'
        path.write_text(text)
        source = self.engine.capture(path)
        samples = [{'source_reference': {'source_id': source['id'], 'start_line': n, 'end_line': n, 'quote': line},
                    'medium': 'speech', 'platform': None, 'attribution': 'creator', 'speaker': 'Morgan'}
                   for n, line in enumerate(text.splitlines(), 1)]
        task = self.pending(selected=samples)
        output = answer(task)
        observation = output['observations'][0]
        observation['certainty'] = 'recurring'
        observation['evidence'] = [{'sample_id': s['id'], 'quote': s['text']} for s in task['inputs']['samples'][:2]]
        with self.assertRaisesRegex(ValueError, 'independent samples'):
            self.engine.complete_task(task['id'], output)
        self.assertEqual(self.voice.list(), [])

    def test_budget_omits_whole_samples_and_refuses_oversized_voice_document(self):
        self.configure({'sample_chars': 256})
        source = self.captured('Morgan: ' + 'Long sample. ' * 40)
        task = self.pending(selected=[source])
        self.assertLessEqual(task['inputs']['coverage']['chars'], 256)
        self.assertIn({'id': 'source:0', 'reason': 'Sample count/character budget; whole sample omitted.'},
                      task['inputs']['coverage']['omitted'])
        self.engine.cancel_task(task['id'], 'Test a different explicit budget.')
        self.configure({'document_chars': 256})
        with self.assertRaisesRegex(ValueError, 'not truncated'):
            self.voice.request(fresh=True)

    def test_pending_resume_cancel_and_deliberate_new_analysis(self):
        task = self.pending()
        self.assertEqual(self.pending()['id'], task['id'])
        with self.assertRaisesRegex(ValueError, 'Finish or cancel'):
            self.voice.request(fresh=True)
        self.engine.cancel_task(task['id'], 'Different intended sample set.')
        self.assertEqual(self.engine.cancel_task(task['id'], 'Already cancelled.')['status'], 'CANCELLED')
        with self.assertRaisesRegex(ValueError, 'cancelled'):
            self.engine.complete_task(task['id'], answer(task))
        with self.assertRaisesRegex(ValueError, 'cancelled'):
            self.voice.request()
        later = self.pending(fresh=True)
        self.assertNotEqual(later['id'], task['id'])
        proposal = self.complete(later)
        self.assertEqual(self.voice.request()['id'], proposal['id'])
        self.assertEqual(len(self.voice.list()), 1)
        self.voice.dismiss(proposal['id'], 'Need writing rather than speech examples.')
        with self.assertRaisesRegex(ValueError, 'dismissed'):
            self.voice.apply(proposal['id'])

    def test_changed_profile_feedback_or_document_never_overwrites_creator_work(self):
        proposal = self.complete()
        original = self.voice.document.read_bytes()
        atomic_text(self.voice.document, 'Creator added: avoid all slogans.')
        with self.assertRaisesRegex(ValueError, 'VOICE.md changed'):
            self.voice.apply(proposal['id'])
        self.assertEqual(read_text(self.voice.document), 'Creator added: avoid all slogans.')
        self.voice.document.write_bytes(original)
        profile_path = self.root / 'data/creator/profile.json'
        profile_bytes = profile_path.read_bytes()
        atomic_json(profile_path, {**self.profile, 'desired_tone': 'Changed intentionally'})
        with self.assertRaisesRegex(ValueError, 'profile or creator feedback changed'):
            self.voice.apply(proposal['id'])
        profile_path.write_bytes(profile_bytes)
        with patch.object(Feedback, 'context', return_value=[{'note': 'New explicit correction'}]):
            with self.assertRaisesRegex(ValueError, 'profile or creator feedback changed'):
                self.voice.apply(proposal['id'])
        self.assertEqual(self.voice.document.read_bytes(), original)

    def test_new_analysis_replaces_owned_block_but_preserves_creator_edits_outside_it(self):
        first = self.complete()
        self.voice.apply(first['id'])
        atomic_text(self.voice.document, read_text(self.voice.document) + '\nCreator addition: no named frameworks.\n')
        second = self.complete(self.pending(fresh=True))
        self.voice.apply(second['id'])
        document = read_text(self.voice.document)
        self.assertEqual(document.count(OPEN), 1)
        self.assertIn(second['id'], document)
        self.assertNotIn(first['id'], document)
        self.assertIn('Creator addition: no named frameworks.', document)
        self.voice.apply(first['id'])
        self.assertEqual(read_text(self.voice.document), document)

    def test_creator_edits_inside_generated_section_require_reconciliation(self):
        first = self.complete()
        self.voice.apply(first['id'])
        document = read_text(self.voice.document).replace('Lead with the actual action.', 'Creator correction: lead with the problem.')
        atomic_text(self.voice.document, document)
        second = self.complete(self.pending(fresh=True))
        with self.assertRaisesRegex(ValueError, 'edited by the creator'):
            self.voice.apply(second['id'])
        self.assertEqual(read_text(self.voice.document), document)
        self.assertEqual(self.voice.get(second['id'])['status'], 'PROPOSED')

    def test_import_recovery_preserves_saved_proposal_and_sidecar(self):
        task = self.pending()
        with patch.object(self.engine.store, 'put', side_effect=OSError('task checkpoint failed')):
            with self.assertRaises(OSError):
                self.engine.complete_task(task['id'], answer(task))
        proposal = self.voice.list()[0]
        self.voice.path(proposal['id']).with_suffix('.md').unlink()
        with self.assertRaisesRegex(ValueError, 'already committed'):
            self.engine.cancel_task(task['id'], 'Interrupt after the proposal write.')
        self.assertTrue(self.voice.path(proposal['id']).with_suffix('.md').exists())
        restored = self.engine.complete_task(task['id'], {'garbage': 'Ignored after committed result'})[0]
        self.assertEqual(restored['analysis'], answer(task))
        self.assertEqual(len(self.voice.list()), 1)

    def test_apply_recovers_document_write_without_undoing_later_edits(self):
        proposal = self.complete()
        original_save = self.voice.save
        def fail_checkpoint(value):
            if value['status'] == 'APPLIED':
                raise OSError('Final journal write interrupted')
            return original_save(value)
        with patch.object(self.voice, 'save', side_effect=fail_checkpoint):
            with self.assertRaises(OSError):
                self.voice.apply(proposal['id'])
        self.assertEqual(self.voice.get(proposal['id'])['status'], 'APPLYING')
        committed = read_text(self.voice.document)
        atomic_text(self.voice.document, committed + '\nLater creator correction.')
        self.assertEqual(self.voice.apply(proposal['id'])['status'], 'APPLIED')
        self.assertTrue(read_text(self.voice.document).endswith('Later creator correction.'))
        atomic_text(self.voice.document, committed + '\nEven later correction.')
        self.voice.apply(proposal['id'])
        self.assertTrue(read_text(self.voice.document).endswith('Even later correction.'))

    def test_interrupted_apply_with_edited_observations_can_be_set_aside_without_writes(self):
        proposal = self.complete()
        original_save = self.voice.save
        def fail_checkpoint(value):
            if value['status'] == 'APPLIED':
                raise OSError('Interrupted')
            return original_save(value)
        with patch.object(self.voice, 'save', side_effect=fail_checkpoint):
            with self.assertRaises(OSError):
                self.voice.apply(proposal['id'])
        changed = read_text(self.voice.document).replace('Lead with the actual action.', 'Creator: prefer the question first.')
        atomic_text(self.voice.document, changed)
        with self.assertRaisesRegex(ValueError, 'VOICE.md changed'):
            self.voice.apply(proposal['id'])
        self.voice.dismiss(proposal['id'], 'The creator has taken over this section; preserve it for manual reconciliation.')
        self.assertEqual(read_text(self.voice.document), changed)
        self.assertNotEqual(overview(self.root)['stage'], 'VOICE')

    def test_apply_retries_after_failure_before_document_write(self):
        proposal = self.complete()
        before = read_text(self.voice.document)
        def write(path, text):
            if path == self.voice.document:
                raise OSError('Document write interrupted')
            return atomic_text(path, text)
        with patch('contentmaxxing.voice.atomic_text', side_effect=write):
            with self.assertRaises(OSError):
                self.voice.apply(proposal['id'])
        self.assertEqual(read_text(self.voice.document), before)
        self.assertEqual(self.voice.get(proposal['id'])['status'], 'APPLYING')
        self.assertEqual(self.voice.apply(proposal['id'])['status'], 'APPLIED')

    def test_provider_uses_shared_analyze_contract_and_empty_findings_are_valid(self):
        provider = Mock()
        output = {'summary': 'Too little evidence to infer a pattern.', 'observations': [],
                  'unknowns': ['Need examples from different occasions.'], 'conflicts': []}
        provider.analyze.return_value = output
        proposal = Voice(Engine(self.root, provider=provider)).request()
        provider.analyze.assert_called_once()
        provider.generate.assert_not_called()
        task = provider.analyze.call_args[0][0]
        self.assertIn('## Inputs and analysis', task['instructions'])
        self.assertEqual(task['operation'], 'voice')
        self.assertEqual(proposal['analysis']['observations'], [])
        with self.assertRaisesRegex(ValueError, 'Extractive mode cannot learn'):
            Voice(Engine(self.root, provider_name='extractive')).request(fresh=True)

    def test_compatible_provider_and_cli_use_same_portable_task_after_export(self):
        task = self.pending()
        transport = Mock(return_value={'choices': [{'message': {'content': json.dumps(answer(task))}}]})
        provider = OpenAICompatibleProvider('https://example.invalid/v1', 'demo', 'fake', transport)
        output = provider.analyze(task)
        self.assertEqual(json.loads(transport.call_args.args[3]['messages'][1]['content'])['output_contract'], task['output_contract'])
        result = Path(self.temp.name) / 'result.json'
        atomic_json(result, output)
        proposal = self.cli('tasks', 'complete', task['id'], str(result))[0]
        self.assertEqual(self.cli('voice', 'list')[0]['id'], proposal['id'])
        self.cli('voice', 'apply', proposal['id'])
        archive = Path(self.temp.name) / 'portable.zip'
        export_workspace(self.engine.store, archive)
        restored = Path(self.temp.name) / 'restored'
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(restored)
        other = Voice(Engine(restored))
        self.assertEqual(other.request()['analysis'], proposal['analysis'])
        self.assertEqual(other.apply(proposal['id'])['status'], 'APPLIED')
        self.assertEqual(other.document.read_bytes(), self.voice.document.read_bytes())
        self.assertNotIn(str(self.root), json.dumps(other.get(proposal['id'])))

    def test_old_workspace_contract_fallback_does_not_replace_local_skill(self):
        (self.engine.store.assets / 'schemas/voice-analysis.schema.json').unlink()
        skill = self.engine.store.assets / 'skills/voice/SKILL.md'
        skill.write_text(skill.read_text() + '\nCreator customization: KEEP ME.\n')
        task = self.pending()
        self.assertIn('KEEP ME', task['instructions'])
        self.assertEqual(self.complete(task)['status'], 'PROPOSED')
        self.assertIn('KEEP ME', skill.read_text())
