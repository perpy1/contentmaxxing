"""Measured winners become source-backed, inspectable development briefs."""
from copy import deepcopy
from difflib import SequenceMatcher
import hashlib
import json

from jsonschema import Draft202012Validator

from .analytics import latest_snapshots, score, winners
from .editorial import REFERENCE, TEXT
from .feedback import Feedback
from .providers import PendingTask
from .retrieval import SourceLibrary, bounded_integer, terms, validate_task_reference
from .store import atomic_text, normalize, now


CONTRACT = {'type': 'object', 'additionalProperties': False,
    'required': ['assessment', 'opportunities'], 'properties': {
        'assessment': TEXT,
        'opportunities': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False,
            'required': ['topic', 'addition', 'new_value', 'rationale', 'platform', 'format', 'job',
                         'source_reference', 'evidence_gaps'],
            'properties': {'topic': TEXT, 'new_value': TEXT, 'rationale': TEXT,
                'addition': {'enum': ['context', 'proof', 'story', 'format', 'argument', 'utility']},
                'platform': {'type': 'string'}, 'format': {'type': 'string'}, 'job': {'type': 'string'},
                'source_reference': {'type': 'array', 'minItems': 1, 'items': REFERENCE},
                'evidence_gaps': {'type': 'array', 'uniqueItems': True, 'items': TEXT}}}}}}


def needs_capture(idea):
    return any(gap['resolution'] is None for gap in idea.get('development', {}).get('gaps', []))


def require_ready(idea):
    if needs_capture(idea):
        raise ValueError('Follow-up needs captured evidence. Resolve its development gaps before drafting: ' + idea['id'])


def duplicate_topic(candidate, other, parent):
    # A deliberate new native container can keep the original topic. Its new
    # value and lineage distinguish the derivative from the source idea.
    if candidate['addition'] == 'format':
        if other['id'] == parent['idea_id']:
            return False
        target = (candidate.get('platform', candidate.get('best_platform')), candidate['format'])
        if other.get('parent_content_id') == parent['id'] and target != (other['best_platform'], other['format']):
            return False
    a, b = normalize(candidate['topic']), normalize(other['topic'])
    same_span = any(r in other['source_reference'] for r in candidate['source_reference'])
    negators = {'no', 'not', 'never', 'without', 'avoid'}
    return a == b or (same_span and set(a.split()) & negators == set(b.split()) & negators and
                      SequenceMatcher(None, a, b).ratio() >= .92)


