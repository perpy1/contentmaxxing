import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import yaml

from contentmaxxing.cli import main
from contentmaxxing.engine import Engine
from contentmaxxing.export import export_workspace
from contentmaxxing.installation import (HOSTS, SKILL_ROOTS, catalog, doctor, install,
                                         invocation, manifest_path, render, uninstall)
from contentmaxxing.kickoff import Kickoff
from contentmaxxing.overview import overview
from contentmaxxing.store import Store, atomic_text

FIXTURES = Path(__file__).parent / 'fixtures'


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'creator'

    def tearDown(self):
        self.temp.cleanup()

    def test_dry_run_writes_nothing_and_menu_is_host_native(self):
        for host in HOSTS:
            result = install(host, self.root, dry_run=True)
            self.assertEqual(len(result['commands']), len(catalog()))
            self.assertFalse(self.root.exists())
            if host != 'generic':
                self.assertIn(invocation(host, 'start'), result['next'])
        self.assertEqual(invocation('codex', 'start'), '$contentmaxxing-start')
        self.assertEqual(invocation('claude', 'start'), '/contentmaxxing-start')
        self.assertEqual(invocation('gemini', 'start'), '/contentmaxxing:start')

    def test_native_entrypoints_resolve_to_shared_procedures_for_all_hosts(self):
        for host in HOSTS:
            with self.subTest(host=host):
                root = self.root / host
                install(host, root)
                self.assertTrue(doctor(host, root)['integrity_ok'])
                self.assertFalse((root / 'config.yaml').exists())
                self.assertFalse((root / 'data').exists())
                core = root / '.contentmaxxing-agent' / host / 'core'
                self.assertEqual(json.loads((core / 'config/commands.json').read_text()), catalog())
                for command in catalog():
                    self.assertTrue((core / 'commands' / (command['name'] + '.md')).is_file())
                    if host in SKILL_ROOTS:
                        path = root / SKILL_ROOTS[host] / ('contentmaxxing-' + command['name']) / 'SKILL.md'
                        text = path.read_text()
                        metadata = yaml.safe_load(text.split('---')[1])
                        self.assertEqual(metadata['name'], 'contentmaxxing-' + command['name'])
                    elif host == 'gemini':
                        path = root / '.gemini/commands/contentmaxxing' / (command['name'] + '.toml')
                        text = json.loads(path.read_text().split('prompt = ', 1)[1])
                    else:
                        path = root / '.contentmaxxing-agent/generic/CONTENTMAXXING.md'
                        text = path.read_text()
                    reference = re.search(r'Core bundle: `([^`]+)`', text).group(1)
                    self.assertEqual((path.parent / reference).resolve(), core.resolve())
                    self.assertNotIn(str(root), text)

    @unittest.skipIf(sys.version_info < (3, 11), 'tomllib is part of Python 3.11+')
    def test_gemini_commands_are_real_toml_without_shell_interpolation(self):
        import tomllib
        for name, text in render('gemini').items():
            if name.endswith('.toml'):
                payload = tomllib.loads(text)
                self.assertIn('{{args}}', payload['prompt'])
                self.assertNotIn('!{', payload['prompt'])
                self.assertNotIn('@{', payload['prompt'])

    def test_repeat_install_updates_owned_files_and_preserves_creator_data(self):
        install('claude', self.root)
        Store(self.root).init()
        custom = self.root / 'data/creator/VOICE.md'
        custom.write_text('My exact voice, intentionally edited.')
        agents = self.root / 'AGENTS.md'
        before = agents.read_bytes()
        result = install('claude', self.root)
        self.assertEqual(result['write'], [])
        original_render = render('claude')
        name = '.claude/skills/contentmaxxing-start/SKILL.md'
        with patch('contentmaxxing.installation.render', return_value={**original_render, name: original_render[name] + '\nUpdated entrypoint.\n'}):
            result = install('claude', self.root)
            self.assertEqual(result['write'], [name])
        self.assertEqual(custom.read_text(), 'My exact voice, intentionally edited.')
        self.assertEqual(agents.read_bytes(), before)

    def test_conflicting_edits_are_preflighted_before_any_write(self):
        install('codex', self.root)
        path = self.root / '.agents/skills/contentmaxxing-start/SKILL.md'
        path.write_text('My custom command.')
        old = (self.root / manifest_path('codex')).read_bytes()
        with self.assertRaisesRegex(ValueError, 'Preserved locally edited'):
            install('codex', self.root)
        self.assertEqual(path.read_text(), 'My custom command.')
        self.assertEqual((self.root / manifest_path('codex')).read_bytes(), old)
        self.assertFalse(doctor('codex', self.root)['integrity_ok'])

    def test_unowned_collision_never_gets_overwritten(self):
        path = self.root / '.claude/skills/contentmaxxing/SKILL.md'
        path.parent.mkdir(parents=True)
        path.write_text('An independently installed skill.')
        with self.assertRaisesRegex(ValueError, 'unowned'):
            install('claude', self.root)
        self.assertFalse((self.root / manifest_path('claude')).exists())
        self.assertEqual(path.read_text(), 'An independently installed skill.')

    def test_identical_unowned_skill_is_not_silently_adopted(self):
        name = '.claude/skills/contentmaxxing/SKILL.md'
        path = self.root / name
        path.parent.mkdir(parents=True)
        path.write_text(render('claude')[name])
        with self.assertRaisesRegex(ValueError, 'unowned'):
            install('claude', self.root)
        self.assertFalse((self.root / manifest_path('claude')).exists())

    def test_uninstall_keeps_modified_files_and_all_creator_and_other_host_files(self):
        install('claude', self.root)
        Store(self.root).init()
        unrelated = self.root / '.claude/skills/my-skill/SKILL.md'
        unrelated.parent.mkdir(parents=True)
        unrelated.write_text('Not owned by CONTENTMAXXING.')
        custom = self.root / '.claude/skills/contentmaxxing-start/SKILL.md'
        custom.write_text('Locally customized.')
        before = {str(p): p.read_bytes() for p in (self.root / '.contentmaxxing').rglob('*') if p.is_file()}
        preview = uninstall('claude', self.root, dry_run=True)
        self.assertTrue((self.root / '.claude/skills/contentmaxxing/SKILL.md').exists())
        actual = uninstall('claude', self.root)
        self.assertEqual(actual['removed'], preview['removed'])
        self.assertEqual(actual['preserved_edited_files'], ['.claude/skills/contentmaxxing-start/SKILL.md'])
        self.assertEqual(custom.read_text(), 'Locally customized.')
        self.assertTrue(unrelated.exists())
        self.assertTrue((self.root / 'config.yaml').exists())
        for name, value in before.items():
            self.assertEqual(Path(name).read_bytes(), value)

    def test_manifest_cannot_claim_arbitrary_creator_files(self):
        install('codex', self.root)
        manifest = self.root / manifest_path('codex')
        data = json.loads(manifest.read_text())
        data['files']['data/creator/VOICE.md'] = '0' * 64
        manifest.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'Invalid owned file'):
            uninstall('codex', self.root)
        self.assertTrue((self.root / '.agents/skills/contentmaxxing/SKILL.md').exists())

    def test_symlinked_host_directory_is_not_followed(self):
        outside = Path(self.temp.name) / 'other'
        outside.mkdir()
        self.root.mkdir()
        (self.root / '.claude').symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            install('claude', self.root)
        self.assertEqual(list(outside.iterdir()), [])

    def test_user_scope_is_explicit_and_never_initializes_home_as_creator(self):
        fake_home = Path(self.temp.name) / 'home'
        with patch('contentmaxxing.installation.Path.home', return_value=fake_home):
            install('codex', scope='user')
            self.assertTrue((fake_home / '.agents/skills/contentmaxxing-start/SKILL.md').is_file())
            self.assertFalse((fake_home / 'data').exists())
            self.assertFalse((fake_home / 'config.yaml').exists())
            with self.assertRaisesRegex(ValueError, '--path'):
                install('codex', self.root, scope='user')

    def test_write_failure_rolls_back_existing_installation(self):
        install('codex', self.root)
        original = render('codex')
        changed = {key: text + ('\n' if isinstance(text, str) else b'\n') for key, text in original.items()}
        calls = [0]

        def fail_once(path, text):
            calls[0] += 1
            if calls[0] == 2:
                raise OSError('Simulated full disk')
            return atomic_text(path, text)

        with patch('contentmaxxing.installation.render', return_value=changed), patch('contentmaxxing.installation.atomic_text', side_effect=fail_once):
            with self.assertRaises(OSError):
                install('codex', self.root)
        self.assertTrue(doctor('codex', self.root)['integrity_ok'])

    def test_moving_project_keeps_instruction_links_valid_and_reinstall_keeps_voice(self):
        install('claude', self.root)
        Store(self.root).init()
        voice = self.root / 'data/creator/VOICE.md'
        voice.write_text('Portable creator voice.')
        archive = Path(self.temp.name) / 'creator.zip'
        export_workspace(Store(self.root), archive)
        moved = Path(self.temp.name) / 'moved'
        shutil.unpack_archive(str(archive), str(moved))
        install('codex', moved)
        self.assertEqual((moved / 'data/creator/VOICE.md').read_text(), 'Portable creator voice.')
        self.assertTrue(doctor('codex', moved)['integrity_ok'])
        self.assertFalse((moved / '.claude').exists())

    def test_overview_is_read_only_before_setup_and_after_pending_work(self):
        self.assertFalse(overview(self.root)['initialized'])
        self.assertFalse(self.root.exists())
        engine = Engine(self.root)
        profile = json.loads((FIXTURES / 'creator.json').read_text())
        kickoff = Kickoff(engine).run(answers=profile, sources=[FIXTURES / 'transcript.txt'])
        before = (self.root / 'data/creator/kickoff.json').read_bytes()
        state = overview(self.root)
        self.assertEqual(state['kickoff_phase'], 'MINING')
        self.assertEqual(len(state['pending_tasks']), 1)
        self.assertEqual((self.root / 'data/creator/kickoff.json').read_bytes(), before)
        self.assertEqual(kickoff['pending_tasks'][0]['id'], state['pending_tasks'][0]['id'])

    def test_cli_install_then_runtime_fallback_starts_creator_outside_repository(self):
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(['install', '--agent', 'claude', '--path', str(self.root)]), 0)
        runtime = json.loads((self.root / '.contentmaxxing-agent/claude/runtime.json').read_text())
        process = subprocess.run([runtime['python'], '-m', runtime['module'], '--workspace', str(self.root),
                                  '--provider', 'external', 'start'], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stdout)['phase'], 'WELCOME')
        self.assertTrue((self.root / '.contentmaxxing/skills/kickoff/SKILL.md').is_file())
        errors = StringIO()
        with redirect_stderr(errors):
            self.assertEqual(main(['--workspace', str(self.root), 'install', '--agent', 'claude']), 1)
        self.assertIn('Use --path', errors.getvalue())
