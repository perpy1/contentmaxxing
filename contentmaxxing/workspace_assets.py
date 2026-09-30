"""Upgrade portable workspace intelligence without replacing creator customizations."""
import difflib
import json
import re
from pathlib import Path

from . import __version__
from .installation import digest, safe_path
from .store import PACKAGE, atomic_bytes, atomic_json, new_id

FOLDERS = ('skills', 'schemas', 'templates', 'prompts', 'config', 'commands', 'assets')
DOCUMENTS = ('orchestrator.md', 'WELCOME.md')
MANIFEST = 'intelligence-manifest.json'
HASH = re.compile(r'[0-9a-f]{64}')


def asset_name(name):
    if not isinstance(name, str):
        return False
    path = Path(name)
    return ('\\' not in name and not path.is_absolute()
            and '..' not in path.parts and path.as_posix() == name
            and (name in DOCUMENTS or (len(path.parts) > 1 and path.parts[0] in FOLDERS
                 and path.suffix in ('.md', '.json', '.yaml', '.png'))))


def bundle(package=PACKAGE):
    files = {}
    for folder in FOLDERS:
        for path in sorted((package / folder).rglob('*')):
            name = path.relative_to(package).as_posix()
            if path.is_file() and asset_name(name):
                files[name] = path.read_bytes()
    for name in DOCUMENTS:
        files[name] = (package / name).read_bytes()
    return files


def initial_assets(store, package=PACKAGE):
    """Called only for a new workspace; never adopt pre-existing intelligence."""
    root = safe_path(store.root, '.contentmaxxing')
    if root.exists() and (not root.is_dir() or any(root.iterdir())):
        raise ValueError('Existing .contentmaxxing files preserved; use the original workspace or a new empty folder.')
    files = bundle(package)
    for name, content in files.items():
        atomic_bytes(safe_path(root, name), content)
    atomic_json(root / MANIFEST, {'manifest_version': 1, 'engine_version': __version__,
                                'files': {name: digest(value) for name, value in files.items()}})


