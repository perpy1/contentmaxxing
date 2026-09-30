"""Sample-backed voice proposals. Creator Markdown stays editable and authoritative."""
import hashlib
import json
import re
from copy import deepcopy

from jsonschema import Draft202012Validator

from .editorial import REFERENCE
from .feedback import Feedback
from .providers import PendingTask
from .retrieval import bounded_integer
from .store import PACKAGE, atomic_json, atomic_text, now, record


OPEN = '<!-- contentmaxxing:voice-observations:start -->'
CLOSE = '<!-- contentmaxxing:voice-observations:end -->'
SAMPLES = {'type': 'array', 'maxItems': 200, 'items': {
    'type': 'object', 'additionalProperties': False,
    'required': ['source_reference', 'platform', 'medium', 'attribution', 'speaker'],
    'properties': {'source_reference': REFERENCE, 'platform': {'type': ['string', 'null']},
        'medium': {'enum': ['writing', 'speech']}, 'attribution': {'const': 'creator'},
        'speaker': {'type': ['string', 'null']}}}}


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def read_text(path):
    # Preserve the creator's exact newlines when adding/replacing our section.
    return path.read_bytes().decode('utf-8') if path.exists() else ''


def link_only(text):
    return bool(re.fullmatch(r'(?:https?://\S+|\[[^\]]*\]\(https?://[^\s)]+\))', text.strip()))


