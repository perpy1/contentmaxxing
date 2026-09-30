"""Distribution failures must fail before a candidate is described as ready."""
import importlib.util
import io
import json
import subprocess
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('verify_release', Path(__file__).resolve().parents[1] / 'scripts/verify_release.py')
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


class ReleaseArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.dist = self.root / 'dist'
        self.dist.mkdir()
        for name in release.ROOT_FILES:
            (self.root / name).write_text('Fictional project fixture.\n')
        (self.root / 'pyproject.toml').write_text('[project]\nname="contentmaxxing"\nversion="0.1.0"\n')
        for name, data in {
            'contentmaxxing/__init__.py': b'__version__ = "0.1.0"\n',
            'contentmaxxing/skills/capture/SKILL.md': b'Fictional capture skill',
            'contentmaxxing/assets/welcome.png': b'Fictional image bytes',
            '.github/workflows/tests.yml': b'name: Example\n',
            'tests/fixtures/creator.json': b'{"name":"Fictional"}',
            'scripts/release_smoke.py': b'# Fixture smoke\n',
        }.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        self.runtime = {'contentmaxxing/' + k: v for k, v in release.files_under(self.root / 'contentmaxxing').items()}
        self.metadata = b'Name: contentmaxxing\nVersion: 0.1.0\n'

    def pack(self, wheel_remove=(), wheel_add=None, source_remove=(), source_add=None, version='0.1.0'):
        wheel_files = dict(self.runtime)
        wheel_files['contentmaxxing-0.1.0.dist-info/METADATA'] = self.metadata.replace(b'0.1.0', version.encode())
        for key in wheel_remove:
            wheel_files.pop(key)
        wheel_files.update(wheel_add or {})
        with zipfile.ZipFile(self.dist / 'contentmaxxing-0.1.0-py3-none-any.whl', 'w') as archive:
            for name, data in wheel_files.items():
                archive.writestr(name, data)
        source_files = release.files_under(self.root)
        source_files.update({name: (self.root / name).read_bytes() for name in release.ROOT_FILES})
        source_files['PKG-INFO'] = self.metadata
        for key in source_remove:
            source_files.pop(key)
        source_files.update(source_add or {})
        with tarfile.open(self.dist / 'contentmaxxing-0.1.0.tar.gz', 'w:gz') as archive:
            for name, data in source_files.items():
                member = tarfile.TarInfo('contentmaxxing-0.1.0/' + name)
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))

    def test_complete_candidate_records_hashes_and_never_invents_release_provenance(self):
        self.pack()
        result = release.verify_archives(self.root, self.dist)
        self.assertEqual(result['version'], '0.1.0')
        self.assertEqual(result['source']['kind'], 'LOCAL_CANDIDATE')
        self.assertIsNone(result['source']['commit'])
        self.assertEqual(len(result['runtime']), 3)
        for archive in result['artifacts']:
            self.assertEqual(archive['sha256'], release.digest((self.dist / archive['file']).read_bytes()))

    def test_missing_skill_or_hud_is_a_release_failure(self):
        for name in ('contentmaxxing/skills/capture/SKILL.md', 'contentmaxxing/assets/welcome.png'):
            with self.subTest(name=name):
                self.pack(wheel_remove=[name])
                with self.assertRaisesRegex(ValueError, 'Wheel runtime mismatch'):
                    release.verify_archives(self.root, self.dist)

    def test_source_archive_must_contain_the_tests_and_ci(self):
        for name in ('tests/fixtures/creator.json', '.github/workflows/tests.yml'):
            with self.subTest(name=name):
                self.pack(source_remove=[name])
                with self.assertRaisesRegex(ValueError, 'Source archive mismatch'):
                    release.verify_archives(self.root, self.dist)

    def test_wrong_version_and_mixed_distribution_directory_fail(self):
        self.pack(version='0.2.0')
        with self.assertRaisesRegex(ValueError, 'metadata'):
            release.verify_archives(self.root, self.dist)
        self.pack()
        (self.dist / 'contentmaxxing-0.2.0-py3-none-any.whl').write_bytes(b'old artifact')
        with self.assertRaisesRegex(ValueError, 'dedicated directory'):
            release.verify_archives(self.root, self.dist)

    def test_creator_data_and_stale_runtime_files_cannot_sneak_into_archives(self):
        for change in ({'source_add': {'data/creator/private.json': b'{}'}},
                       {'wheel_add': {'contentmaxxing/stale.py': b'# stale'}},
                       {'wheel_add': {'other_package/__init__.py': b''}}):
            with self.subTest(change=change):
                self.pack(**change)
                with self.assertRaises(ValueError):
                    release.verify_archives(self.root, self.dist)

    def test_runtime_and_project_version_cannot_diverge(self):
        (self.root / 'contentmaxxing/__init__.py').write_text('__version__ = "0.2.0"\n')
        with self.assertRaisesRegex(ValueError, 'versions must agree'):
            release.project_version(self.root)

    def test_tag_requires_matching_version_existing_commit_and_clean_tree(self):
        def responses(commit='a' * 40, target='a' * 40, status=''):
            def run(argv, **kwargs):
                value = status if 'status' in argv else target if argv[-1].startswith('refs/tags/') else commit
                return subprocess.CompletedProcess(argv, 0 if value is not None else 1, value or '', '')
            return run
        with patch.object(release.subprocess, 'run', side_effect=responses()):
            self.assertEqual(release.source_identity(self.root, '0.1.0', 'v0.1.0')['kind'], 'TAGGED_CANDIDATE')
            with self.assertRaisesRegex(ValueError, 'tag must be'):
                release.source_identity(self.root, '0.1.0', 'v0.2.0')
        for case in ({'target': None}, {'target': 'b' * 40}, {'status': ' M README.md'}, {'commit': None}):
            with patch.object(release.subprocess, 'run', side_effect=responses(**case)):
                with self.assertRaisesRegex(ValueError, 'existing tag at HEAD'):
                    release.source_identity(self.root, '0.1.0', 'v0.1.0')

    def test_installed_check_detects_missing_changed_and_extra_bytes(self):
        import contentmaxxing
        fake_package = self.root / 'installed/contentmaxxing'
        fake_package.mkdir(parents=True)
        (fake_package / '__init__.py').write_bytes(self.runtime['contentmaxxing/__init__.py'])
        manifest = {'version': '0.1.0', 'runtime': {'contentmaxxing/__init__.py': release.digest((fake_package / '__init__.py').read_bytes())},
                    'artifacts': [{'file': 'fixture.whl', 'sha256': 'fixture'}]}
        with patch.object(contentmaxxing, '__file__', str(fake_package / '__init__.py')):
            self.assertEqual(release.verify_installed(manifest, self.root)['status'], 'passed')
            (fake_package / '__init__.py').write_text('changed bytes')
            with self.assertRaisesRegex(ValueError, 'Installed runtime mismatch'):
                release.verify_installed(manifest, self.root)
            (fake_package / '__init__.py').unlink()
            with self.assertRaisesRegex(ValueError, 'Installed runtime mismatch'):
                release.verify_installed(manifest, self.root)
            (fake_package / '__init__.py').write_bytes(self.runtime['contentmaxxing/__init__.py'])
            (fake_package / 'stale.py').write_text('# stale')
            with self.assertRaisesRegex(ValueError, 'Installed runtime mismatch'):
                release.verify_installed(manifest, self.root)
        with patch.object(contentmaxxing, '__file__', str(self.root / 'contentmaxxing/__init__.py')):
            with self.assertRaisesRegex(ValueError, 'non-editable'):
                release.verify_installed(manifest, self.root)


if __name__ == '__main__':
    unittest.main()
