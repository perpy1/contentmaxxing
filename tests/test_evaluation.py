import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from jsonschema import ValidationError

from contentmaxxing.cli import main
from contentmaxxing.evaluation import Evaluation, compare, file_hashes, prepare
from contentmaxxing.store import PACKAGE


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.run = self.root / 'trial'

    def tearDown(self):
        self.temp.cleanup()

    def setup_run(self, attempts=1, root=None):
        folder = root or self.run
        with patch('socket.create_connection', side_effect=AssertionError('No network in evals')):
            prepare(folder, 'fictional-test', max_attempts=attempts)
        return Evaluation(folder)

    def task(self, case='missing-proof', root=None):
        return json.loads(((root or self.run) / 'cases' / case / 'packet.json').read_text())['task']

    def response(self, case='missing-proof', root=None):
        task = self.task(case, root)
        return {'body': 'We added an owner field yesterday. Next: record unanswered requests for a week before claiming it helps.',
                'title': 'Check the change', 'quality_notes': ['Human review required.'], 'framework': None,
                'claims': [{'claim': 'An owner field was added yesterday.',
                            'source_reference': task['inputs']['idea']['source_reference'][0]}]}

    def test_prepare_is_isolated_and_compound_has_real_parent_context(self):
        evaluation = self.setup_run()
        self.assertEqual(evaluation.report()['summary'], {'NOT_RUN': 6})
        parent = self.task('compound-new-value')['inputs']['parent_content']
        self.assertEqual(parent['body'], 'A handoff needs one named owner for the next step.')
        self.assertIn('original post is context', self.task('compound-new-value')['instructions'])
        self.assertEqual(set(self.root.iterdir()), {self.run})

    def test_submit_checks_engine_behavior_without_touching_fixtures(self):
        evaluation = self.setup_run()
        before = file_hashes(self.run / 'cases')
        report = evaluation.submit('missing-proof', self.response())
        result = next(c for c in report['cases'] if c['id'] == 'missing-proof')
        self.assertEqual(result['status'], 'NEEDS_HUMAN_REVIEW')
        self.assertTrue(all(c['status'] == 'PASS' for c in result['attempts'][0]['checks']))
        self.assertEqual(file_hashes(self.run / 'cases'), before)
        state = evaluation.load()
        attempt = next(c for c in state['cases'] if c['id'] == 'missing-proof')['attempts'][0]
        self.assertEqual(attempt['result_records'][0]['status'], 'NEEDS_REVIEW')
        self.assertEqual([e['event'] for e in attempt['trace']],
                         ['response_received', 'engine_imported_response', 'repeat_import_checked'])

    def test_valid_citation_does_not_certify_a_false_claim(self):
        evaluation = self.setup_run()
        response = self.response()
        response['body'] = 'Our new owner field doubled revenue overnight.'
        response['claims'][0]['claim'] = response['body']
        report = evaluation.submit('missing-proof', response)
        result = next(c for c in report['cases'] if c['id'] == 'missing-proof')
        self.assertEqual(result['status'], 'NEEDS_HUMAN_REVIEW')
        report = evaluation.grade('missing-proof', 'fail', 'Fictional test reviewer',
                                  'The source says no outcome has been measured.')
        self.assertEqual(next(c for c in report['cases'] if c['id'] == 'missing-proof')['status'], 'FAIL')

    def test_attempt_history_budget_idempotence_and_review_invalidation(self):
        evaluation = self.setup_run(attempts=2)
        bad = self.response()
        bad['claims'][0]['source_reference']['quote'] = 'A fabricated source quote.'
        evaluation.submit('missing-proof', bad)
        evaluation.grade('missing-proof', 'pass', 'Test reviewer', 'Cannot override a failed automatic check.')
        good = self.response()
        evaluation.submit('missing-proof', good)
        report = evaluation.submit('missing-proof', good)
        case = next(c for c in report['cases'] if c['id'] == 'missing-proof')
        self.assertEqual(case['first_attempt_status'], 'FAIL')
        self.assertEqual(case['status'], 'NEEDS_HUMAN_REVIEW')
        self.assertEqual(len(case['attempts']), 2)
        good['body'] += ' More.'
        with self.assertRaisesRegex(ValueError, 'Attempt limit'):
            evaluation.submit('missing-proof', good)

    def test_duplicate_parent_is_rejected(self):
        evaluation = self.setup_run()
        output = self.response('compound-new-value')
        output['body'] = self.task('compound-new-value')['inputs']['parent_content']['body']
        result = evaluation.submit('compound-new-value', output)
        case = next(c for c in result['cases'] if c['id'] == 'compound-new-value')
        self.assertEqual(case['status'], 'FAIL')
        self.assertIn('repeats its parent', case['attempts'][0]['checks'][0]['detail'])

    def test_compare_exposes_first_attempt_and_individual_regressions(self):
        first = self.setup_run()
        first.submit('missing-proof', self.response())
        first.grade('missing-proof', 'pass', 'Test reviewer', 'This fictional response stays within the source.')
        second_root = self.root / 'candidate'
        second = self.setup_run(root=second_root)
        bad = self.response(root=second_root)
        bad['claims'][0]['source_reference']['quote'] = 'Not in the source.'
        second.submit('missing-proof', bad)
        report = compare(self.run, second_root)
        case = next(c for c in report['cases'] if c['case'] == 'missing-proof')
        self.assertEqual(case['regressions'], ['engine_contract'])
        self.assertEqual(case['baseline'], 'PASS')
        self.assertEqual(case['candidate'], 'FAIL')

    def test_moving_run_preserves_results_and_frozen_files_detect_edits(self):
        evaluation = self.setup_run()
        evaluation.submit('missing-proof', self.response())
        before = evaluation.report()
        moved = self.root / 'moved'
        shutil.move(str(self.run), moved)
        self.assertEqual(Evaluation(moved).report(), before)
        (moved / 'cases/missing-proof/workspace/data/creator/VOICE.md').write_text('Changed after the trial')
        with self.assertRaisesRegex(ValueError, 'Frozen case changed'):
            Evaluation(moved).report()

    def test_invalid_suite_or_existing_destination_preserves_work(self):
        self.run.mkdir()
        (self.run / 'notes.txt').write_text('Keep this.')
        with self.assertRaisesRegex(ValueError, 'existing work'):
            prepare(self.run, 'test')
        self.assertEqual((self.run / 'notes.txt').read_text(), 'Keep this.')
        suite = json.loads((PACKAGE / 'evals/editorial-v1.json').read_text())
        suite['cases'][0]['id'] = '../escape'
        path = self.root / 'invalid.json'
        path.write_text(json.dumps(suite))
        with self.assertRaises(ValidationError):
            prepare(self.root / 'bad', 'test', path)
        self.assertFalse((self.root / 'bad').exists())

    def test_malformed_model_json_is_retained_and_consumes_the_attempt(self):
        evaluation = self.setup_run()
        response = self.root / 'malformed.json'
        response.write_text('{unfinished')
        evaluation.submit_file('missing-proof', response)
        case = next(c for c in evaluation.load()['cases'] if c['id'] == 'missing-proof')
        self.assertEqual(case['attempts'][0]['response'], '{unfinished')
        self.assertEqual(case['attempts'][0]['checks'][0]['status'], 'FAIL')
        with self.assertRaisesRegex(ValueError, 'Attempt limit'):
            evaluation.submit('missing-proof', self.response())

    def test_intelligence_changes_are_comparable_but_suite_changes_are_not(self):
        self.setup_run()
        custom = self.root / 'intelligence'
        for folder in ('skills', 'prompts', 'templates'):
            shutil.copytree(PACKAGE / folder, custom / folder)
        with (custom / 'skills/x-writing/SKILL.md').open('a') as f:
            f.write('\nPrefer a concrete action in this trial.\n')
        other = self.root / 'other'
        prepare(other, 'changed-skill', intelligence=custom)
        comparison = compare(self.run, other)
        self.assertEqual(len(comparison['cases']), 6)
        self.assertNotEqual(Evaluation(self.run).report()['cases'][1]['instruction_sha256'],
                            Evaluation(other).report()['cases'][1]['instruction_sha256'])
        changed = json.loads((PACKAGE / 'evals/editorial-v1.json').read_text())
        changed['cases'][0]['source'] += 'Extra material.\n'
        path = self.root / 'suite.json'; path.write_text(json.dumps(changed))
        prepare(self.root / 'different', 'different-suite', path)
        with self.assertRaisesRegex(ValueError, 'same suite'):
            compare(self.run, self.root / 'different')

    def test_cli_is_available_without_creator_setup_and_never_hides_failures(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = main(['evals', 'prepare', '--output', str(self.run), '--label', 'CLI'])
        self.assertEqual(code, 0)
        self.assertEqual(len(json.loads(out.getvalue())['cases']), 6)
        with contextlib.redirect_stderr(io.StringIO()) as err:
            code = main(['--workspace', str(self.root), 'evals', 'report', '--run', str(self.run)])
        self.assertEqual(code, 1)
        self.assertIn('isolated', err.getvalue())
        with patch('contentmaxxing.evaluation.grader_digest', return_value='new-grader'):
            with self.assertRaisesRegex(ValueError, 'Grader or engine changed'):
                Evaluation(self.run).submit('missing-proof', self.response())