class WorkspaceUpgrade:
    def __init__(self, store, package=PACKAGE):
        self.store = store
        self.root = safe_path(store.root, '.contentmaxxing')
        self.package = package

    def path(self, name):
        if name != MANIFEST and not asset_name(name):
            raise ValueError('Invalid intelligence asset: ' + str(name))
        return safe_path(self.root, name)

    def read(self, name):
        path = self.path(name)
        if path.exists() and not path.is_file():
            raise ValueError('Expected an intelligence file: ' + name)
        return path.read_bytes() if path.exists() else None

    def manifest(self):
        raw = self.read(MANIFEST)
        if raw is None:
            return None
        value = json.loads(raw)
        if not isinstance(value, dict) or value.get('manifest_version') != 1 or not isinstance(value.get('files'), dict):
            raise ValueError('Invalid workspace intelligence manifest.')
        for name, checksum in value['files'].items():
            if not asset_name(name) or not isinstance(checksum, str) or not HASH.fullmatch(checksum):
                raise ValueError('Invalid intelligence manifest entry: ' + str(name))
            self.path(name)
        return value

    def pending(self):
        root = safe_path(self.root, 'updates')
        result = []
        for path in sorted(root.glob('upgrade_*/report.json')):
            path = safe_path(self.root, path.relative_to(self.root))
            report = json.loads(path.read_text(encoding='utf-8'))
            if report.get('status') == 'PREPARED':
                result.append(path.parent.name)
        return result

    def plan(self, accept=(), adopt_matching=False):
        previous = self.manifest()
        owned = previous['files'] if previous else {}
        wanted = bundle(self.package)
        accepted = {}
        for item in accept:
            name, separator, token = item.rpartition('=')
            if not separator or not asset_name(name) or not HASH.fullmatch(token) or name in accepted:
                raise ValueError('Use --accept FILE=TOKEN from upgrade --review FILE; each file once.')
            accepted[name] = token
        if set(accepted) - set(wanted):
            raise ValueError('Accepted file is not in this installed bundle.')
        entries, writes, hashes = [], {}, dict(owned)
        for name, value in sorted(wanted.items()):
            current = self.read(name)
            before = digest(current) if current is not None else None
            after = digest(value)
            token = digest(json.dumps([name, before, after]).encode('utf-8'))
            if name in accepted and accepted[name] != token:
                raise ValueError('Review is stale; inspect the current and incoming file again: ' + name)
            if name in accepted:
                action, reason = ('adopt' if current == value else 'update'), 'explicitly_reviewed'
            elif current == value and name in owned and before == owned[name]:
                action, reason = 'unchanged', 'tracked'
            elif current == value and adopt_matching:
                action, reason = 'adopt', 'exact_match'
            elif name not in owned and current is None:
                action, reason = 'create', 'new_asset'
            elif name in owned and before == owned[name]:
                action, reason = 'update', 'unchanged_since_install'
            else:
                action = 'preserve'
                reason = 'locally_deleted' if current is None else ('locally_edited' if name in owned else 'untracked')
            if action in ('create', 'update', 'adopt', 'unchanged'):
                hashes[name] = after
                if current != value:
                    writes[name] = value
            entries.append({'file': name, 'action': action, 'reason': reason,
                            'current_sha256': before, 'incoming_sha256': after,
                            'accept_token': token})
        for name in sorted(set(owned) - set(wanted)):
            self.read(name)  # reject unsafe retired paths too
            entries.append({'file': name, 'action': 'preserve', 'reason': 'retired_from_bundle'})
        manifest = {'manifest_version': 1, 'engine_version': __version__, 'files': hashes}
        if previous != manifest:
            writes[MANIFEST] = (json.dumps(manifest, indent=2, ensure_ascii=False) + '\n').encode('utf-8')
        return {'engine_version': __version__, 'legacy_workspace': previous is None,
                'files': entries, 'write': sorted(name for name in writes if name != MANIFEST),
                'manifest_changes': MANIFEST in writes,
                'preserved': [row['file'] for row in entries if row['action'] == 'preserve'],
                'pending_recovery': self.pending()}, writes

    def review(self, name):
        self.path(name)
        result, _ = self.plan()
        row = next((row for row in result['files'] if row['file'] == name), None)
        if not row or 'incoming_sha256' not in row:
            raise ValueError('No incoming bundle asset: ' + name)
        before, after = self.read(name) or b'', bundle(self.package)[name]
        try:
            diff = ''.join(difflib.unified_diff(before.decode('utf-8').splitlines(keepends=True),
                                              after.decode('utf-8').splitlines(keepends=True),
                                              fromfile='workspace/' + name, tofile='incoming/' + name))
        except UnicodeDecodeError:
            diff = None
        return {**row, 'diff': diff, 'current_path': str(self.path(name)),
                'incoming_path': str(self.package / name),
                'accept': name + '=' + row['accept_token'],
                'note': 'Accept replaces this entire file with the incoming version. Merge customizations manually if needed.'}

    def run(self, dry_run=False, accept=(), adopt_matching=False):
        self.store.config
        if dry_run:
            result, _ = self.plan(accept, adopt_matching)
            return {**self.summary(result), 'dry_run': True}
        with self.store.lock():
            result, writes = self.plan(accept, adopt_matching)
            result = self.summary(result)
            if result['pending_recovery']:
                raise ValueError('An interrupted upgrade needs recovery first: upgrade --recover ' + result['pending_recovery'][0])
            if not writes:
                return {**result, 'dry_run': False, 'upgrade_id': None}
            identifier = new_id('upgrade')
            journal = safe_path(self.root, 'updates/' + identifier)
            before, after = {}, {}
            for name, value in writes.items():
                current = self.read(name)
                before[name] = digest(current) if current is not None else None
                after[name] = digest(value)
                if current is not None:
                    atomic_bytes(safe_path(journal, 'before/' + name), current)
            report = {'id': identifier, 'status': 'PREPARED', 'before': before, 'after': after, 'plan': result}
            atomic_json(journal / 'report.json', report)
            try:
                # The manifest is last: it never advertises files not yet written.
                for name in sorted(writes, key=lambda name: (name == MANIFEST, name)):
                    atomic_bytes(self.path(name), writes[name])
                report['status'] = 'APPLIED'
                atomic_json(journal / 'report.json', report)
            except (OSError, ValueError):
                self._recover(identifier)
                raise
            return {**result, 'dry_run': False, 'upgrade_id': identifier,
                    'report': '.contentmaxxing/updates/' + identifier + '/report.json'}

    @staticmethod
    def summary(plan):
        return {**plan, 'unchanged': sum(row['action'] == 'unchanged' for row in plan['files']),
                'files': [row for row in plan['files'] if row['action'] != 'unchanged']}

    def recover(self, identifier):
        with self.store.lock():
            return self._recover(identifier)

    def _recover(self, identifier):
        if not re.fullmatch(r'upgrade_[a-f0-9]{12}', identifier):
            raise ValueError('Invalid upgrade ID.')
        journal = safe_path(self.root, 'updates/' + identifier)
        report_path = safe_path(journal, 'report.json')
        if not report_path.is_file():
            raise ValueError('Unknown upgrade ID: ' + identifier)
        report = json.loads(report_path.read_text(encoding='utf-8'))
        if report.get('id') != identifier or report.get('status') not in ('PREPARED', 'APPLIED', 'ROLLED_BACK'):
            raise ValueError('Invalid upgrade recovery report.')
        if report['status'] != 'PREPARED':
            return {'upgrade_id': identifier, 'status': report['status'], 'restored': []}
        before, after = report.get('before'), report.get('after')
        if not isinstance(before, dict) or not isinstance(after, dict) or not before or set(before) != set(after):
            raise ValueError('Invalid upgrade recovery files.')
        restores = {}
        for name, checksum in before.items():
            if (checksum is not None and (not isinstance(checksum, str) or not HASH.fullmatch(checksum))) or not isinstance(after[name], str) or not HASH.fullmatch(after[name]):
                raise ValueError('Invalid upgrade recovery checksum.')
            current = self.read(name)
            current_hash = digest(current) if current is not None else None
            if current_hash not in (checksum, after[name]):
                raise ValueError('Recovery preserved a newer edit; resolve before retrying: ' + name)
            saved = safe_path(journal, 'before/' + name)
            value = saved.read_bytes() if checksum is not None else None
            if value is not None and digest(value) != checksum:
                raise ValueError('Upgrade backup changed; refusing recovery: ' + name)
            if current_hash != checksum:
                restores[name] = value
        for name, value in restores.items():
            if value is None:
                self.path(name).unlink()
            else:
                atomic_bytes(self.path(name), value)
        report['status'] = 'ROLLED_BACK'
        atomic_json(report_path, report)
        return {'upgrade_id': identifier, 'status': 'ROLLED_BACK', 'restored': sorted(restores)}
