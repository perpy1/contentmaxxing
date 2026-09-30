"""Portable bulk intake and cited profile proposals; no provider-specific reasoning."""
import hashlib
import json
import os
from collections import Counter
from pathlib import Path

from jsonschema import Draft202012Validator

from .store import atomic_json, atomic_bytes, now

TEXT_SUFFIXES = {'.txt', '.md', '.markdown', '.csv', '.json', '.jsonl', '.srt', '.vtt'}
EXCLUDED_DIRS = {'node_modules', '__pycache__', 'data', 'build', 'dist'}
MAX_FILE_BYTES = 50 * 1024 * 1024


class Intake:
    def __init__(self, store):
        self.store = store
        self.path = store.data / 'creator/intake-manifest.json'

    def manifest(self):
        return json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else {'version': 1, 'entries': []}

    def ingest(self, paths):
        manifest = self.manifest()
        entries = manifest['entries']
        accepted = {entry['sha256']: entry for entry in entries if entry['status'] == 'READY'}
        candidates = []
        for supplied in paths:
            path = Path(supplied).expanduser()
            if path.is_dir() and not path.is_symlink():
                for directory, folders, files in os.walk(path, followlinks=False):
                    parent = Path(directory)
                    for name in list(folders):
                        child = parent / name
                        if name.startswith('.') or name in EXCLUDED_DIRS or child.is_symlink():
                            candidates.append((child, 'SKIPPED', 'Hidden, generated, or symlinked directory.', str(child.relative_to(path))))
                            folders.remove(name)
                    for name in sorted(files):
                        child = parent / name
                        candidates.append((child, None, None, str(child.relative_to(path))))
            else:
                candidates.append((path, None, None, path.name))
        for path, status, reason, label in candidates:
            entry = {'name': label, 'status': status, 'reason': reason, 'path': None, 'sha256': None}
            try:
                if status:
                    pass
                elif path.is_symlink() or path.name.startswith('.'):
                    entry.update(status='SKIPPED', reason='Hidden files and symlinks are not imported.')
                elif path.suffix.lower() not in TEXT_SUFFIXES:
                    entry.update(status='UNSUPPORTED', reason='Export text/Markdown first; PDF, DOCX, images, audio and video need extraction or transcription. Original left in place.')
                elif path.stat().st_size > MAX_FILE_BYTES:
                    entry.update(status='TOO_LARGE', reason='Split text files larger than 50 MiB into smaller sources.')
                else:
                    original = path.read_bytes()
                    text = original.decode('utf-8-sig')
                    if not text.strip() or '\x00' in text:
                        entry.update(status='EMPTY' if not text.strip() else 'UNSUPPORTED', reason='Empty or binary-looking text.')
                    else:
                        sha = hashlib.sha256(original).hexdigest()
                        entry['sha256'] = sha
                        if sha in accepted:
                            entry.update(status='DUPLICATE', reason='Identical bytes already preserved.', path=accepted[sha]['path'])
                        else:
                            relative = 'data/inbox/' + sha + '/' + path.name
                            atomic_bytes(self.store.root / relative, original)
                            entry.update(status='READY', reason=None, path=relative)
                            accepted[sha] = entry
            except (OSError, UnicodeDecodeError) as exc:
                entry.update(status='UNREADABLE', reason='Cannot read as UTF-8 text: ' + type(exc).__name__)
            # Repeating a drop should not inflate the inventory with identical entries.
            if entry['status'] == 'DUPLICATE' and any(e['name'] == entry['name'] and e['sha256'] == entry['sha256'] for e in entries):
                continue
            if entry not in entries:
                entries.append(entry)
            manifest['updated_at'] = now()
            atomic_json(self.path, manifest)
        return self.summary()

    def summary(self):
        entries = self.manifest()['entries']
        return {'manifest': 'data/creator/intake-manifest.json',
                'counts': dict(Counter(e['status'] for e in entries)),
                'documents': [e for e in entries if e['status'] == 'READY'],
                'exceptions': [e for e in entries if e['status'] not in ('READY', 'DUPLICATE')]}

    def validate_proposal(self, value):
        profile_schema = json.loads((self.store.assets / 'schemas/creator-profile.schema.json').read_text())
        profile_schema['required'] = []
        reference = {'type': 'object', 'additionalProperties': False,
                     'required': ['field', 'path', 'start_line', 'end_line', 'quote'], 'properties': {
                         'field': {'enum': list(profile_schema['properties'])}, 'path': {'type': 'string'},
                         'start_line': {'type': 'integer', 'minimum': 1}, 'end_line': {'type': 'integer', 'minimum': 1},
                         'quote': {'type': 'string', 'minLength': 1}}}
        schema = {'type': 'object', 'additionalProperties': False,
                  'required': ['profile', 'evidence', 'unknowns', 'conflicts'], 'properties': {
                      'profile': profile_schema, 'evidence': {'type': 'array', 'items': reference},
                      'unknowns': {'type': 'array', 'items': {'type': 'string'}},
                      'conflicts': {'type': 'array', 'items': {'type': 'string'}}}}
        Draft202012Validator(schema).validate(value)
        documents = {entry['path']: entry for entry in self.summary()['documents']}
        supported = set()
        for ref in value['evidence']:
            if ref['path'] not in documents:
                raise ValueError('Profile evidence must cite a preserved intake document.')
            path = (self.store.root / ref['path']).resolve()
            if (self.store.data / 'inbox').resolve() not in path.parents:
                raise ValueError('Profile evidence is outside the inbox.')
            original = path.read_bytes()
            if hashlib.sha256(original).hexdigest() != documents[ref['path']]['sha256']:
                raise ValueError('Intake evidence changed; restore the preserved source.')
            lines = original.decode('utf-8-sig').splitlines()
            if ref['start_line'] > ref['end_line'] or ref['end_line'] > len(lines) or ref['quote'] not in '\n'.join(lines[ref['start_line'] - 1:ref['end_line']]):
                raise ValueError('Profile evidence quote does not match its source lines.')
            supported.add(ref['field'])
        missing = {field for field, val in value['profile'].items() if val} - supported
        if missing:
            raise ValueError('Profile proposal needs source evidence for: ' + ', '.join(sorted(missing)))
        return value
