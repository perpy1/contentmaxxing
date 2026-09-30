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
from contentmaxxing.providers import PendingTask
from contentmaxxing.store import Store, atomic_bytes
from contentmaxxing.workspace_assets import MANIFEST, WorkspaceUpgrade, bundle

FIXTURES = Path(__file__).parent / 'fixtures'


class WorkspaceUpgradeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'creator'
        self.store = Store(self.root)
        self.store.init('extractive')
        self.incoming = Path(self.temp.name) / 'incoming'
        for name, value in bundle().items():
            atomic_bytes(self.incoming / name, value)
        self.upgrade = WorkspaceUpgrade(self.store, self.incoming)

    def tearDown(self):
        self.temp.cleanup()

    def files(self, root=None):
        root = root or self.root
        return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}

    def append(self, name, text='\nIncoming update.\n'):
        path = self.incoming / name
        path.write_text(path.read_text() + text)

    def cli(self, *args, success=True):
        output, error = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            code = main(['--workspace', str(self.root), 'upgrade', *args])
        self.assertEqual(code, 0 if success else 1, error.getvalue())
        return json.loads(output.getvalue()) if success else error.getvalue()

    def test_preview_and_repeat_are_byte_identical(self):
        original = self.files()
        preview = self.upgrade.run(dry_run=True)
        self.assertFalse(preview['legacy_workspace'])
        self.assertEqual(preview['write'], [])
        self.assertEqual(self.files(), original)
        self.assertIsNone(self.upgrade.run()['upgrade_id'])
        self.assertEqual(self.files(), original)
        self.append('prompts/quality-checks.md')
        preview = self.upgrade.run(dry_run=True)
        self.assertEqual(preview['write'], ['prompts/quality-checks.md'])
        self.assertEqual(self.files(), original)
        self.upgrade.run()
        upgraded = self.files()
        self.assertEqual(self.upgrade.run()['write'], [])
        self.assertEqual(self.files(), upgraded)

    def test_new_tasks_use_updated_skills_pending_tasks_and_creator_state_stay_frozen(self):
        engine = Engine(self.root)
        engine.onboard(json.loads((FIXTURES / 'creator.json').read_text()))
        source = engine.capture(FIXTURES / 'transcript.txt', consent='fictional')
        ideas = engine.mine(source['id'])
        engine.select(ideas[0]['id'], job='Bookmarks / Saves')
        external = Engine(self.root, provider_name='external')
        with self.assertRaises(PendingTask) as first:
            external.draft(ideas[0]['id'])
        frozen = self.store.get('tasks', first.exception.task_id)
        marker = '\nUse the fictional upgrade trial writing instruction.\n'
        self.append('skills/x-writing/SKILL.md', marker)
        custom = self.store.assets / 'skills/linkedin/SKILL.md'
        custom.write_text(custom.read_text() + '\nCreator-specific writing preference.\n')
        custom_bytes = custom.read_bytes()
        self.append('skills/linkedin/SKILL.md')
        voice = self.store.data / 'creator/VOICE.md'
        voice.write_text(voice.read_text() + '\nManual creator voice preference.\n')
        before = self.files()
        result = self.upgrade.run()
        self.assertEqual(result['write'], ['skills/x-writing/SKILL.md'])
        self.assertIn('skills/linkedin/SKILL.md', result['preserved'])
        self.assertEqual(custom.read_bytes(), custom_bytes)
        for name, value in before.items():
            if not name.startswith('.contentmaxxing/'):
                self.assertEqual((self.root / name).read_bytes(), value, name)
        self.assertEqual(self.store.get('tasks', first.exception.task_id), frozen)
        engine.select(ideas[1]['id'], job='Conversation')
        with self.assertRaises(PendingTask) as second:
            external.draft(ideas[1]['id'])
        new_task = self.store.get('tasks', second.exception.task_id)
        self.assertIn(marker.strip(), new_task['instructions'])
        self.assertNotIn(marker.strip(), frozen['instructions'])

    def test_legacy_matching_files_need_explicit_adoption_differing_files_stay_custom(self):
        (self.store.assets / MANIFEST).unlink()
        custom = self.store.assets / 'prompts/system.md'
        custom.write_text('An older or customized system file; origin unknown.\n')
        original = custom.read_bytes()
        result = self.upgrade.run()
        self.assertTrue(result['legacy_workspace'])
        self.assertEqual(result['write'], [])
        self.assertEqual(self.upgrade.manifest()['files'], {})
        self.assertEqual(custom.read_bytes(), original)
        result = self.upgrade.run(adopt_matching=True)
        self.assertEqual(result['preserved'], ['prompts/system.md'])
        self.assertNotIn('prompts/system.md', self.upgrade.manifest()['files'])
        self.append('skills/x-writing/SKILL.md')
        self.assertEqual(self.upgrade.run()['write'], ['skills/x-writing/SKILL.md'])
        self.assertEqual(custom.read_bytes(), original)

    def test_missing_new_assets_added_deleted_custom_and_retired_assets_preserved(self):
        existing = self.store.assets / 'prompts/quality-checks.md'
        existing.unlink()
        retired = self.incoming / 'templates/article-frameworks.md'
        retired.unlink()
        atomic_bytes(self.incoming / 'skills/new-example/SKILL.md', b'# New skill\n')
        custom = self.store.assets / 'skills/creator-only/SKILL.md'
        atomic_bytes(custom, b'My private working procedure.')
        result = self.upgrade.run()
        self.assertEqual(result['write'], ['skills/new-example/SKILL.md'])
        self.assertFalse(existing.exists())
        self.assertTrue((self.store.assets / 'templates/article-frameworks.md').exists())
        self.assertEqual(custom.read_bytes(), b'My private working procedure.')
        review = self.upgrade.review('prompts/quality-checks.md')
        self.upgrade.run(accept=[review['accept']])
        self.assertTrue(existing.exists())

    def test_reviewed_replacement_is_backed_up_and_never_changes_voice(self):
        target = self.store.assets / 'prompts/quality-checks.md'
        target.write_text('My old custom checks.\n')
        voice = self.store.data / 'creator/VOICE.md'
        atomic_bytes(voice, b'Creator voice, not bundled voice.')
        before = self.files()
        review = self.upgrade.review('prompts/quality-checks.md')
        self.assertIn('-My old custom checks.', review['diff'])
        self.assertEqual(self.files(), before)
        result = self.upgrade.run(accept=[review['accept']])
        journal = self.store.assets / 'updates' / result['upgrade_id']
        self.assertEqual((journal / 'before/prompts/quality-checks.md').read_text(), 'My old custom checks.\n')
        self.assertEqual(json.loads((journal / 'report.json').read_text())['status'], 'APPLIED')
        self.assertEqual(target.read_bytes(), (self.incoming / 'prompts/quality-checks.md').read_bytes())
        self.assertEqual(voice.read_bytes(), b'Creator voice, not bundled voice.')

    def test_stale_acceptance_rejects_current_or_incoming_change_before_all_writes(self):
        self.append('skills/x-writing/SKILL.md')  # another otherwise safe update
        for changed_root in (self.store.assets, self.incoming):
            review = self.upgrade.review('prompts/system.md')
            path = changed_root / 'prompts/system.md'
            path.write_text(path.read_text() + '\nChanged since review.\n')
            before = self.files()
            with self.assertRaisesRegex(ValueError, 'Review is stale'):
                self.upgrade.run(accept=[review['accept']])
            self.assertEqual(self.files(), before)

    def test_write_failure_rolls_back_the_whole_upgrade(self):
        self.append('prompts/system.md')
        self.append('skills/x-writing/SKILL.md')
        before = self.files()
        failed = []

        def write(path, value):
            if Path(path) == self.store.assets / MANIFEST and not failed:
                failed.append(True)
                raise OSError('simulated disk failure')
            atomic_bytes(path, value)

        with patch('contentmaxxing.workspace_assets.atomic_bytes', side_effect=write):
            with self.assertRaisesRegex(OSError, 'simulated disk failure'):
                self.upgrade.run()
        for name, value in before.items():
            self.assertEqual((self.root / name).read_bytes(), value, name)
        reports = list((self.store.assets / 'updates').glob('*/report.json'))
        self.assertEqual(json.loads(reports[0].read_text())['status'], 'ROLLED_BACK')
        self.assertEqual(self.upgrade.pending(), [])

    def interrupt(self):
        self.append('prompts/system.md')
        self.append('skills/x-writing/SKILL.md')

        def write(path, value):
            if Path(path) == self.store.assets / MANIFEST:
                raise KeyboardInterrupt('simulated terminated process')
            atomic_bytes(path, value)

        with patch('contentmaxxing.workspace_assets.atomic_bytes', side_effect=write):
            with self.assertRaises(KeyboardInterrupt):
                self.upgrade.run()
        return self.upgrade.pending()[0]

    def test_interrupted_upgrade_recovers_after_export_and_move(self):
        before = self.files()
        identifier = self.interrupt()
        with self.assertRaisesRegex(ValueError, 'interrupted upgrade'):
            self.upgrade.run()
        archive = Path(self.temp.name) / 'workspace.zip'
        export_workspace(self.store, archive)
        moved = Path(self.temp.name) / 'moved'
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(moved)
        upgrade = WorkspaceUpgrade(Store(moved), self.incoming)
        self.assertEqual(upgrade.recover(identifier)['status'], 'ROLLED_BACK')
        for name, value in before.items():
            self.assertEqual((moved / name).read_bytes(), value, name)
        self.assertEqual(upgrade.recover(identifier)['restored'], [])
        self.assertEqual(len(upgrade.run()['write']), 2)

    def test_recovery_refuses_newer_edits_and_tampered_backups_without_partial_writes(self):
        identifier = self.interrupt()
        target = self.store.assets / 'prompts/system.md'
        updated = target.read_bytes()
        target.write_text('A newer user edit after the interruption.')
        before = self.files()
        with self.assertRaisesRegex(ValueError, 'newer edit'):
            self.upgrade.recover(identifier)
        self.assertEqual(self.files(), before)
        target.write_bytes(updated)
        backup = self.store.assets / 'updates' / identifier / 'before/prompts/system.md'
        backup.write_text('Someone changed the backup.')
        before = self.files()
        with self.assertRaisesRegex(ValueError, 'backup changed'):
            self.upgrade.recover(identifier)
        self.assertEqual(self.files(), before)

    def test_untrusted_manifest_and_review_paths_cannot_claim_creator_data(self):
        for name in ('../data/creator/VOICE.md', '/tmp/not-an-asset', 'data/creator/VOICE.md', MANIFEST):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    self.upgrade.review(name)
        manifest = self.upgrade.manifest()
        manifest['files']['../data/creator/VOICE.md'] = '0' * 64
        (self.store.assets / MANIFEST).write_text(json.dumps(manifest))
        before = self.files()
        with self.assertRaisesRegex(ValueError, 'Invalid intelligence manifest'):
            self.upgrade.run()
        self.assertEqual(self.files(), before)

    def test_symlink_refused_before_upgrade_writes(self):
        target = self.store.assets / 'prompts/system.md'
        outside = Path(self.temp.name) / 'outside.md'
        outside.write_bytes(target.read_bytes())
        target.unlink()
        target.symlink_to(outside)
        self.append('skills/x-writing/SKILL.md')
        original = outside.read_bytes()
        with self.assertRaisesRegex(ValueError, 'symlink'):
            self.upgrade.run()
        self.assertEqual(outside.read_bytes(), original)
        self.assertFalse((self.store.assets / 'updates').exists())

    def test_live_writer_blocks_apply_but_preview_is_read_only(self):
        self.append('prompts/system.md')
        with self.store.lock():
            other = WorkspaceUpgrade(Store(self.root), self.incoming)
            before = self.files()
            self.assertEqual(other.run(dry_run=True)['write'], ['prompts/system.md'])
            with self.assertRaisesRegex(ValueError, 'Workspace busy'):
                other.run()
            self.assertEqual(self.files(), before)

    def test_new_init_does_not_overwrite_preexisting_intelligence(self):
        root = Path(self.temp.name) / 'not-initialized'
        target = root / '.contentmaxxing/skills/x-writing/SKILL.md'
        atomic_bytes(target, b'Existing custom writing rules.')
        with self.assertRaisesRegex(ValueError, 'Existing .contentmaxxing files preserved'):
            Store(root).init()
        self.assertEqual(target.read_bytes(), b'Existing custom writing rules.')
        self.assertFalse((root / 'data').exists())
        self.assertFalse((root / 'config.yaml').exists())

    def test_cli_review_accept_and_invalid_option_combinations(self):
        target = self.store.assets / 'prompts/system.md'
        target.write_text('Old fictional system instructions.\n')
        before = self.files()
        preview = self.cli('--dry-run')
        self.assertIn('prompts/system.md', preview['preserved'])
        review = self.cli('--review', 'prompts/system.md')
        self.assertEqual(self.files(), before)
        result = self.cli('--accept', review['accept'])
        self.assertEqual(result['write'], ['prompts/system.md'])
        self.assertIn('cannot be combined', self.cli('--review', 'prompts/system.md', '--dry-run', success=False))
        self.assertIn('FILE=TOKEN', self.cli('--accept', 'prompts/system.md', success=False))
