"""Inspectable JSON records. No database or provider-specific state is required."""
import hashlib
import json
import os
import re
import shutil
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
import yaml

PACKAGE = Path(__file__).parent
COLLECTIONS = {'sources': 'source', 'ideas': 'idea', 'content': 'content-item',
               'analytics': 'analytics', 'reports': 'weekly-report', 'experiments': 'experiment',
               'feedback': 'creator-feedback', 'mining': 'mining-run', 'revisions': 'revision'}
RECORD_ID = re.compile(r'[a-z]+_[a-f0-9]{12}')


def now():
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix):
    return prefix + '_' + uuid.uuid4().hex[:12]


def record(prefix):
    timestamp = now()
    return {'id': new_id(prefix), 'created_at': timestamp, 'updated_at': timestamp}


def atomic_text(path, text):
    atomic_bytes(path, text.encode('utf-8'))


def atomic_bytes(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.' + path.name, dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def atomic_json(path, value):
    atomic_text(path, json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def normalize(value):
    return ' '.join(re.findall(r'\w+', value.casefold()))


class Store:
    def __init__(self, workspace):
        self.root = Path(workspace).resolve()
        self.data = self.root / 'data'
        self.assets = self.root / '.contentmaxxing'
        self._lock_depth = 0

    def init(self, provider='external', timezone_name='UTC'):
        from zoneinfo import ZoneInfo
        from .workspace_assets import initial_assets
        ZoneInfo(timezone_name)
        if (self.root / 'config.yaml').exists():
            raise ValueError('Workspace already initialized; existing creator data was preserved.')
        # Establish the exact bundled baseline before creating creator state.
        initial_assets(self, PACKAGE)
        self.root.mkdir(parents=True, exist_ok=True)
        for folder in list(COLLECTIONS) + ['creator', 'tasks', 'runs']:
            (self.data / folder).mkdir(parents=True, exist_ok=True)
        workflows = yaml.safe_load((self.assets / 'config/workflows.yaml').read_text())
        workflows['timezone'] = timezone_name
        atomic_text(self.root / 'workflows.yaml', yaml.safe_dump(workflows, sort_keys=False))
        config = {'version': 1, 'timezone': timezone_name, 'provider': provider,
                  'model': '', 'base_url': 'https://api.openai.com/v1',
                  'api_key_env': 'CONTENTMAXXING_API_KEY', 'article_words': [700, 1000],
                  'x_max_chars': 280, 'review_first': True,
                  'retrieval': {'draft_source_chars': 16000, 'draft_source_passages': 12},
                  'feedback': {'max_context_chars': 8000},
                  'voice': {'sample_chars': 16000, 'max_samples': 24, 'document_chars': 40000},
                  'editorial': {'candidate_limit': 48, 'candidate_chars': 40000, 'experiment_chars': 16000},
                  'compound': {'max_opportunities': 6, 'related_source_chars': 8000},
                  'mining': {'chunk_chars': 16000, 'overlap_chars': 800, 'chunks_per_call': 3, 'idea_context_chars': 12000},
                  'winner': {'minimum_peers': 3, 'minimum_impressions': 100, 'multiplier': 1.5},
                  'typefully_social_set_id': None}
        atomic_text(self.root / 'config.yaml', yaml.safe_dump(config, sort_keys=False))
        atomic_text(self.data / 'creator/LEARNINGS.md', '# Learnings\n\nNo measured learnings yet.\n')
        if not (self.root / 'AGENTS.md').exists():
            atomic_text(self.root / 'AGENTS.md', '# CONTENTMAXXING workspace\n\nWhen the creator says “kick off my content engine”, “get me started”, or “start Contentmaxxing”, read `.contentmaxxing/skills/kickoff/SKILL.md` and run the guided launch conversation. Handle files and CLI tasks yourself; ask the creator only for their context, source material and editorial decisions.\n\nFor other requests, read `.contentmaxxing/orchestrator.md` and route to the relevant skill. Use `contentmaxxing --workspace .` for persistence. Creator documents and data are authoritative. Never invent evidence or bypass review.\n')
        if not (self.root / 'START_HERE.md').exists():
            shutil.copy2(PACKAGE / 'START_HERE.md', self.root / 'START_HERE.md')
        return config

    @property
    def config(self):
        path = self.root / 'config.yaml'
        if not path.exists():
            raise ValueError('Run contentmaxxing init first.')
        return yaml.safe_load(path.read_text(encoding='utf-8'))

    @property
    def registry(self):
        return json.loads((self.assets / 'config/formats.json').read_text(encoding='utf-8'))

    @contextmanager
    def lock(self):
        """Portable single-writer lock. Do not steal locks from possibly live writers."""
        if self._lock_depth:
            self._lock_depth += 1
            try:
                yield
            finally:
                self._lock_depth -= 1
            return
        self.config
        path = self.root / '.writer.lock'
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            raise ValueError('Workspace busy: .writer.lock exists. After a crash, verify no writer is running before removing it.')
        try:
            with os.fdopen(fd, 'w') as stream:
                stream.write(str(os.getpid()))
            self._lock_depth = 1
            yield
        finally:
            self._lock_depth = 0
            path.unlink()

    def validate(self, schema, value):
        path = self.assets / 'schemas' / (schema + '.schema.json')
        # New optional collections work in older workspaces without replacing
        # their intelligence snapshot or any creator-customized schema.
        if schema in ('creator-feedback', 'mining-run', 'revision') and not path.exists():
            path = PACKAGE / 'schemas' / (schema + '.schema.json')
        definition = json.loads(path.read_text())
        if schema == 'idea' and 'development' in value and 'development' not in definition['properties']:
            # One known optional extension works with older snapshots without
            # replacing their existing field constraints or editing schema files.
            definition['properties']['development'] = json.loads(
                (PACKAGE / 'schemas/idea.schema.json').read_text())['properties']['development']
        Draft202012Validator(definition, format_checker=FormatChecker()).validate(value)

    def path(self, collection, identifier):
        if collection not in set(COLLECTIONS) | {'tasks', 'runs'}:
            raise ValueError('Unknown collection: ' + collection)
        if not RECORD_ID.fullmatch(identifier):
            raise ValueError('Invalid record ID: ' + identifier)
        return self.data / collection / (identifier + '.json')

    def get(self, collection, identifier):
        path = self.path(collection, identifier)
        if not path.exists():
            raise ValueError('Unknown ' + collection + ' ID: ' + identifier)
        return json.loads(path.read_text(encoding='utf-8'))

    def list(self, collection):
        if collection not in set(COLLECTIONS) | {'tasks', 'runs'}:
            raise ValueError('Unknown collection')
        records = []
        for path in (self.data / collection).glob('*.json'):
            # Agents may leave import results or other working files beside records.
            # Only the same ID filenames accepted by put/get belong to a collection.
            if not RECORD_ID.fullmatch(path.stem):
                continue
            value = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(value, dict) or value.get('id') != path.stem:
                raise ValueError('Record ID does not match filename: ' + str(path))
            records.append(value)
        return sorted(records, key=lambda x: (x.get('created_at', ''), x['id']))

    def put(self, collection, value):
        if collection in COLLECTIONS:
            self.validate(COLLECTIONS[collection], value)
        value['updated_at'] = now()
        atomic_json(self.path(collection, value['id']), value)
        if collection == 'content':
            atomic_text(self.data / 'content' / (value['id'] + '.md'),
                        '# ' + (value['title'] or value['topic']) + '\n\n' + value['body'] + '\n')
        return value

    def source_text(self, source_id):
        source = self.get('sources', source_id)
        path = (self.root / source['path']).resolve()
        if self.data / 'sources' not in path.parents:
            raise ValueError('Source path escapes workspace')
        text = path.read_bytes().decode('utf-8')
        if hashlib.sha256(text.encode('utf-8')).hexdigest() != source['sha256']:
            raise ValueError('Original source changed; capture a new revision instead: ' + source_id)
        return text

    def validate_reference(self, ref):
        text = self.source_text(ref['source_id'])
        lines = text.splitlines()
        start, end = ref['start_line'], ref['end_line']
        if not 1 <= start <= end <= len(lines):
            raise ValueError('Source line range is invalid')
        quoted = ref['quote'].replace('\r\n', '\n').replace('\r', '\n')
        if not quoted.strip() or quoted not in '\n'.join(lines[start - 1:end]):
            raise ValueError('Source quote does not match the cited lines')
        return ref

    def brain(self):
        profile = self.data / 'creator/profile.json'
        if not profile.exists():
            raise ValueError('Onboard the creator first.')
        return {p.name: p.read_text(encoding='utf-8') for p in (self.data / 'creator').glob('*.md')}
