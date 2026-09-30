"""Native host entrypoints rendered from one portable command catalog.

Installation never initializes a creator, changes host settings, or edits AGENTS.md.
Only hash-owned files can be updated/removed; edited files require manual resolution.
"""
import hashlib
import json
import os
import re
import sys
from contextlib import contextmanager
from pathlib import Path

from . import __version__
from .store import PACKAGE, atomic_json, atomic_text, atomic_bytes

HOSTS = ('codex', 'claude', 'cursor', 'gemini', 'generic')
SKILL_ROOTS = {'codex': '.agents/skills', 'claude': '.claude/skills', 'cursor': '.cursor/skills'}


def catalog():
    commands = json.loads((PACKAGE / 'config/commands.json').read_text(encoding='utf-8'))
    names = set()
    for command in commands:
        name = command['name']
        if not re.fullmatch(r'[a-z][a-z-]*', name) or name in names:
            raise ValueError('Invalid or duplicate command name: ' + name)
        names.add(name)
        if not (PACKAGE / 'commands' / (name + '.md')).is_file():
            raise ValueError('Missing command procedure: ' + name)
        for skill in command['skills']:
            if not (PACKAGE / 'skills' / skill / 'SKILL.md').is_file():
                raise ValueError('Missing routed skill: ' + skill)
    return commands


def invocation(host, name=None):
    if host not in HOSTS:
        raise ValueError('Unknown agent: ' + host)
    if host == 'generic':
        return 'contentmaxxing' + (' ' + name if name else '')
    if host == 'gemini':
        return '/contentmaxxing' + (':' + name if name else '')
    return ('$' if host == 'codex' else '/') + 'contentmaxxing' + ('-' + name if name else '')


def menu(host):
    return [{'command': invocation(host, c['name']), **c} for c in catalog()]


def digest(value):
    return hashlib.sha256(value).hexdigest()


def payload_bytes(value):
    return value.encode('utf-8') if isinstance(value, str) else value


def write_asset(path, value):
    if isinstance(value, str):
        atomic_text(path, value)
    else:
        atomic_bytes(path, value)


def install_root(path=None, scope='project'):
    if scope not in ('project', 'user'):
        raise ValueError('Scope must be project or user.')
    if scope == 'user' and path is not None:
        raise ValueError('--path is for project scope; user scope installs under your home directory.')
    return Path.home().resolve() if scope == 'user' else Path(path or '.').expanduser().resolve()


def safe_path(root, relative):
    """Reject traversal and existing symlinks before reading/writing owned files."""
    relative = Path(relative)
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Unsafe installation path: ' + str(relative))
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError('Installation refuses symlink: ' + str(current))
    return root / relative


def owned_name(host, relative):
    """A manifest cannot grant ownership over creator or unrelated host files."""
    if '\\' in relative or '..' in Path(relative).parts or Path(relative).is_absolute():
        return False
    bundle = '.contentmaxxing-agent/' + host + '/'
    if relative.startswith(bundle + 'core/') or relative == bundle + 'runtime.json':
        return True
    if host in SKILL_ROOTS:
        return bool(re.fullmatch(re.escape(SKILL_ROOTS[host]) +
                                 r'/contentmaxxing(?:-[a-z-]+)?/SKILL\.md', relative))
    if host == 'gemini':
        return relative == '.gemini/commands/contentmaxxing.toml' or bool(
            re.fullmatch(r'\.gemini/commands/contentmaxxing/[a-z-]+\.toml', relative))
    return relative == bundle + 'CONTENTMAXXING.md'


def manifest_path(host):
    if host not in HOSTS:
        raise ValueError('Unknown agent: ' + host)
    return '.contentmaxxing-agent/' + host + '/install.json'


def read_manifest(root, host):
    path = safe_path(root, manifest_path(host))
    if not path.exists():
        return None
    result = json.loads(path.read_text(encoding='utf-8'))
    if result.get('agent') != host or result.get('manifest_version') != 1 or not isinstance(result.get('files'), dict):
        raise ValueError('Invalid CONTENTMAXXING install manifest.')
    for name, checksum in result['files'].items():
        if not owned_name(host, name) or not isinstance(checksum, str) or not re.fullmatch('[0-9a-f]{64}', checksum):
            raise ValueError('Invalid owned file in install manifest: ' + name)
        safe_path(root, name)
    return result


