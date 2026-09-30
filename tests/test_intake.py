import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from contentmaxxing.cli import main
from contentmaxxing.engine import Engine
from contentmaxxing.export import export_workspace
from contentmaxxing.intake import Intake
from contentmaxxing.installation import doctor, install, uninstall
from contentmaxxing.kickoff import Kickoff
from contentmaxxing.store import PACKAGE, Store, atomic_json

FIXTURES = Path(__file__).parent / 'fixtures'


class IntakeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'creator'
        self.engine = Engine(self.root, provider_name='external')
        self.kickoff = Kickoff(self.engine)

    def tearDown(self):
        self.temp.cleanup()

    def proposal(self):
        document = Intake(self.engine.store).summary()['documents'][0]
        lines = (self.root / document['path']).read_text().splitlines()
        profile = {'name': 'Morgan Demo', 'audience': 'Independent studio operators',
                   'content_goals': ['Share usable working notes'], 'platforms': ['x']}
        return {'profile': profile, 'evidence': [
            {'field': field, 'path': document['path'], 'start_line': line, 'end_line': line,
             'quote': lines[line - 1]} for line, field in enumerate(profile, 1)],
            'unknowns': ['Desired weekly pace'], 'conflicts': []}

    def test_new_creator_gets_choice_without_identity_or_tasks(self):
        state = self.kickoff.run()
        self.assertEqual(state['phase'], 'WELCOME')
        self.assertEqual([c['id'] for c in state['choices']], ['interview', 'files'])
        self.assertEqual(self.engine.store.list('tasks'), [])
        self.assertFalse((self.root / 'data/creator/profile.json').exists())
        self.assertTrue(Path(state['welcome_image']).read_bytes().startswith(b'\x89PNG'))
        self.assertEqual(self.kickoff.run()['phase'], 'WELCOME')
        self.assertEqual(self.kickoff.run(mode='interview')['phase'], 'CONTEXT')

    def test_files_are_read_before_profile_questions_and_confirmation_is_required(self):
        self.assertEqual(self.kickoff.run(mode='files')['phase'], 'FILE_DROP')
        state = self.kickoff.run(sources=[FIXTURES / 'intake'])
        self.assertEqual(state['phase'], 'SOURCE_REVIEW')
        self.assertEqual(state['questions'], [])
        self.assertEqual(state['intake']['counts']['READY'], 1)
        state = self.kickoff.run(profile_proposal=self.proposal())
        self.assertEqual(state['phase'], 'PROFILE_REVIEW')
        self.assertFalse((self.root / 'data/creator/profile.json').exists())
        self.assertEqual(self.kickoff.run()['phase'], 'PROFILE_REVIEW')
        state = self.kickoff.run(confirm_profile=True)
        self.assertEqual(state['phase'], 'MINING')
        self.assertEqual(len(state['pending_tasks']), 1)
        self.assertEqual(self.kickoff.run()['source_ids'], state['source_ids'])
        self.assertEqual(len(self.engine.store.list('tasks')), 1)

    def test_folder_inventory_preserves_bytes_deduplicates_and_reports_exceptions(self):
        folder = Path(self.temp.name) / 'drop'
        folder.mkdir()
        content = b'Morgan: A real fictional observation.\r\n'
        (folder / 'note.txt').write_bytes(content)
        (folder / 'copy.md').write_bytes(content)
        (folder / 'empty.txt').write_text('')
        (folder / 'bad.txt').write_bytes(b'\xff\xfe\x00')
        (folder / 'scan.pdf').write_bytes(b'%PDF demo')
        (folder / '.env').write_text('PRIVATE=not-imported')
        (folder / 'node_modules').mkdir()
        (folder / 'node_modules/hidden.txt').write_text('Ignored directory.')
        (folder / 'link.txt').symlink_to(folder / 'note.txt')
        state = self.kickoff.run(mode='files', sources=[folder])
        counts = state['intake']['counts']
        self.assertEqual(counts['READY'], 1)
        self.assertEqual(counts['DUPLICATE'], 1)
        self.assertEqual(counts['EMPTY'], 1)
        self.assertEqual(counts['UNREADABLE'], 1)
        self.assertEqual(counts['UNSUPPORTED'], 1)
        self.assertEqual(counts['SKIPPED'], 3)
        preserved = self.root / state['intake']['documents'][0]['path']
        self.assertEqual(preserved.read_bytes(), content)
        count = len(Intake(self.engine.store).manifest()['entries'])
        self.kickoff.run(sources=[folder])
        self.assertEqual(len(Intake(self.engine.store).manifest()['entries']), count)
        self.assertEqual(len(list((self.root / 'data/inbox').rglob('*.pdf'))), 0)

    def test_unsupported_only_drop_does_not_pretend_to_have_sources(self):
        path = Path(self.temp.name) / 'voice.mp3'
        path.write_bytes(b'fake audio')
        state = self.kickoff.run(mode='files', sources=[path])
        self.assertEqual(state['phase'], 'FILE_DROP')
        self.assertEqual(state['intake']['counts'], {'UNSUPPORTED': 1})
        self.assertEqual(self.engine.store.list('sources'), [])

    def test_file_identity_requires_valid_quote_and_field_evidence(self):
        self.kickoff.run(mode='files', sources=[FIXTURES / 'intake'])
        proposal = self.proposal()
        proposal['evidence'][0]['quote'] = 'An invented name quote'
        with self.assertRaisesRegex(ValueError, 'quote'):
            self.kickoff.run(profile_proposal=proposal)
        proposal = self.proposal()
        proposal['profile']['proof_results'] = ['Invented outcome']
        with self.assertRaisesRegex(ValueError, 'proof_results'):
            self.kickoff.run(profile_proposal=proposal)
        proposal = self.proposal()
        proposal['evidence'][0]['path'] = '../outside.md'
        with self.assertRaisesRegex(ValueError, 'preserved intake'):
            self.kickoff.run(profile_proposal=proposal)
        self.assertFalse((self.root / 'data/creator/profile.json').exists())

    def test_creator_corrections_outrank_profile_suggestions(self):
        self.kickoff.run(mode='files', sources=[FIXTURES / 'intake'])
        self.kickoff.run(profile_proposal=self.proposal())
        self.kickoff.run(confirm_profile=True, answers={'audience': 'A narrower creator-confirmed audience'})
        profile = json.loads((self.root / 'data/creator/profile.json').read_text())
        self.assertEqual(profile['audience'], 'A narrower creator-confirmed audience')
        self.assertEqual(profile['name'], 'Morgan Demo')

    def test_source_change_after_proposal_blocks_confirmation(self):
        self.kickoff.run(mode='files', sources=[FIXTURES / 'intake'])
        proposal = self.proposal()
        self.kickoff.run(profile_proposal=proposal)
        (self.root / proposal['evidence'][0]['path']).write_text('Edited source')
        with self.assertRaisesRegex(ValueError, 'evidence changed'):
            self.kickoff.run(confirm_profile=True)

    def test_profile_proposal_and_sources_survive_portable_export(self):
        self.kickoff.run(mode='files', sources=[FIXTURES / 'intake'])
        self.kickoff.run(profile_proposal=self.proposal())
        archive = Path(self.temp.name) / 'creator.zip'
        export_workspace(self.engine.store, archive)
        restored = Path(self.temp.name) / 'restored'
        shutil.unpack_archive(str(archive), str(restored))
        resumed = Kickoff(Engine(restored)).run(confirm_profile=True)
        self.assertEqual(resumed['phase'], 'MINING')
        self.assertEqual(len(resumed['source_ids']), 1)
        self.assertTrue((restored / '.contentmaxxing/assets/welcome.png').is_file())

    def test_switch_to_interview_keeps_dropped_files_and_answers(self):
        self.kickoff.run(mode='files', sources=[FIXTURES / 'intake'])
        answers = {'name': 'Morgan', 'audience': 'Studio operators'}
        state = self.kickoff.run(mode='interview', answers=answers)
        self.assertEqual(state['phase'], 'CONTEXT')
        self.assertEqual(len(state['questions']), 2)
        self.assertEqual(state['intake']['counts']['READY'], 1)
        state = self.kickoff.run(answers={'platforms': ['x'], 'content_goals': ['Teach useful processes']})
        self.assertEqual(state['phase'], 'MINING')

    def test_legacy_launch_resumes_without_new_welcome(self):
        self.kickoff.run(mode='interview', answers={'name': 'Morgan'})
        path = self.root / 'data/creator/kickoff.json'
        old = json.loads(path.read_text())
        old.pop('intake_mode')
        old['version'] = 1
        atomic_json(path, old)
        state = self.kickoff.run()
        self.assertEqual(state['phase'], 'CONTEXT')
        self.assertEqual(state['choices'], [])
        self.assertEqual(json.loads(path.read_text())['profile_draft']['name'], 'Morgan')

    def test_new_drop_invalidates_an_unconfirmed_profile_proposal(self):
        self.kickoff.run(mode='files', sources=[FIXTURES / 'intake'])
        self.kickoff.run(profile_proposal=self.proposal())
        state = self.kickoff.run(sources=[FIXTURES / 'transcript.txt'])
        self.assertEqual(state['phase'], 'SOURCE_REVIEW')
        self.assertIsNone(state['profile_proposal'])

    def test_saved_inventory_recovers_after_copy_checkpoint_interruption(self):
        self.kickoff.run(mode='files')
        ingest = Intake.ingest

        def interrupted(instance, paths):
            ingest(instance, paths)
            raise OSError('Simulated interruption after preserving files')

        with patch.object(Intake, 'ingest', interrupted):
            with self.assertRaises(OSError):
                self.kickoff.run(sources=[FIXTURES / 'intake'])
        self.assertEqual(self.kickoff.run()['phase'], 'SOURCE_REVIEW')
        self.kickoff.run(profile_proposal=self.proposal())
        state = self.kickoff.run(confirm_profile=True)
        self.assertEqual(state['phase'], 'MINING')
        self.assertEqual(len(state['source_ids']), 1)

    def test_welcome_asset_is_installed_and_owned_like_other_resources(self):
        result = install('codex', self.root)
        asset = Path(result['welcome']['image'])
        self.assertEqual(asset.read_bytes(), (PACKAGE / 'assets/welcome.png').read_bytes())
        self.assertTrue(Path(result['welcome']['document']).exists())
        asset.write_bytes(b'creator customized image')
        self.assertFalse(doctor('codex', self.root)['integrity_ok'])
        removed = uninstall('codex', self.root)
        self.assertIn(str(asset.relative_to(self.root.resolve())), removed['preserved_edited_files'])
        self.assertEqual(asset.read_bytes(), b'creator customized image')

    def test_cli_home_and_install_have_human_hud_and_json_modes(self):
        class Terminal(StringIO):
            def isatty(self):
                return True
        terminal = Terminal()
        with redirect_stdout(terminal):
            self.assertEqual(main(['install', '--agent', 'codex', '--path', str(self.root)]), 0)
        self.assertIn('CONTENTMAXXING', terminal.getvalue())
        self.assertIn('MEGA FILE DUMP', terminal.getvalue())
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(['--json', 'welcome']), 0)
        self.assertEqual(len(json.loads(output.getvalue())['choices']), 2)
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(['--workspace', str(self.root), 'start', '--mode', 'files', '--source', str(FIXTURES / 'intake')]), 0)
        self.assertEqual(json.loads(output.getvalue())['phase'], 'SOURCE_REVIEW')
