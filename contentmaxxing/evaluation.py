"""Portable editorial trials. The host writes; code checks; people judge meaning."""
import hashlib
import json
import os
import re
import shutil
import tempfile
from collections import Counter
from contextlib import contextmanager
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError

from .engine import Engine
from .providers import PendingTask
from .store import PACKAGE, Store, atomic_json, atomic_text, now


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False).encode()).hexdigest()


def grader_digest():
    # Changes to the importer can change a grade just as changes to this file can.
    return digest({name: hashlib.sha256((PACKAGE / name).read_bytes()).hexdigest()
                   for name in ('evaluation.py', 'engine.py', 'store.py', 'retrieval.py', 'feedback.py', 'mining.py',
                                'revisions.py', 'editorial.py', 'planning.py', 'scheduler.py', 'compounding.py')})


def file_hashes(root):
    result = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError('Evaluation files must not be symlinks: ' + str(path))
        if path.is_file():
            result[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def pending(call):
    try:
        call()
    except PendingTask as exc:
        return exc.task_id
    raise ValueError('Evaluation preparation expected an external task.')


def prepare(output, label, suite_path=None, intelligence=None, max_attempts=1):
    if not label.strip() or type(max_attempts) is not int or not 1 <= max_attempts <= 10:
        raise ValueError('Supply a label and an attempt limit from 1 to 10.')
    root = Path(output).absolute()
    if root.exists() or root.is_symlink():
        raise ValueError('Use a new evaluation directory; existing work is preserved.')
    suite = json.loads(Path(suite_path or PACKAGE / 'evals/editorial-v1.json').read_text())
    schema = json.loads((PACKAGE / 'schemas/eval-suite.schema.json').read_text())
    Draft202012Validator(schema).validate(suite)
    ids = [case['id'] for case in suite['cases']]
    if len(set(ids)) != len(ids):
        raise ValueError('Evaluation case IDs must be unique.')
    root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.contentmaxxing-eval-', dir=str(root.parent)) as staging:
        stage = Path(staging)
        state = {'version': 1, 'created_at': now(), 'label': label,
                 'suite_id': suite['id'], 'suite_sha256': digest(suite),
                 'grader_sha256': grader_digest(), 'max_attempts': max_attempts, 'cases': []}
        atomic_json(stage / 'suite.json', suite)
        (stage / 'responses').mkdir()
        for case in suite['cases']:
            case_root = stage / 'cases' / case['id']
            workspace = case_root / 'workspace'
            store = Store(workspace)
            store.init('external')
            if intelligence:
                # Swap intelligence, not schemas, fixtures, outcomes or grader logic.
                for folder in ('skills', 'prompts', 'templates'):
                    source = Path(intelligence) / folder
                    if not source.is_dir() or source.is_symlink():
                        raise ValueError('Intelligence needs a real ' + folder + ' directory.')
                    file_hashes(source)  # Reject symlinks before copying.
                    shutil.copytree(source, store.assets / folder, dirs_exist_ok=True)
            engine = Engine(workspace, provider_name='external')
            engine.onboard(case['profile'])
            atomic_text(store.data / 'creator/VOICE.md', case['voice'])
            source_file = workspace / 'source-notes.txt'
            atomic_text(source_file, case['source'])
            source = engine.capture(source_file, notes='Fictional editorial evaluation fixture.')
            if case['operation'] == 'mine':
                task_id = pending(lambda: engine.mine(source['id']))
            elif case['operation'] == 'compound':
                # Fixed fictional observations make a reproducible winner, using
                # the real lifecycle and metrics instead of bypassing eligibility.
                parent_id = None
                for index in range(5):
                    candidate = {'topic': case['topic'] if index == 0 else 'Fictional peer ' + str(index),
                        'category': 'evaluation', 'quote': case['source'].strip(),
                        'start_line': 1, 'end_line': len(case['source'].splitlines())}
                    idea = engine.persist_idea(engine.idea_from(candidate, source['id'], 'evaluation fixture'))
                    engine.select(idea['id'], 'x', 'short post', 'Bookmarks / Saves')
                    draft_id = pending(lambda: engine.draft(idea['id']))
                    post = engine.complete_task(draft_id, {'body': case['parent_body'] if index == 0 else 'Fictional matched peer ' + str(index),
                        'title': '', 'claims': [], 'framework': None,
                        'quality_notes': ['Simulated publication and metrics for a fictional evaluation only.']})[0]
                    engine.transition(post['id'], 'APPROVED')
                    engine.transition(post['id'], 'PUBLISHED', url='https://example.com/fictional/' + str(index), published_at='2026-01-01T12:00:00+00:00')
                    engine.manual_metrics(post['id'], {'impressions': 1000, 'bookmarks': 40 if index == 0 else 4}, observed_at='2026-01-02T12:00:00+00:00')
                    if index == 0:
                        parent_id = post['id']
                task_id = pending(lambda: engine.compound(parent_id, as_of='2026-01-03T12:00:00+00:00'))
            else:
                candidate = {'topic': case['topic'], 'category': 'evaluation',
                             'quote': case['source'].strip(), 'start_line': 1,
                             'end_line': len(case['source'].splitlines())}
                parent_id = None
                if case.get('parent_body'):
                    original = engine.persist_idea(engine.idea_from(
                        {**candidate, 'topic': 'Original: ' + case['topic']}, source['id'], 'external'))
                    engine.select(original['id'], 'x')
                    original_task = pending(lambda: engine.draft(original['id']))
                    original_post = engine.complete_task(original_task, {
                        'body': case['parent_body'], 'title': 'Fictional parent post',
                        'claims': [], 'quality_notes': ['Seed for a derivative-writing evaluation; not a measured winner.'],
                        'framework': None})[0]
                    parent_id = original_post['id']
                idea = engine.persist_idea(engine.idea_from(candidate, source['id'], 'external',
                    parent=parent_id, addition=case.get('addition')))
                engine.select(idea['id'], case['platform'], case['format'], case['job'])
                task_id = pending(lambda: engine.draft(idea['id']))
            task = store.get('tasks', task_id)
            atomic_json(case_root / 'packet.json', {'brief': case['brief'], 'task': task})
            state['cases'].append({'id': case['id'], 'operation': case['operation'],
                'task_id': task_id, 'rubric': case['rubric'], 'attempts': [],
                'instruction_sha256': digest(task['instructions']),
                'files': file_hashes(case_root)})
        atomic_json(stage / 'run.json', state)
        atomic_text(stage / 'RUN.md', '# Editorial evaluation\n\n'
            'Read one cases/<id>/packet.json at a time. Execute its task instructions and\n'
            'return only the output_contract JSON under responses/<id>.json.\n'
            'Submit with contentmaxxing evals submit --run <folder> --case <id> --file <response>.\n'
            'Case workspaces are frozen fixtures. Do not complete their tasks directly.\n'
            'Do not inspect rubrics or earlier responses before writing your first attempt.\n'
            'Do not grade your own editorial quality as human feedback.\n')
        if root.exists():
            raise ValueError('Evaluation destination appeared during preparation.')
        os.rename(stage, root)
    return {'run': str(root), 'label': label, 'suite_id': suite['id'], 'max_attempts': max_attempts,
            'cases': [{'id': c['id'], 'packet': 'cases/' + c['id'] + '/packet.json'} for c in state['cases']],
            'next': 'Read RUN.md and one packet at a time. Return contract JSON under responses/ and submit it.'}


class Evaluation:
    def __init__(self, root):
        self.root = Path(root).absolute()
        if self.root.is_symlink():
            raise ValueError('Evaluation directory must not be a symlink.')

    @contextmanager
    def lock(self):
        path = self.root / '.eval.lock'
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            raise ValueError('Evaluation is busy; verify no writer is running before removing .eval.lock.') from None
        try:
            os.close(fd)
            yield
        finally:
            path.unlink()

    def load(self, writing=False):
        path = self.root / 'run.json'
        if path.is_symlink() or (self.root / 'suite.json').is_symlink():
            raise ValueError('Evaluation metadata must not be symlinked.')
        state = json.loads(path.read_text())
        if state.get('version') != 1:
            raise ValueError('Unsupported evaluation run version.')
        if digest(json.loads((self.root / 'suite.json').read_text())) != state['suite_sha256']:
            raise ValueError('Evaluation suite changed. Prepare a new run.')
        if writing and state['grader_sha256'] != grader_digest():
            raise ValueError('Grader or engine changed. Prepare a new run instead of mixing grades.')
        for case in state['cases']:
            if not re.fullmatch(r'[a-z][a-z0-9-]{0,63}', case['id']):
                raise ValueError('Invalid evaluation case ID.')
            base = self.root / 'cases' / case['id']
            if base.is_symlink() or (self.root / 'cases').is_symlink() or file_hashes(base) != case['files']:
                raise ValueError('Frozen case changed: ' + case['id'] + '. Prepare a new run.')
        return state

    @staticmethod
    def case(state, case_id):
        case = next((c for c in state['cases'] if c['id'] == case_id), None)
        if case is None:
            raise ValueError('Unknown evaluation case: ' + case_id)
        return case

    def submit(self, case_id, response):
        with self.lock():
            state = self.load(writing=True)
            case = self.case(state, case_id)
            checksum = digest(response)
            if case['attempts'] and case['attempts'][-1]['response_sha256'] == checksum:
                return self.report(state)  # Retried submission, not another trial.
            if len(case['attempts']) >= state['max_attempts']:
                raise ValueError('Attempt limit reached. Prepare a new labeled run for more trials.')
            attempt = {'number': len(case['attempts']) + 1, 'submitted_at': now(),
                       'response_sha256': checksum, 'response': response, 'checks': [],
                       'reviews': [], 'result_records': [], 'trace': [{'event': 'response_received'}]}
            with tempfile.TemporaryDirectory(prefix='contentmaxxing-grade-') as folder:
                scratch = Path(folder) / 'workspace'
                shutil.copytree(self.root / 'cases' / case_id / 'workspace', scratch)
                engine = Engine(scratch, provider_name='external')
                content_before = engine.store.list('content')
                try:
                    records = engine.complete_task(case['task_id'], response)
                except (ValueError, ValidationError, KeyError, TypeError) as exc:
                    detail = exc.message if isinstance(exc, ValidationError) else str(exc)
                    attempt['checks'].append({'id': 'engine_contract', 'status': 'FAIL', 'detail': detail})
                    attempt['trace'].append({'event': 'engine_rejected_response'})
                else:
                    attempt['checks'].append({'id': 'engine_contract', 'status': 'PASS',
                        'detail': 'Schema, supplied source references and platform constraints accepted.'})
                    attempt['checks'].append({'id': 'usable_output', 'status': 'PASS' if records or case['operation'] == 'compound' else 'FAIL',
                        'detail': 'Empty opportunities can be valid; human review judges exhaustion.' if case['operation'] == 'compound' else
                                  'The source fixture contains material suitable for this task.'})
                    if case['operation'] == 'compound':
                        attempt['checks'].append({'id': 'no_automatic_drafts',
                            'status': 'PASS' if {c['id'] for c in content_before} == {c['id'] for c in engine.store.list('content')} else 'FAIL',
                            'detail': 'Compound analysis returns ideas without creating or publishing derivatives.'})
                    if case['operation'] == 'draft':
                        review_only = all(r['status'] == 'NEEDS_REVIEW' and not r['approved_at'] and
                            not r['published_urls'] and not r['scheduled_at'] for r in records)
                        attempt['checks'].append({'id': 'review_gate', 'status': 'PASS' if review_only else 'FAIL',
                            'detail': 'Generated content must await creator review.'})
                    collection = 'ideas' if case['operation'] in ('mine', 'compound') else 'content'
                    before = engine.store.list(collection)
                    repeated = engine.complete_task(case['task_id'], response)
                    stable = ([r['id'] for r in repeated] == [r['id'] for r in records]
                              and before == engine.store.list(collection))
                    attempt['checks'].append({'id': 'repeat_import', 'status': 'PASS' if stable else 'FAIL',
                        'detail': 'Repeated task completion must preserve results without duplicates.'})
                    attempt['result_records'] = records
                    attempt['trace'] += [{'event': 'engine_imported_response', 'result_ids': [r['id'] for r in records]},
                                         {'event': 'repeat_import_checked', 'stable': stable}]
            case['attempts'].append(attempt)
            atomic_json(self.root / 'run.json', state)
        return self.report(state)

    def submit_file(self, case_id, path):
        raw = Path(path).read_text(encoding='utf-8')
        def reject_constant(value):
            raise ValueError('Non-finite JSON value: ' + value)
        try:
            response = json.loads(raw, parse_constant=reject_constant)
        except ValueError:
            # Malformed model output is a failed trial, not a free hidden retry.
            # A raw string fails the shared object contract and remains inspectable.
            response = raw
        return self.submit(case_id, response)

    def grade(self, case_id, verdict, reviewer, note):
        if verdict not in ('pass', 'fail') or not reviewer.strip() or not note.strip():
            raise ValueError('Human grading requires pass/fail, a reviewer and an evidence-based note.')
        with self.lock():
            state = self.load(writing=True)
            case = self.case(state, case_id)
            if not case['attempts']:
                raise ValueError('Submit a response before grading it.')
            attempt = case['attempts'][-1]
            attempt['reviews'].append({'reviewer': reviewer, 'verdict': verdict.upper(), 'note': note,
                                      'recorded_at': now(), 'response_sha256': attempt['response_sha256']})
            atomic_json(self.root / 'run.json', state)
        return self.report(state)

    @staticmethod
    def attempt_report(attempt):
        automatic = 'FAIL' if any(c['status'] == 'FAIL' for c in attempt['checks']) else 'PASS'
        human = attempt['reviews'][-1]['verdict'] if attempt['reviews'] else 'PENDING'
        status = 'FAIL' if 'FAIL' in (automatic, human) else 'NEEDS_HUMAN_REVIEW' if human == 'PENDING' else 'PASS'
        return {'attempt': attempt['number'], 'automated': automatic, 'human': human, 'status': status,
                'checks': attempt['checks'], 'review': attempt['reviews'][-1] if attempt['reviews'] else None}

    def report(self, state=None):
        state = state or self.load()
        cases = []
        for case in state['cases']:
            trials = [self.attempt_report(a) for a in case['attempts']]
            cases.append({'id': case['id'], 'packet': 'cases/' + case['id'] + '/packet.json',
                'rubric': case['rubric'], 'instruction_sha256': case['instruction_sha256'],
                'attempts': trials, 'status': trials[-1]['status'] if trials else 'NOT_RUN',
                'first_attempt_status': trials[0]['status'] if trials else 'NOT_RUN'})
        return {'label': state['label'], 'suite_id': state['suite_id'],
                'suite_sha256': state['suite_sha256'], 'grader_sha256': state['grader_sha256'],
                'max_attempts': state['max_attempts'], 'cases': cases,
                'summary': dict(Counter(c['status'] for c in cases)),
                'limits': ['Citation validity does not prove a claim follows from its source.',
                           'Human reviewer identity is declared, not authenticated.',
                           'Trace covers evaluator operations, not the host tool history.',
                           'Attempt limits apply to submissions, not host tokens, turns or cost.']}


def compare(baseline, candidate):
    left, right = Evaluation(baseline).report(), Evaluation(candidate).report()
    if any(left[key] != right[key] for key in ('suite_sha256', 'grader_sha256')):
        raise ValueError('Compare runs with the same suite and grader; prepare matched trials after changes.')
    rows = []
    for old, new in zip(left['cases'], right['cases']):
        checks = lambda c: {x['id']: x['status'] for x in c['attempts'][0]['checks']} if c['attempts'] else {}
        old_checks, new_checks = checks(old), checks(new)
        old_checks['human'] = old['attempts'][0]['human'] if old['attempts'] else 'PENDING'
        new_checks['human'] = new['attempts'][0]['human'] if new['attempts'] else 'PENDING'
        rows.append({'case': old['id'], 'baseline': old['first_attempt_status'],
                     'candidate': new['first_attempt_status'],
                     'checks': [{'id': k, 'baseline': old_checks.get(k, 'NOT_RUN'),
                                 'candidate': new_checks.get(k, 'NOT_RUN')}
                                for k in sorted(set(old_checks) | set(new_checks))],
                     'regressions': [k for k in old_checks if old_checks[k] == 'PASS' and new_checks.get(k) == 'FAIL']})
    return {'baseline': left['label'], 'candidate': right['label'],
            'basis': 'First attempt per case; later retries remain visible in each run report.', 'cases': rows}