class Voice:
    def __init__(self, engine):
        self.engine, self.store = engine, engine.store
        self.directory = self.store.data / 'creator/voice'
        self.document = self.store.data / 'creator/VOICE.md'

    def path(self, identifier):
        if not re.fullmatch(r'voice_[a-f0-9]{12}', identifier):
            raise ValueError('Invalid voice proposal ID.')
        return self.directory / (identifier + '.json')

    def get(self, identifier):
        path = self.path(identifier)
        if not path.exists():
            raise ValueError('Unknown voice proposal: ' + identifier)
        value = json.loads(read_text(path))
        if value.get('id') != identifier:
            raise ValueError('Voice proposal ID does not match its filename.')
        return value

    def list(self):
        return sorted((self.get(p.stem) for p in self.directory.glob('voice_*.json')),
                      key=lambda p: (p['created_at'], p['id']))

    def save(self, proposal):
        proposal['updated_at'] = now()
        atomic_json(self.path(proposal['id']), proposal)
        preview = ('# Voice proposal: ' + proposal['id'] + '\n\nStatus: ' + proposal['status'] +
            '\n\n' + proposal['analysis']['summary'] + '\n\n' + proposal['block'] +
            '\n\nThis preview is generated from the JSON proposal. Applying preserves text outside '
            'the managed section. Creator-edited observations require manual reconciliation.\n')
        atomic_text(self.path(proposal['id']).with_suffix('.md'), preview)
        return proposal

    def direction(self):
        profile_path = self.store.data / 'creator/profile.json'
        if not profile_path.exists():
            raise ValueError('Onboard the creator first.')
        profile_text = read_text(profile_path)
        profile = json.loads(profile_text)
        feedback = {p: Feedback(self.store).context(p) for p in self.store.registry['platforms']}
        return profile, {'profile_sha256': digest(profile_text), 'feedback': feedback}

    def context(self, selected):
        Draft202012Validator(SAMPLES).validate(selected)
        profile, state = self.direction()
        voice = read_text(self.document)
        config = self.store.config.get('voice', {})
        max_chars = bounded_integer(config.get('sample_chars', 16000), 'voice.sample_chars', 256, 200000)
        limit = bounded_integer(config.get('max_samples', 24), 'voice.max_samples', 1, 200)
        doc_limit = bounded_integer(config.get('document_chars', 40000), 'voice.document_chars', 256, 300000)
        if len(voice) > doc_limit:
            raise ValueError('VOICE.md exceeds voice.document_chars. Deliberately increase the budget or edit the document; it was not truncated.')
        candidates, omitted, seen = [], [], set()
        # Explicitly selected excerpts go first. Never infer ownership from arbitrary sources.
        for index, entry in enumerate(selected):
            ref = entry['source_reference']
            self.store.validate_reference(ref)
            if entry['platform'] is not None and entry['platform'] not in self.store.registry['platforms']:
                raise ValueError('Unknown voice sample platform.')
            if entry['medium'] == 'speech' and not (entry['speaker'] or '').strip():
                raise ValueError('Speech samples require the creator speaker label; select only their turns.')
            source = self.store.get('sources', ref['source_id'])
            candidates.append({'id': 'source:' + str(index), 'text': ref['quote'],
                'origin': ref['source_id'], 'source_reference': deepcopy(ref), 'source_sha256': source['sha256'],
                **{k: entry[k] for k in ('platform', 'medium', 'speaker', 'attribution')}})
        for field in ('writing_samples', 'top_posts', 'articles_newsletters'):
            for index, value in enumerate(profile[field]):
                identifier = 'profile:' + field + ':' + str(index)
                if not value.strip() or link_only(value):
                    omitted.append({'id': identifier, 'reason': 'Empty or link-only; capture the actual creator text.'})
                    continue
                candidates.append({'id': identifier, 'text': value, 'origin': 'text:' + digest(value.strip()),
                    'profile_field': field, 'profile_index': index, 'platform': None,
                    'medium': 'writing', 'speaker': None, 'attribution': 'creator'})
        samples, used = [], 0
        for candidate in candidates:
            key = digest(candidate['text'].strip())
            reason = ('Duplicate text.' if key in seen else
                      'Sample count/character budget; whole sample omitted.' if
                      len(samples) >= limit or used + len(candidate['text']) > max_chars else None)
            seen.add(key)
            if reason:
                omitted.append({'id': candidate['id'], 'reason': reason})
                continue
            candidate['sha256'] = digest(candidate['text'])
            samples.append(candidate)
            used += len(candidate['text'])
        return {'samples': samples, 'coverage': {'supplied': len(samples), 'chars': used,
                    'max_chars': max_chars, 'max_samples': limit, 'omitted': omitted},
            'creator_direction': {k: profile[k] for k in ('name', 'audience', 'desired_tone', 'restrictions')},
            'voice_document': voice, 'base_state': state, 'selected_samples': selected}

    def request(self, selected=None, fresh=False):
        with self.store.lock():
            tasks = [t for t in self.store.list('tasks') if t['operation'] == 'voice']
            pending = [t for t in tasks if t['status'] == 'PENDING']
            if pending:
                task = pending[-1]
                if fresh or (selected is not None and selected != task['inputs']['selected_samples']):
                    raise ValueError('Finish or cancel the pending voice task before changing its sample set.')
                raise PendingTask(task['id'])
            if tasks and not fresh:
                task = tasks[-1]
                if selected is not None and selected != task['inputs']['selected_samples']:
                    raise ValueError('Use voice learn --new to analyze a different sample set.')
                if task['status'] == 'COMPLETED':
                    return self.get(task['result_ids'][0])
                raise ValueError('The last voice task was cancelled; use voice learn --new when ready.')
            if (self.engine.provider_name or self.store.config['provider']) == 'extractive':
                raise ValueError('Extractive mode cannot learn a voice. Use external or openai-compatible.')
            inputs = self.context(selected or [])
            if not inputs['samples']:
                return {'status': 'NEEDS_SAMPLES', 'coverage': inputs['coverage'],
                    'message': 'Add actual creator writing or explicitly select their captured turns. Desired tone is direction, not learned voice; drafting can remain provisional.'}
            schema = self.store.assets / 'schemas/voice-analysis.schema.json'
            contract = json.loads(read_text(schema if schema.exists() else PACKAGE / 'schemas/voice-analysis.schema.json'))
            task = self.engine.task('voice', 'voice', inputs, contract)
            return self.engine.execute(task)[0]

    def validate(self, task, output):
        Draft202012Validator(task['output_contract']).validate(output)
        samples = {s['id']: s for s in task['inputs']['samples']}
        for observation in output['observations']:
            origins = set()
            for ref in observation['evidence']:
                sample = samples.get(ref['sample_id'])
                if not sample or not ref['quote'].strip() or ref['quote'] not in sample['text']:
                    raise ValueError('Voice evidence must quote an exact supplied sample.')
                if observation['medium'] != sample['medium']:
                    raise ValueError('Do not turn speech evidence into an observed writing rule.')
                if observation['platform'] is not None and observation['platform'] != sample['platform']:
                    raise ValueError('A platform observation needs samples explicitly attributed to that platform.')
                origins.add(sample['origin'])
            if observation['certainty'] == 'recurring' and len(origins) < 2:
                raise ValueError('Recurring voice patterns need at least two independent samples; otherwise mark tentative.')
        # Markers delimit engine-owned text; sample/model text cannot create nested sections.
        if OPEN in json.dumps(output) or CLOSE in json.dumps(output):
            raise ValueError('Voice output contains reserved section markers.')

    def block(self, identifier, task, output):
        lines = [OPEN, '## Sample-backed voice observations', '', 'Proposal: `' + identifier + '`', '',
                 output['summary'], '', 'Creator corrections and manual guidance take precedence. '
                 'These observations do not establish biography, proof or universal preferences.', '']
        for observation in output['observations']:
            scope = observation['platform'] or 'platform unspecified; verify before transferring'
            lines += ['### ' + observation['dimension'].title(), '',
                observation['certainty'].title() + ' · ' + observation['medium'] + ' · ' + scope, '',
                'Observed: ' + observation['pattern'], '', 'Use: ' + observation['guidance'], '', 'Evidence:']
            for ref in observation['evidence']:
                lines += ['- `' + ref['sample_id'] + '`: ' + json.dumps(ref['quote'], ensure_ascii=False)]
            lines += ['']
        for key in ('unknowns', 'conflicts'):
            lines += ['### ' + key.title(), ''] + (['- ' + x for x in output[key]] or ['None reported.']) + ['']
        coverage = task['inputs']['coverage']
        lines += ['Coverage: ' + str(coverage['supplied']) + ' supplied samples; ' +
                  str(len(coverage['omitted'])) + ' omitted entries. Full frozen evidence and omissions: '
                  '`data/tasks/' + task['id'] + '.json`.', CLOSE]
        return '\n'.join(lines)

    def complete(self, task, output):
        identifier = 'voice_' + task['id'][5:]
        if self.path(identifier).exists():
            proposal = self.get(identifier)
            if proposal['task_id'] != task['id']:
                raise ValueError('Voice proposal belongs to another task.')
        else:
            self.validate(task, output)
            proposal = {**record('voice'), 'id': identifier, 'task_id': task['id'], 'status': 'PROPOSED',
                'analysis': deepcopy(output), 'block': self.block(identifier, task, output),
                'before': task['inputs']['voice_document'], 'after': None, 'applied_at': None,
                'dismissal_reason': None}
        self.save(proposal)  # Also repairs a missing preview after a partial write.
        task.update(status='COMPLETED', result_ids=[identifier], error=None)
        self.store.put('tasks', task)
        return proposal

    def current_evidence(self, task):
        _, state = self.direction()
        if state != task['inputs']['base_state']:
            raise ValueError('Voice proposal is stale: profile or creator feedback changed. Learn again with --new.')
        for sample in task['inputs']['samples']:
            if 'source_reference' in sample:
                self.store.validate_reference(sample['source_reference'])
                if self.store.get('sources', sample['source_reference']['source_id'])['sha256'] != sample['source_sha256']:
                    raise ValueError('Voice sample source changed. Learn again from the new source.')

    def replacement(self, proposal):
        before, block = proposal['before'], proposal['block']
        if OPEN not in before and CLOSE not in before:
            return before + ('\n\n' if before else '') + block + '\n'
        if before.count(OPEN) != 1 or before.count(CLOSE) != 1 or before.index(CLOSE) < before.index(OPEN):
            raise ValueError('Voice observation markers were edited. Reconcile the section manually; VOICE.md was preserved.')
        start, end = before.index(OPEN), before.index(CLOSE) + len(CLOSE)
        existing = before[start:end]
        if not any(p['status'] == 'APPLIED' and p['block'] == existing for p in self.list()):
            raise ValueError('Voice observations were edited by the creator. Reconcile them manually before replacing this section; VOICE.md was preserved.')
        return before[:start] + block + before[end:]

    def apply(self, identifier):
        with self.store.lock():
            proposal = self.get(identifier)
            if proposal['status'] == 'APPLIED':
                return proposal  # Never roll back later manual edits on a repeated command.
            if proposal['status'] == 'DISMISSED':
                raise ValueError('Voice proposal was dismissed; learn again with --new.')
            current = read_text(self.document)
            if proposal['status'] == 'APPLYING' and (current == proposal['after'] or
                    (current.count(OPEN) == 1 and current.count(CLOSE) == 1 and proposal['block'] in current)):
                # The document committed before the final journal checkpoint.
                # An intact generated block also proves it survived later manual
                # edits outside the section. Reconcile history without writing it.
                proposal.update(status='APPLIED', applied_at=now())
                return self.save(proposal)
            if current != proposal['before']:
                raise ValueError('VOICE.md changed since this proposal. Preserve the edit and learn again with --new; reconcile an interrupted apply manually if needed.')
            task = self.store.get('tasks', proposal['task_id'])
            self.validate(task, proposal['analysis'])
            if proposal['block'] != self.block(identifier, task, proposal['analysis']):
                raise ValueError('Generated voice section changed; keep creator edits in VOICE.md, not the generated proposal.')
            self.current_evidence(task)
            after = self.replacement(proposal)
            proposal.update(status='APPLYING', after=after)
            self.save(proposal)
            atomic_text(self.document, after)
            proposal.update(status='APPLIED', applied_at=now())
            return self.save(proposal)

    def dismiss(self, identifier, reason):
        if not reason.strip():
            raise ValueError('Give the reason for dismissing the voice proposal.')
        with self.store.lock():
            proposal = self.get(identifier)
            if proposal['status'] not in ('PROPOSED', 'APPLYING', 'DISMISSED'):
                raise ValueError('An applied voice proposal cannot be dismissed; edit voice deliberately.')
            proposal.update(status='DISMISSED', dismissal_reason=reason.strip())
            return self.save(proposal)

    def cancel(self, task_id, reason):
        if not reason.strip():
            raise ValueError('Give the reason for cancelling the task.')
        task = self.store.get('tasks', task_id)
        if task['status'] == 'CANCELLED':
            return task
        if self.path('voice_' + task_id[5:]).exists():
            self.complete(task, None)
            raise ValueError('The voice proposal already committed. Review or dismiss it instead.')
        if task['status'] != 'PENDING':
            raise ValueError('Only a pending voice task can be cancelled.')
        task.update(status='CANCELLED', error=reason.strip())
        return self.store.put('tasks', task)
