import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import yaml

from contentmaxxing.cli import main
from contentmaxxing.engine import Engine
from contentmaxxing.export import export_workspace
from contentmaxxing.kickoff import Kickoff
from contentmaxxing.store import Store

FIXTURES = Path(__file__).parent / 'fixtures'


class KickoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name) / 'creator'
        self.profile = json.loads((FIXTURES / 'creator.json').read_text())
        self.engine = Engine(self.workspace, provider_name='external')
        self.kickoff = Kickoff(self.engine)

    def tearDown(self):
        self.temp.cleanup()

    def mine_pending(self, response):
        for pending in response['pending_tasks']:
            task = self.engine.store.get('tasks', pending['id'])
            lines = task['inputs']['text'].splitlines()
            output = {'ideas': [{'topic': 'Specific decision from source line ' + str(i),
                                'quote': line, 'start_line': i, 'end_line': i,
                                'category': 'operator observation'} for i, line in enumerate(lines, 1)]}
            self.engine.complete_task(task['id'], output)

    def write_pending(self, response):
        for pending in response['pending_tasks']:
            task = self.engine.store.get('tasks', pending['id'])
            ref = task['inputs']['idea']['source_reference'][0]
            self.engine.complete_task(task['id'], {
                'body': ref['quote'].replace('Morgan: ', ''), 'title': task['inputs']['idea']['topic'],
                'claims': [{'claim': ref['quote'], 'source_reference': ref}],
                'quality_notes': ['Fictional test response; creator review still required.'], 'framework': None})

    def test_progressive_questions_and_resume_do_not_reask_known_context(self):
        response = self.kickoff.run(mode='interview')
        self.assertEqual(response['phase'], 'CONTEXT')
        self.assertEqual(len(response['questions']), 3)
        response = self.kickoff.run(answers={'name': 'Morgan', 'audience': 'Studio operators'})
        self.assertEqual(len(response['questions']), 2)
        resumed = Kickoff(Engine(self.workspace)).run(answers={'content_goals': ['Useful working notes'], 'platforms': ['x']})
        self.assertEqual(resumed['phase'], 'SOURCE')
        self.assertFalse((self.workspace / 'data/creator/profile.json').exists())
        state = json.loads((self.workspace / 'data/creator/kickoff.json').read_text())
        self.assertEqual(state['profile_draft']['name'], 'Morgan')
        self.assertEqual(state['profile_draft']['content_goals'], ['Useful working notes'])

    def test_material_questions_use_existing_voice_and_restrictions(self):
        response = self.kickoff.run(answers=self.profile)
        self.assertEqual(response['phase'], 'SOURCE')
        self.assertEqual(len(response['questions']), 1)

    def test_external_launch_carries_through_first_batch_and_is_idempotent(self):
        response = self.kickoff.run(answers=self.profile, sources=[FIXTURES / 'transcript.txt'])
        self.assertEqual(response['phase'], 'MINING')
        self.assertEqual(len(response['pending_tasks']), 1)
        self.kickoff.run()
        self.assertEqual(len(self.engine.store.list('tasks')), 1)
        self.mine_pending(response)
        response = self.kickoff.run()
        self.assertEqual(response['phase'], 'CHOOSE_TOPICS')
        selected = [i['id'] for i in response['candidate_ideas'][:3]]
        for idea in selected:
            self.engine.select(idea, platform='x', format_name='short post', job='Conversation')
        response = self.kickoff.run(idea_ids=selected)
        self.assertEqual(response['phase'], 'DRAFTING')
        self.assertEqual(len(response['pending_tasks']), 3)
        self.assertEqual(len(self.kickoff.run()['pending_tasks']), 3)
        self.write_pending(response)
        response = self.kickoff.run()
        self.assertEqual(response['phase'], 'REVIEW')
        self.assertEqual(len(response['content_ids']), 3)
        for content_id in response['content_ids']:
            content = self.engine.store.get('content', content_id)
            self.assertEqual(content['status'], 'NEEDS_REVIEW')
            self.assertEqual(content['primary_job'], 'Conversation')
            self.assertEqual(content['remote'], {})
        plan = self.workspace / 'data/creator/LAUNCH_PLAN.md'
        self.assertTrue(plan.is_file())
        self.assertIn('First-week rhythm', plan.read_text())
        self.assertEqual(self.kickoff.run()['content_ids'], response['content_ids'])
        self.assertEqual(len(self.engine.store.list('tasks')), 4)
        cfg = yaml.safe_load((self.workspace / 'workflows.yaml').read_text())
        self.assertEqual(cfg['counts']['x'], 3)
        self.assertEqual(cfg['counts']['linkedin'], 1)
        self.assertEqual(cfg['counts']['x_article'], 0)

    def test_source_supplied_early_survives_export_move_and_original_deletion(self):
        source_path = Path(self.temp.name) / 'my-call.txt'
        source_path.write_text((FIXTURES / 'transcript.txt').read_text())
        response = self.kickoff.run(mode='interview', sources=[source_path])
        self.assertEqual(response['phase'], 'CONTEXT')
        archive = Path(self.temp.name) / 'creator.zip'
        export_workspace(self.engine.store, archive)
        restored = Path(self.temp.name) / 'moved'
        shutil.unpack_archive(str(archive), str(restored))
        source_path.unlink()
        response = Kickoff(Engine(restored)).run(answers=self.profile)
        self.assertEqual(response['phase'], 'MINING')
        self.assertEqual(len(response['source_ids']), 1)
        self.assertTrue((restored / 'START_HERE.md').exists())
        self.assertIn('Morgan:', Store(restored).source_text(response['source_ids'][0]))

    def test_existing_creator_documents_and_cadence_are_preserved(self):
        Store(self.workspace).init('extractive')
        engine = Engine(self.workspace)
        engine.onboard(self.profile)
        engine.capture(FIXTURES / 'transcript.txt')
        voice = self.workspace / 'data/creator/VOICE.md'
        voice.write_text('Creator-edited voice; preserve exactly.')
        workflows = self.workspace / 'workflows.yaml'
        original_workflows = workflows.read_text()
        profile_bytes = (self.workspace / 'data/creator/profile.json').read_bytes()
        response = Kickoff(engine).run()
        self.assertEqual(response['phase'], 'CHOOSE_TOPICS')
        self.assertEqual(voice.read_text(), 'Creator-edited voice; preserve exactly.')
        self.assertEqual(workflows.read_text(), original_workflows)
        self.assertEqual((self.workspace / 'data/creator/profile.json').read_bytes(), profile_bytes)
        with self.assertRaisesRegex(ValueError, 'already onboarded'):
            Kickoff(engine).run(answers={'name': 'A different identity'})

    def test_small_first_week_default_and_quality_shortfall(self):
        engine = Engine(self.workspace, provider_name='extractive')
        kickoff = Kickoff(engine)
        profile = dict(self.profile, posting_cadence={})
        response = kickoff.run(answers=profile, sources=[FIXTURES / 'transcript.txt'])
        response = kickoff.run(idea_ids=[response['candidate_ideas'][0]['id']])
        self.assertEqual(response['phase'], 'REVIEW')
        plan = (self.workspace / 'data/creator/LAUNCH_PLAN.md').read_text()
        self.assertIn('1 of 3 target drafts', plan)
        self.assertIn('Proposed weekly targets', plan)
        counts = yaml.safe_load((self.workspace / 'workflows.yaml').read_text())['counts']
        self.assertEqual(counts['x'], 3)
        self.assertEqual(sum(counts.values()), 3)

    def test_creator_platform_is_respected(self):
        profile = dict(self.profile, platforms=['linkedin'])
        with self.assertRaisesRegex(ValueError, 'creator selected'):
            self.kickoff.run(answers=profile, platform='x', sources=[FIXTURES / 'transcript.txt'])
        self.assertEqual(self.engine.store.list('content'), [])

    def test_cli_uses_separate_creator_folder_inside_repository(self):
        repository = Path(self.temp.name) / 'source-repo'
        (repository / 'contentmaxxing').mkdir(parents=True)
        (repository / 'contentmaxxing/orchestrator.md').write_text('Repository marker')
        (repository / 'AGENTS.md').write_text('Keep repository instructions.')
        before = Path.cwd()
        output = StringIO()
        try:
            os.chdir(repository)
            with redirect_stdout(output):
                result = main(['start'])
        finally:
            os.chdir(before)
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(output.getvalue())['phase'], 'WELCOME')
        self.assertTrue((repository / 'my-creator/config.yaml').is_file())
        self.assertFalse((repository / 'config.yaml').exists())
        self.assertEqual((repository / 'AGENTS.md').read_text(), 'Keep repository instructions.')

    def test_init_keeps_existing_agent_instructions(self):
        self.workspace.mkdir(parents=True)
        (self.workspace / 'AGENTS.md').write_text('Existing workspace instructions.')
        self.kickoff.run()
        self.assertEqual((self.workspace / 'AGENTS.md').read_text(), 'Existing workspace instructions.')
        self.assertTrue((self.workspace / 'START_HERE.md').is_file())

    def test_interrupted_capture_still_applies_starter_cadence_on_resume(self):
        from unittest.mock import patch
        with patch.object(self.engine, 'capture', side_effect=OSError('Simulated interrupted disk operation')):
            with self.assertRaises(OSError):
                self.kickoff.run(answers=self.profile, sources=[FIXTURES / 'transcript.txt'])
        profile_path = self.workspace / 'data/creator/profile.json'
        saved = profile_path.read_bytes()
        response = Kickoff(Engine(self.workspace)).run()
        self.assertEqual(response['phase'], 'MINING')
        self.assertEqual(profile_path.read_bytes(), saved)
        config = yaml.safe_load((self.workspace / 'workflows.yaml').read_text())
        self.assertEqual(config['counts']['x'], 3)
        self.assertEqual(config['counts']['x_article'], 0)