def render(host):
    """No local paths or creator identity are embedded in portable instructions."""
    manifest_path(host)  # validate host
    bundle = Path('.contentmaxxing-agent') / host
    core = bundle / 'core'
    files = {}
    for folder in ('skills', 'schemas', 'templates', 'prompts', 'config', 'commands', 'assets'):
        for path in sorted((PACKAGE / folder).rglob('*')):
            if path.is_file() and path.suffix in ('.md', '.json', '.yaml', '.png'):
                files[(core / path.relative_to(PACKAGE)).as_posix()] = path.read_bytes() if path.suffix == '.png' else path.read_text(encoding='utf-8')
    for name in ('orchestrator.md', 'START_HERE.md', 'WELCOME.md'):
        files[(core / name).as_posix()] = (PACKAGE / name).read_text(encoding='utf-8')
    files[(bundle / 'runtime.json').as_posix()] = json.dumps(
        {'python': sys.executable, 'module': 'contentmaxxing', 'version': __version__,
         'note': 'Machine-local fallback. Reinstall on another machine; creator data stays portable.'}, indent=2) + '\n'
    all_commands = [{'name': None, 'description': 'Build and run your own content engine. Use for Contentmaxxing, creator kickoff, source capture, weekly content, and performance learning.'}] + catalog()
    for command in all_commands:
        name = command['name']
        skill_name = 'contentmaxxing' + ('-' + name if name else '')
        if host in SKILL_ROOTS:
            destination = Path(SKILL_ROOTS[host]) / skill_name / 'SKILL.md'
        elif host == 'gemini':
            destination = Path('.gemini/commands/contentmaxxing') / (name + '.toml') if name else Path('.gemini/commands/contentmaxxing.toml')
        else:
            if name:
                continue
            destination = bundle / 'CONTENTMAXXING.md'
        relative_core = Path(os.path.relpath(core, destination.parent)).as_posix()
        body = '# CONTENTMAXXING\n\n'
        body += ('Core bundle: `' + relative_core + '` **relative to the directory containing this file**.\n'
                 'Resolve that path from this file\'s parent directory before reading it.\n'
                 'Read its `commands/README.md` first, then the selected command procedure.\n'
                 'Use the user\'s current creator workspace; the installation folder is never their creator workspace.\n\n')
        if name in (None, 'start', 'help'):
            body += ('For the first welcome, read `' + relative_core + '/WELCOME.md`. Include its HUD in your reply:\n'
                     'render the local image if supported; otherwise copy the `contentmaxxing welcome` text banner\n'
                     'into a fenced text block. Reading the image yourself does not display it to the creator.\n'
                     'Offer the two onboarding choices in live text. Returning creators resume saved progress.\n\n')
        if name:
            body += 'Run the **' + name + '** procedure at `' + relative_core + '/commands/' + name + '.md`.\n'
        else:
            body += ('Route the user\'s arguments or natural-language intent using `config/commands.json`.\n'
                     'With no requested action, run the read-only `home` CLI operation. Show the current stage,\n'
                     'saved library counts, any decision needed, and ONE recommended next action. For a new\n'
                     'creator show the welcome choices. Keep the full menu for an explicit help request.\n'
                     'Execute the selected procedure under `commands/<name>.md`.\n')
        if name == 'help' or host == 'generic':
            body += '\n| Command | Ability |\n| --- | --- |\n'
            body += ''.join('| `' + row['command'] + '` | ' + row['description'] + ' |\n' for row in menu(host))
        if host == 'claude':
            body += '\nUser arguments: $ARGUMENTS\n'
        if host == 'gemini':
            body += '\nUser arguments: {{args}}\n'
            # JSON basic strings form valid TOML strings, without shell interpolation.
            text = 'description = ' + json.dumps(command['description']) + '\nprompt = ' + json.dumps(body) + '\n'
        elif host == 'generic':
            text = body
        else:
            text = '---\nname: ' + skill_name + '\ndescription: ' + json.dumps(command['description']) + '\n---\n\n' + body
        files[destination.as_posix()] = text
    return files


@contextmanager
def installation_lock(root):
    path = safe_path(root, '.contentmaxxing-agent/.installer.lock')
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError('An installer is already running. After a crash, verify it stopped before removing .installer.lock.')
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(str(os.getpid()))
        yield
    finally:
        path.unlink()