class Compounding:
    def __init__(self, engine):
        self.engine, self.store = engine, engine.store

    def cite(self, task, ref):
        """Explicitly enrich evidence without replanning or remeasuring a winner."""
        if task['status'] != 'PENDING' or 'prepared_compound' in task:
            raise ValueError('Only an uncommitted pending compound task can receive more evidence.')
        self.store.validate_reference(ref)
        inputs = task['inputs']
        extras = list(inputs.get('extra_source_reference', []))
        if ref in extras or ref in inputs['parent_content']['source_reference']:
            return task
        library = SourceLibrary(self.store)
        limit = bounded_integer(inputs['source_context']['max_chars'], 'compound source budget', 256, 300000)
        existing = [p for values in inputs['sources'].values() for p in values]
        required = library.required_passages([ref])[0]
        selected = library.coalesce(existing + [required])
        used = sum(len(p['quote']) for p in selected)
        if used > limit:
            raise ValueError('Additional evidence exceeds the frozen compound source budget. '
                             'Use a narrower quote or deliberately start a new analysis with a larger budget; '
                             'the existing snapshot was not changed.')
        _, text, _, _ = library.document(ref['source_id'])
        whole = library.coalesce(selected + [library.passage(ref['source_id'], 0, len(text))]) if len(text) <= 2400 else None
        if whole is not None and sum(len(p['quote']) for p in whole) <= limit:
            selected = whole
        else:
            allowance = min(600, limit - used)
            start = max(0, required['start_offset'] - allowance // 2)
            end = min(len(text), required['end_offset'] + allowance - (required['start_offset'] - start))
            selected = library.coalesce(selected + [library.passage(ref['source_id'], start, end)])
        source_ids = sorted({p['source_id'] for p in selected})
        # Loading each original also verifies its stored hash before committing.
        metadata = {sid: library.document(sid)[0] for sid in source_ids}
        context = {**inputs['source_context'],
                   'returned_chars': sum(len(p['quote']) for p in selected),
                   'available_chars': sum(len(library.document(sid)[1]) for sid in source_ids)}
        inputs.update(sources={sid: [p for p in selected if p['source_id'] == sid] for sid in source_ids},
                      source_metadata=metadata, source_context=context,
                      extra_source_reference=extras + [ref])
        return self.store.put('tasks', task)

    def request(self, content_id, fresh=False, query='', as_of=None):
        previous = [t for t in self.store.list('tasks') if t['operation'] == 'compound' and
                    t['inputs']['parent_content']['id'] == content_id]
        if previous:
            task = previous[-1]
            if task['status'] == 'CANCELLED' and not fresh:
                raise ValueError('Compound task was cancelled. Use --new for a deliberate new analysis.')
            if task['status'] == 'PENDING':
                if task.get('prepared_compound'):
                    return self.complete(task, None)
                if fresh or (query and query != task['inputs']['retrieval_query']):
                    raise ValueError('Complete the pending compound task before requesting another pass.')
                raise PendingTask(task['id'])
            if not fresh:
                return [self.store.get('ideas', identifier) for identifier in task['result_ids']]
        legacy = [i for i in self.store.list('ideas') if i['parent_content_id'] == content_id]
        if legacy and not fresh:
            return legacy
        parent = self.store.get('content', content_id)
        as_of = as_of or now()
        winner = next((w for w in winners(self.store, as_of) if w['content_id'] == content_id), None)
        if winner is None:
            raise ValueError('Not a measured winner: need a known job metric, sufficient matched peers and meaningful lift.')
        inputs = self.context(parent, winner, as_of, query)
        return self.engine.execute(self.engine.task('compound', 'compound', inputs, CONTRACT))

    def context(self, parent, winner, as_of, query):
        library = SourceLibrary(self.store)
        cfg = self.store.config.get('compound', {})
        max_moves = bounded_integer(cfg.get('max_opportunities', 6), 'compound.max_opportunities', 1, 30)
        refs = deepcopy(parent['source_reference'])
        for claim in parent['claims']:
            if claim['source_reference'] not in refs:
                refs.append(claim['source_reference'])
        retrieval = self.store.config.get('retrieval', {})
        evidence = library.context(refs, parent['topic'], retrieval.get('draft_source_chars', 16000),
                                   retrieval.get('draft_source_passages', 12))
        search_query = query or parent['topic']
        extra_chars = bounded_integer(cfg.get('related_source_chars', 8000), 'compound.related_source_chars', 128, 100000)
        hits = library.search(search_query, limit=6, max_chars=extra_chars) if terms(search_query) else {'results': [], 'source_count': 0}
        passages = [p for values in evidence['sources'].values() for p in values]
        for hit in hits['results']:
            if not any(library.overlap(hit, old) for old in passages):
                evidence['sources'].setdefault(hit['source_id'], []).append(hit)
                evidence['source_metadata'][hit['source_id']] = self.store.get('sources', hit['source_id'])
                passages.append(hit)
        evidence['source_context'].update(max_chars=evidence['source_context']['max_chars'] + extra_chars,
            returned_chars=sum(len(p['quote']) for p in passages),
            available_chars=sum(len(library.document(sid)[1]) for sid in evidence['sources']))
        profile = json.loads((self.store.data / 'creator/profile.json').read_text())
        formats = {p: f for p, f in self.store.registry['platforms'].items()
                   if {'x_article': 'x', 'substack_note': 'substack'}.get(p, p) in profile['platforms']}
        latest = latest_snapshots(self.store, as_of)
        peers = []
        for content in self.store.list('content'):
            measurement = latest.get(content['id'])
            if (content['id'] == parent['id'] or content['status'] not in ('PUBLISHED', 'COMPOUND') or
                    (content['platform'], content['primary_job']) != (parent['platform'], parent['primary_job']) or not measurement):
                continue
            metric = score(content, measurement, self.store.registry)
            impressions = measurement['metrics']['impressions']
            if metric is not None and impressions is not None and impressions >= self.store.config['winner']['minimum_impressions']:
                peers.append({'content_id': content['id'], 'score': metric, 'observed_at': measurement['observed_at'],
                              'published_at': content['published_at'], 'measurement_ids': measurement['measurement_ids']})
        existing = [i for i in self.store.list('ideas') if i['parent_content_id'] == parent['id']]
        return {'parent_content': {**parent, 'source_reference': refs}, 'creator': self.store.brain(),
            **evidence, 'retrieval_query': search_query, 'searched_sources': hits['source_count'],
            'performance': {'winner': winner, 'as_of': as_of, 'measurement': latest[parent['id']],
                'peer_examples': peers[:30], 'peer_count': len(peers),
                'limitations': 'Matched platform/job median, excluding this post. Cumulative observation ages may differ. Lift is not causal proof; peer examples are capped at 30.'},
            'formats': formats, 'jobs': self.store.registry['jobs'], 'max_opportunities': max_moves,
            'feedback': {p: Feedback(self.store).context(p, parent['id'] if p == parent['platform'] else None) for p in formats},
            'existing_follow_ups': [{**{k: i[k] for k in ('id', 'topic', 'addition', 'follow_up_angle', 'status',
                'best_platform', 'format', 'primary_job')}, 'needs_capture': needs_capture(i)} for i in existing],
            'notice': 'Generate useful follow-up topics, not finished posts. Empty output is valid. Missing evidence becomes an explicit development gap.'}

    def prepare(self, task, output):
        Draft202012Validator(task['output_contract']).validate(output)
        inputs, prepared = task['inputs'], []
        if len(output['opportunities']) > inputs['max_opportunities']:
            raise ValueError('Compound opportunities exceed the configured ceiling.')
        parent = inputs['parent_content']
        existing = self.store.list('ideas')
        for choice in output['opportunities']:
            if choice['platform'] not in inputs['formats'] or choice['format'] not in inputs['formats'][choice['platform']] or choice['job'] not in inputs['jobs']:
                raise ValueError('Compound opportunity needs a creator-selected platform, registered native format and job.')
            if choice['addition'] == 'format' and (choice['platform'], choice['format']) == (parent['platform'], parent['format']):
                raise ValueError('A format-only derivative must change the native container.')
            if not normalize(choice['new_value']) or normalize(choice['new_value']) in (normalize(parent['topic']), normalize(parent['body'])):
                raise ValueError('Describe distinct new value beyond repeating the parent.')
            topic = normalize(choice['topic'])
            if not topic or (topic == normalize(parent['topic']) and choice['addition'] != 'format'):
                raise ValueError('A compound topic must be distinct from its parent.')
            for other in existing + prepared:
                if duplicate_topic(choice, other, parent):
                    raise ValueError('Compound topic duplicates an existing idea or another proposed angle: ' + other['id'])
            for ref in choice['source_reference']:
                self.store.validate_reference(ref)
                validate_task_reference(inputs, ref)
            ref = choice['source_reference'][0]
            idea = self.engine.idea_from({'topic': choice['topic'], 'category': 'compound opportunity',
                'quote': ref['quote'], 'start_line': ref['start_line'], 'end_line': ref['end_line']},
                ref['source_id'], task['provider'] + ' compound', parent['id'], choice['addition'])
            idea.update(source_reference=deepcopy(choice['source_reference']), format=choice['format'],
                primary_job=choice['job'], best_platform=choice['platform'], priority=80,
                article_candidate=choice['platform'] in ('x_article', 'substack'),
                notes=choice['rationale'], follow_up_angle=choice['new_value'],
                performance={'parent': inputs['performance']['winner'], 'as_of': inputs['performance']['as_of']},
                development={'task_id': task['id'], 'new_value': choice['new_value'],
                    'gaps': [{'question': gap, 'resolution': None} for gap in choice['evidence_gaps']]})
            idea['dedupe_key'] = hashlib.sha256('\0'.join((topic, parent['id'], choice['platform'],
                choice['format'], normalize(choice['new_value']))).encode()).hexdigest()
            self.store.validate('idea', idea)
            prepared.append(idea)
        return {'assessment': output['assessment'], 'ideas': prepared}

    def complete(self, task, output):
        prepared = task.get('prepared_compound')
        parent = self.store.get('content', task['inputs']['parent_content']['id'])
        if parent['status'] not in ('PUBLISHED', 'COMPOUND') and (prepared is None or
                any(not self.store.path('ideas', i['id']).exists() for i in prepared['ideas'])):
            raise ValueError('Parent is no longer active published content; do not create new derivatives.')
        if prepared is None:
            prepared = self.prepare(task, output)
            task['prepared_compound'] = prepared
            self.store.put('tasks', task)  # Stable IDs and full validation before any idea is written.
        # Validate every new write first, also after an interrupted import.
        planned_ids = {i['id'] for i in prepared['ideas']}
        others = [i for i in self.store.list('ideas') if i['id'] not in planned_ids]
        for idea in prepared['ideas']:
            if self.store.path('ideas', idea['id']).exists():
                current = self.store.get('ideas', idea['id'])
                if current.get('development', {}).get('task_id') != task['id']:
                    raise ValueError('Compound checkpoint belongs to another task.')
            else:
                if any(duplicate_topic(idea, other, parent) for other in others):
                    raise ValueError('A matching idea appeared after preparation. Resolve the duplicate before importing this compound task.')
                self.store.validate('idea', idea)
                for ref in idea['source_reference']:
                    self.store.validate_reference(ref)
        results = []
        for idea in prepared['ideas']:
            path = self.store.path('ideas', idea['id'])
            if path.exists():
                current = self.store.get('ideas', idea['id'])
                results.append(current)  # Preserve subsequent creator edits and resolved gaps.
            else:
                results.append(self.store.put('ideas', idea))
        if parent['status'] == 'PUBLISHED':
            self.engine.transition(parent['id'], 'COMPOUND')
        winner = task['inputs']['performance']['winner']
        marker = '<!-- compound:' + task['id'] + ' -->'
        path = self.store.data / 'creator/LEARNINGS.md'
        learning = path.read_text()
        if marker not in learning:
            atomic_text(path, learning + '\n' + marker + '\n- %s: %.2fx matched median (%s; %s peers), as of %s. Tentative association, not causal proof. %s follow-up topics; assessment in task %s.\n' % (
                parent['id'], winner['lift'], winner['metric'], winner['peers'], task['inputs']['performance']['as_of'], len(results), task['id']))
        task.update(status='COMPLETED', result_ids=[i['id'] for i in results], error=None)
        self.render(task)
        self.store.put('tasks', task)
        return results

    def render(self, task):
        prepared = task.get('prepared_compound')
        if not prepared:
            return
        parent = task['inputs']['parent_content']
        performance = task['inputs']['performance']
        metric = performance['winner']
        lines = ['# Compound opportunities', '', 'Task status: ' + task['status'], '', 'Parent: ' + parent['id'] + ' — ' + parent['topic'], '',
            'Measured observation: %.2fx matched median on %s (%s peers), as of %s.' % (
                metric['lift'], metric['metric'], metric['peers'], performance['as_of']), '',
            performance['limitations'], '', '## Editorial assessment (hypothesis)', '', prepared['assessment']]
        for planned in prepared['ideas']:
            if not self.store.path('ideas', planned['id']).exists():
                continue
            idea = self.store.get('ideas', planned['id'])
            lines += ['', '## ' + idea['topic'], '',
                'Idea: ' + idea['id'], '', 'Readiness: ' + ('NEEDS CAPTURE' if needs_capture(idea) else 'Ready for editorial selection'), '',
                'Platform / format / job: %s / %s / %s' % (idea['best_platform'], idea['format'], idea['primary_job']), '',
                'New value: ' + idea['development']['new_value'], '', 'Rationale: ' + idea['notes']]
            for index, gap in enumerate(idea['development']['gaps'], 1):
                lines += ['', 'Gap %s: %s' % (index, gap['question']),
                          'Resolution: ' + (gap['resolution']['note'] if gap['resolution'] else 'Capture required.')]
            lines += ['', 'Evidence: ' + ', '.join('%s lines %s–%s' % (r['source_id'], r['start_line'], r['end_line']) for r in idea['source_reference'])]
        lines += ['', 'This is a development report, not approval or publication. Citation validity does not establish semantic support.']
        atomic_text(self.store.data / 'reports/compound' / (task['id'] + '.md'), '\n'.join(lines) + '\n')

    def cancel(self, task_id, reason):
        task = self.store.get('tasks', task_id)
        if task['operation'] != 'compound' or task['status'] == 'COMPLETED' or not reason.strip():
            raise ValueError('Cancel a pending compound task with an explicit reason.')
        if task['status'] == 'CANCELLED':
            return task
        planned = task.get('prepared_compound', {}).get('ideas', [])
        saved = [i['id'] for i in planned if self.store.path('ideas', i['id']).exists()]
        if planned and len(saved) == len(planned):
            self.complete(task, None)  # Already committed: reconcile, do not claim it was cancelled.
            return self.store.get('tasks', task_id)
        task.update(status='CANCELLED', cancellation_reason=reason.strip(), result_ids=saved, error=None)
        self.store.put('tasks', task)
        self.render(task)
        return task

    def resolve(self, idea_id, supplied):
        contract = {'type': 'object', 'additionalProperties': False, 'required': ['resolutions'], 'properties': {
            'resolutions': {'type': 'array', 'minItems': 1, 'items': {'type': 'object', 'additionalProperties': False,
                'required': ['gap', 'note', 'source_reference'], 'properties': {
                    'gap': {'type': 'integer', 'minimum': 1}, 'note': TEXT,
                    'source_reference': {'type': 'array', 'minItems': 1, 'items': REFERENCE}}}}}}
        Draft202012Validator(contract).validate(supplied)
        idea = self.store.get('ideas', idea_id)
        gaps = idea.get('development', {}).get('gaps', [])
        seen, changed = set(), False
        for value in supplied['resolutions']:
            index = value['gap'] - 1
            if index >= len(gaps) or index in seen:
                raise ValueError('Resolve each existing development gap at most once per import.')
            seen.add(index)
            resolution = {k: value[k] for k in ('note', 'source_reference')}
            previous = gaps[index]['resolution']
            if previous:
                if any(previous[k] != resolution[k] for k in resolution):
                    raise ValueError('Gap already resolved; its recorded evidence is preserved.')
                continue
            for ref in value['source_reference']:
                self.store.validate_reference(ref)
                if ref not in idea['source_reference']:
                    idea['source_reference'].append(ref)
            gaps[index]['resolution'] = {**resolution, 'resolved_at': now()}
            changed = True
        if changed:
            self.store.put('ideas', idea)
        self.render(self.store.get('tasks', idea['development']['task_id']))
        return idea
