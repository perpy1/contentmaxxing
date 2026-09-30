"""Verify distributable bytes, source identity and the installed runtime.

Archive verification requires Python 3.11+ or the development-only tomli package.
Installed verification runs on every supported runtime. This never publishes.
"""
import argparse
import ast
import hashlib
import importlib.metadata
import json
import subprocess
import tarfile
import zipfile
from email.parser import BytesParser
from pathlib import Path, PurePosixPath


ROOT_FILES = ('pyproject.toml', 'requirements-dev.txt', 'MANIFEST.in', 'README.md',
              'AGENTS.md', 'CLAUDE.md', 'START_HERE.md', 'LICENSE',
              'IMPLEMENTATION_PLAN.md', 'VERIFICATION.json', 'PROJECT.md',
              'STATUS.md', 'DECISIONS.md', 'CONTRIBUTING.md', 'CHANGELOG.md')
SOURCE_DIRS = ('docs', 'examples', 'scripts', 'tests', 'providers', 'connectors',
               'scheduler', 'cli', '.github')
SUFFIXES = {'.py', '.md', '.json', '.txt', '.yaml', '.yml', '.png'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def files_under(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in sorted(root.rglob('*'))
            if p.is_file() and p.suffix in SUFFIXES and '__pycache__' not in p.parts}


def project_version(project):
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib
    config = tomllib.loads((project / 'pyproject.toml').read_text())
    version = config['project']['version']
    tree = ast.parse((project / 'contentmaxxing/__init__.py').read_text())
    versions = [ast.literal_eval(node.value) for node in tree.body
                if isinstance(node, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == '__version__' for t in node.targets)]
    if config['project']['name'] != 'contentmaxxing' or versions != [version]:
        raise ValueError('Project and runtime names/versions must agree.')
    return version


def source_identity(project, version, tag=None):
    def git(*args):
        result = subprocess.run(['git', '-C', str(project), *args], capture_output=True, text=True)
        return result.stdout.strip() if result.returncode == 0 else None
    commit = git('rev-parse', '--verify', 'HEAD')
    status = git('status', '--porcelain', '--untracked-files=all')
    dirty = status != ''
    if tag is not None:
        if tag != 'v' + version:
            raise ValueError('Release tag must be v' + version)
        target = git('rev-parse', '--verify', 'refs/tags/' + tag + '^{commit}')
        if not commit or target != commit or dirty:
            raise ValueError('Release requires an existing tag at HEAD and a clean worktree.')
    return {'commit': commit, 'dirty': dirty, 'tag': tag,
            'kind': 'TAGGED_CANDIDATE' if tag else 'LOCAL_CANDIDATE'}


def compare(expected, actual, label, exact=False):
    missing = sorted(set(expected) - set(actual))
    changed = sorted(k for k in expected.keys() & actual.keys() if expected[k] != actual[k])
    extra = sorted(set(actual) - set(expected)) if exact else []
    if missing or changed or extra:
        raise ValueError('{} mismatch: missing={}, changed={}, extra={}'.format(label, missing, changed, extra))


def check_metadata(data, version, label):
    metadata = BytesParser().parsebytes(data)
    if metadata['Name'] != 'contentmaxxing' or metadata['Version'] != version:
        raise ValueError(label + ' metadata does not match project name/version.')


def verify_archives(project, directory, tag=None):
    project, directory = Path(project).resolve(), Path(directory).resolve()
    version = project_version(project)
    wheel = directory / ('contentmaxxing-' + version + '-py3-none-any.whl')
    source = directory / ('contentmaxxing-' + version + '.tar.gz')
    archives = sorted(directory.glob('*.whl')) + sorted(directory.glob('*.tar.gz'))
    if set(archives) != {wheel, source}:
        raise ValueError('Use a dedicated directory containing exactly this version\'s wheel and sdist.')
    runtime = {'contentmaxxing/' + k: v for k, v in files_under(project / 'contentmaxxing').items()}
    with zipfile.ZipFile(wheel) as archive:
        names = [i.filename for i in archive.infolist() if not i.is_dir()]
        if len(names) != len(set(names)):
            raise ValueError('Duplicate wheel members.')
        payload = {name: archive.read(name) for name in names if name.startswith('contentmaxxing/')}
        compare(runtime, payload, 'Wheel runtime', exact=True)
        check_metadata(archive.read('contentmaxxing-' + version + '.dist-info/METADATA'), version, 'Wheel')
        unexpected = [n for n in names if n not in runtime
                      and not n.startswith('contentmaxxing-' + version + '.dist-info/')]
        if unexpected:
            raise ValueError('Unexpected wheel files: ' + repr(unexpected))
    required = dict(runtime)
    required.update({name: (project / name).read_bytes() for name in ROOT_FILES})
    for folder in SOURCE_DIRS:
        required.update({folder + '/' + k: v for k, v in files_under(project / folder).items()})
    prefix = 'contentmaxxing-' + version + '/'
    with tarfile.open(source) as archive:
        packed = {}
        for member in archive.getmembers():
            if member.isdir():
                continue
            if (not member.isfile() or not member.name.startswith(prefix)
                    or '..' in PurePosixPath(member.name).parts):
                raise ValueError('Invalid source archive member: ' + member.name)
            relative = member.name[len(prefix):]
            if relative in packed:
                raise ValueError('Duplicate source archive member: ' + member.name)
            packed[relative] = archive.extractfile(member).read()
        compare(required, packed, 'Source archive')
        check_metadata(packed['PKG-INFO'], version, 'Source archive')
        extras = [n for n in packed if n not in required and n not in ('PKG-INFO', 'setup.cfg')
                  and not n.startswith('contentmaxxing.egg-info/')]
        if extras:
            raise ValueError('Unexpected source files: ' + repr(extras))
    return {'version': version, 'source': source_identity(project, version, tag),
            'artifacts': [{'file': p.name, 'sha256': digest(p.read_bytes()), 'bytes': p.stat().st_size}
                          for p in (wheel, source)],
            'runtime': {name: digest(data) for name, data in sorted(runtime.items())},
            'checks': {'archive_contents': 'passed', 'metadata_versions': 'passed'},
            'notice': 'Artifact integrity only. Test results and creator quality review are separate evidence.'}


def verify_installed(manifest, project):
    import contentmaxxing
    package = Path(contentmaxxing.__file__).resolve().parent
    if package == Path(project).resolve() / 'contentmaxxing':
        raise ValueError('Use a non-editable wheel installation, outside the source checkout.')
    if (importlib.metadata.version('contentmaxxing') != manifest['version']
            or contentmaxxing.__version__ != manifest['version']):
        raise ValueError('Installed version differs from the candidate.')
    actual = {'contentmaxxing/' + name: digest(data) for name, data in files_under(package).items()}
    compare(manifest['runtime'], actual, 'Installed runtime', exact=True)
    return {'package': str(package), 'version': manifest['version'],
            'runtime_files': len(actual), 'status': 'passed',
            'wheel_sha256': next(a['sha256'] for a in manifest['artifacts'] if a['file'].endswith('.whl'))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=Path(__file__).resolve().parents[1])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--dist', type=Path)
    mode.add_argument('--installed', type=Path, help='Candidate ARTIFACTS.json to compare with installed bytes')
    parser.add_argument('--tag', help='Require this existing clean tag at HEAD (v plus package version)')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        if args.installed and args.tag:
            parser.error('--tag applies to archive verification only')
        result = (verify_installed(json.loads(args.installed.read_text()), args.project) if args.installed
                  else verify_archives(args.project, args.dist, args.tag))
    except (ValueError, KeyError, OSError) as exc:
        parser.exit(1, 'Release verification failed: ' + str(exc) + '\n')
    text = json.dumps(result, indent=2) + '\n'
    if args.output:
        args.output.write_text(text)
        if args.dist:
            (args.output.parent / 'SHA256SUMS').write_text(''.join(
                a['sha256'] + '  ' + a['file'] + '\n' for a in result['artifacts']))
    print(text, end='')


if __name__ == '__main__':
    main()