def _install(host, root, scope, dry_run):
    expected = render(host)
    previous = read_manifest(root, host)
    old_files = previous['files'] if previous else {}
    changed, removed, conflicts = [], [], []
    for name in sorted(set(expected) | set(old_files)):
        path = safe_path(root, name)
        if path.exists() and not path.is_file():
            conflicts.append(name)
            continue
        current = path.read_bytes() if path.exists() else None
        wanted = payload_bytes(expected[name]) if name in expected else None
        if current is not None and name not in old_files:
            conflicts.append(name)
            continue
        if current == wanted:
            continue
        if current is not None and digest(current) != old_files.get(name):
            conflicts.append(name)
        elif wanted is None:
            removed.append(name)
        else:
            changed.append(name)
    if conflicts:
        raise ValueError('Preserved locally edited or unowned files; resolve before installing: ' + ', '.join(conflicts))
    result = {'agent': host, 'scope': scope, 'root': str(root), 'dry_run': dry_run,
              'write': changed, 'remove': removed, 'commands': menu(host),
              'welcome': {'document': str(root / '.contentmaxxing-agent' / host / 'core/WELCOME.md'),
                          'image': str(root / '.contentmaxxing-agent' / host / 'core/assets/welcome.png'),
                          'agent_action': 'Show the welcome HUD and offer 1. Curated interview or 2. Mega file dump. Use text HUD when images are unavailable.'},
              'next': 'Open your creator folder in ' + host + ' and invoke ' + invocation(host, 'start') +
                      '. Reload skills or restart the host if needed.'}
    if host == 'generic':
        result['next'] = 'Ask your filesystem-capable AI to read .contentmaxxing-agent/generic/CONTENTMAXXING.md and start your content engine.'
    if scope == 'project' and (root / 'config.yaml').is_file():
        result['workspace_update'] = {'workspace': str(root), 'operation': 'upgrade --dry-run',
            'note': 'Host commands and workspace intelligence update separately. Preview the workspace upgrade; preserve customizations and frozen tasks.'}
    if dry_run:
        return result
    manifest_name = manifest_path(host)
    backup = {name: safe_path(root, name).read_bytes() if safe_path(root, name).is_file() else None
              for name in changed + removed + [manifest_name]}
    try:
        for name in changed:
            write_asset(safe_path(root, name), expected[name])
        for name in removed:
            safe_path(root, name).unlink()
        atomic_json(safe_path(root, manifest_name), {'manifest_version': 1, 'version': __version__,
                    'agent': host, 'scope': scope, 'files': {name: digest(payload_bytes(value)) for name, value in expected.items()}})
    except OSError:
        for name, value in backup.items():
            path = safe_path(root, name)
            if value is None:
                if path.exists():
                    path.unlink()
            else:
                write_asset(path, value)
        raise
    return result


def install(host, path=None, scope='project', dry_run=False):
    root = install_root(path, scope)
    manifest_path(host)
    if dry_run:
        return _install(host, root, scope, True)
    with installation_lock(root):
        return _install(host, root, scope, False)


def uninstall(host, path=None, scope='project', dry_run=False):
    root = install_root(path, scope)

    def perform():
        manifest = read_manifest(root, host)
        removed, preserved = [], []
        if manifest:
            for name, checksum in manifest['files'].items():
                target = safe_path(root, name)
                if not target.exists():
                    continue
                if target.is_file() and digest(target.read_bytes()) == checksum:
                    removed.append(name)
                else:
                    preserved.append(name)
            if not dry_run:
                for name in removed:
                    safe_path(root, name).unlink()
                if preserved:
                    manifest['files'] = {name: manifest['files'][name] for name in preserved}
                    atomic_json(safe_path(root, manifest_path(host)), manifest)
                else:
                    safe_path(root, manifest_path(host)).unlink()
        return {'agent': host, 'dry_run': dry_run, 'removed': removed, 'preserved_edited_files': preserved,
                'creator_data': 'Untouched. Only manifest-owned installation files are eligible for removal.'}

    if dry_run:
        return perform()
    with installation_lock(root):
        return perform()


def doctor(host, path=None, scope='project'):
    root = install_root(path, scope)
    manifest = read_manifest(root, host)
    issues = []
    if not manifest:
        issues.append('Agent commands are not installed in this scope.')
    else:
        for name, checksum in manifest['files'].items():
            target = safe_path(root, name)
            if not target.is_file():
                issues.append('Missing: ' + name)
            elif digest(target.read_bytes()) != checksum:
                issues.append('Locally modified: ' + name)
        missing = set(render(host)) - set(manifest['files'])
        if missing:
            issues.append('Installation is incomplete or from an older catalog; reinstall to add missing files.')
    return {'agent': host, 'root': str(root), 'installed': manifest is not None,
            'integrity_ok': not issues, 'issues': issues, 'engine_version': __version__,
            'host_session_verified': False,
            'next': 'Reload or restart your host, invoke ' + invocation(host, 'help') +
                    ', then ' + invocation(host, 'start') + '. This check validates files, not host discovery.'}
