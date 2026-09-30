"""Checkpointed long-source mining. Every window is bounded; coverage is explicit."""
from copy import deepcopy
import json

from .providers import PendingTask
from .retrieval import SourceLibrary, bounded_integer, validate_task_reference
from .store import new_id, normalize, record


class MiningIncomplete(Exception):
    def __init__(self, progress):
        self.progress = progress
        super().__init__('Mining call budget reached; resume the saved source pass.')


def settings(store):
    config = store.config.get('mining', {})
    size = bounded_integer(config.get('chunk_chars', 16000), 'mining.chunk_chars', 512, 200000)
    overlap = bounded_integer(config.get('overlap_chars', 800), 'mining.overlap_chars', 0, size // 2)
    calls = bounded_integer(config.get('chunks_per_call', 3), 'mining.chunks_per_call', 1, 100)
    topics = bounded_integer(config.get('idea_context_chars', 12000), 'mining.idea_context_chars', 0, 100000)
    return {'chunk_chars': size, 'overlap_chars': overlap, 'chunks_per_call': calls, 'idea_context_chars': topics}


def existing_idea_context(store, source_id, text, max_chars):
    """Bounded retrieval keys, not proof or a global semantic deduplication claim."""
    words = {word for word in normalize(text).split() if len(word) >= 4}
    pending = {t['inputs']['idea']['id'] for t in store.list('tasks')
               if t['operation'] == 'draft' and t['status'] == 'PENDING'}
    eligible = []
    for idea in store.list('ideas'):
        if idea['status'] == 'ARCHIVED' or idea.get('parent_content_id') or idea['id'] in pending:
            continue
        same_source = any(ref['source_id'] == source_id for ref in idea['source_reference'])
        overlap = len(words & set(normalize(idea['topic']).split()))
        if same_source or overlap:
            row = {key: idea[key] for key in ('id', 'topic', 'category')}
            notes = idea.get('notes', '')
            row.update(notes=notes[:600], notes_truncated=len(notes) > 600)
            eligible.append((not same_source, -overlap, idea['id'], row))
    selected = []
    # Charge the serialized list, including punctuation. Zero explicitly disables retrieval.
    returned = 2 if max_chars >= 2 else 0
    for _, _, _, row in sorted(eligible):
        size = len(json.dumps(selected + [row], ensure_ascii=False, separators=(',', ':')))
        if size <= max_chars:
            selected.append(row)
            returned = size
    return {'existing_ideas': selected,
            'existing_idea_context': {'max_chars': max_chars, 'returned_chars': returned,
                'eligible': len(eligible), 'omitted': len(eligible) - len(selected),
                'notice': 'Same-source topics first, then lexical matches. Titles and bounded notes are retrieval guidance, not evidence; this is not the complete idea bank.'}}


def existing_target(store, inputs, candidate):
    identifier = candidate.get('existing_idea_id')
    if identifier is None:
        return None
    snapshot = next((i for i in inputs.get('existing_ideas', []) if i['id'] == identifier), None)
    if snapshot is None:
        raise ValueError('Existing idea was not supplied to this mining task: ' + identifier)
    if candidate['topic'] != snapshot['topic']:
        raise ValueError('An evidence attachment must retain the supplied existing topic exactly.')
    current = store.get('ideas', identifier)
    ref = {'source_id': inputs['source_id'], **{key: candidate[key] for key in ('quote', 'start_line', 'end_line')}}
    if ref in current['source_reference']:
        return identifier  # Recovery must not undo a rename/status edit made after attachment.
    context_changed = (current['topic'] != snapshot['topic'] or current['category'] != snapshot['category'] or
                       ('notes' in snapshot and (current.get('notes', '')[:600] != snapshot['notes'] or
                        (len(current.get('notes', '')) > 600) != snapshot.get('notes_truncated', False))))
    if context_changed or current['status'] == 'ARCHIVED' or current.get('parent_content_id'):
        raise ValueError('Existing idea changed since mining context was saved; preserve it and review the match: ' + identifier)
    if any(t['status'] == 'PENDING' and t['operation'] == 'draft' and t['inputs']['idea']['id'] == identifier
           for t in store.list('tasks')):
        raise ValueError('A draft task already snapshots this existing idea; finish it or attach evidence to that task explicitly.')
    return identifier


def windows(text, size, overlap):
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        if end < len(text):
            # Keep full turns when possible, without allowing one huge turn to
            # break the budget. Overlap supplies boundary context, not new topics.
            newline = text.rfind('\n', start + size * 3 // 4, end)
            if newline >= 0:
                end = newline + 1
        yield start, end
        if end == len(text):
            break
        start = end - overlap
        boundary = text.find('\n', start, end - 1)
        if overlap and boundary >= 0:
            start = boundary + 1


def latest(store, source_id):
    runs = [r for r in store.list('mining') if r['source_id'] == source_id]
    return runs[-1] if runs else None


def progress(store, run):
    completed, pending, results, covered, furthest = 0, [], [], 0, 0
    for part in run['parts']:
        path = store.path('tasks', part['task_id'])
        task = store.get('tasks', part['task_id']) if path.exists() else None
        if task and task['status'] == 'COMPLETED':
            completed += 1
            results.extend(task['result_ids'])
            covered += max(0, part['end_offset'] - max(furthest, part['start_offset']))
            furthest = max(furthest, part['end_offset'])
        elif task:
            pending.append(task['id'])
    return {'id': run['id'], 'source_id': run['source_id'],
            'status': 'COMPLETED' if completed == len(run['parts']) else 'IN_PROGRESS',
            'completed_chunks': completed, 'total_chunks': len(run['parts']),
            'covered_chars': covered, 'source_chars': run['source_chars'],
            'pending_task_ids': pending, 'result_ids': list(dict.fromkeys(results)),
            'notice': 'Coverage measures processed source windows, not semantic completeness or editorial quality.'}


def source_progress(store, source_id=None):
    if source_id:
        store.get('sources', source_id)
        run = latest(store, source_id)
        if run:
            return progress(store, run)
        tasks = [t for t in store.list('tasks') if t['operation'] == 'mine' and t['inputs']['source_id'] == source_id]
        task = tasks[-1] if tasks else None
        return {'source_id': source_id, 'status': task['status'] if task else 'NOT_STARTED',
                'completed_chunks': int(bool(task and task['status'] == 'COMPLETED')), 'total_chunks': 1,
                'pending_task_ids': [task['id']] if task and task['status'] == 'PENDING' else [],
                'result_ids': task['result_ids'] if task else []}
    return [source_progress(store, s['id']) for s in store.list('sources')]


def validate_window(inputs, candidate):
    if 'source_window' not in inputs:
        return  # Existing whole-source tasks retain their contract.
    validate_task_reference({'source_context': {'version': 2}, 'sources': {
        inputs['source_id']: [{'quote': inputs['text'], 'start_line': inputs['source_window']['start_line']}]}},
        {'source_id': inputs['source_id'], **candidate})


class Mining:
    def __init__(self, engine):
        self.engine, self.store = engine, engine.store

    def run(self, source_id, restart=False, retry=False):
        from .engine import MINE_CONTRACT
        library = SourceLibrary(self.store)
        source, text, _, _ = library.document(source_id)  # Verify the immutable original on every resume.
        config = settings(self.store)
        run = latest(self.store, source_id)
        if run and restart and progress(self.store, run)['status'] != 'COMPLETED':
            raise ValueError('Finish the saved mining pass before restarting it; partial work was preserved.')
        if run is None or restart:
            template = self.engine.task('mine', 'transcript-mining', {
                'source_id': source_id, 'source': source, 'creator': self.store.brain()}, MINE_CONTRACT)
            template['instructions'] += ('\nThis is one source window. Extract every useful distinct topic in '
                'inputs.text, preserving original line numbers from source_window.start_line. Windows may '
                'overlap or start/end mid-line; do not invent missing speaker/context. Do not cite unseen '
                'text. Do not artificially multiply one idea at a boundary. Other windows are separate '
                'saved tasks; completing this one does not complete the whole source.\n')
            parts = []
            for start, end in windows(text, config['chunk_chars'], config['overlap_chars']):
                span = library.passage(source_id, start, end)
                parts.append({'task_id': new_id('task'), **{k: span[k] for k in
                              ('start_offset', 'end_offset', 'start_line', 'end_line')}})
            run = {**record('mine'), 'source_id': source_id, 'source_sha256': source['sha256'],
                   'source_chars': len(text), 'settings': config, 'template': template, 'parts': parts}
            self.store.put('mining', run)  # IDs exist before task/provider side effects.
        if run['source_sha256'] != source['sha256']:
            raise ValueError('Mining source identity changed; capture a new source revision.')
        executed = 0
        for index, part in enumerate(run['parts']):
            path = self.store.path('tasks', part['task_id'])
            if path.exists():
                task = self.store.get('tasks', part['task_id'])
                if task['status'] == 'COMPLETED':
                    continue
                if not retry:
                    raise PendingTask(task['id'])
                selected_provider = self.engine.provider_name or self.store.config['provider']
                if task['provider'] != selected_provider:
                    raise ValueError('Retry must use the saved task provider, or complete the task with an external result.')
            else:
                task = deepcopy(run['template'])
                task['id'] = part['task_id']
                task['inputs'].update(text=text[part['start_offset']:part['end_offset']],
                    source_window={**part, 'run_id': run['id'], 'index': index + 1, 'total': len(run['parts']),
                        'starts_mid_line': part['start_offset'] > 0 and text[part['start_offset'] - 1] != '\n',
                        'ends_mid_line': part['end_offset'] < len(text) and text[part['end_offset'] - 1] != '\n'})
                if 'existing_idea_id' in task['output_contract']['properties']['ideas']['items']['properties']:
                    task['inputs'].update(existing_idea_context(self.store, source_id, task['inputs']['text'],
                        run['settings'].get('idea_context_chars', 12000)))
            if executed == config['chunks_per_call']:
                raise MiningIncomplete(progress(self.store, run))
            executed += 1
            self.engine.execute(task)
        result = progress(self.store, run)
        return [self.store.get('ideas', identifier) for identifier in result['result_ids']]
