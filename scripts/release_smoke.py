"""Exercise the installed kit offline, outside the checkout, with fictional data.

Run with the Python interpreter into which the release wheel was installed.
The external-agent responses here are deliberately literal test fixtures.
"""
import argparse
import csv
import hashlib
import io
import json
import os
import tempfile
import zipfile
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import contentmaxxing
from contentmaxxing.cli import main


def smoke():
    project = Path(__file__).resolve().parents[1]
    package = Path(contentmaxxing.__file__).resolve().parent
    assert package != project / 'contentmaxxing', 'Use the installed wheel, not an editable checkout.'
    fixtures = project / 'tests/fixtures'
    with tempfile.TemporaryDirectory(prefix='contentmaxxing-release-') as directory:
        root = Path(directory) / 'creator'
        def cli(*args, workspace=True, creator_root=None):
            output = io.StringIO()
            argv = (['--workspace', str(creator_root or root), '--provider', 'external'] if workspace else []) + list(args)
            with redirect_stdout(output):
                status = main(argv)
            assert status == 0, 'Failed CLI action: ' + args[0]
            return json.loads(output.getvalue())

        installed = cli('install', '--agent', 'codex', '--path', str(root), workspace=False)
        assert len(installed['commands']) == 19
        assert cli('doctor', '--agent', 'codex', '--path', str(root), workspace=False)['integrity_ok']
        assert cli('home')['initialized'] is False
        assert not (root / 'config.yaml').exists()
        assert cli('start')['phase'] == 'WELCOME'
        started = cli('start', '--mode', 'interview', '--answers', str(fixtures / 'creator.json'),
                      '--source', str(fixtures / 'transcript.txt'), '--batch-size', '5')
        assert started['phase'] == 'MINING'
        voice_path = root / 'data/creator/VOICE.md'
        voice_path.write_text(voice_path.read_text() + '\nQA voice marker: preserve sentence case.\n')
        for pending in started['pending_tasks']:
            task = cli('tasks', 'show', pending['id'])
            ideas = [{'topic': text, 'quote': text, 'start_line': index, 'end_line': index, 'category': 'fictional source'}
                     for index, text in enumerate(task['inputs']['text'].splitlines(), 1) if text.strip()]
            answer = Path(directory) / 'mining.json'
            answer.write_text(json.dumps({'ideas': ideas}))
            cli('tasks', 'complete', task['id'], str(answer))
        selected = cli('start')
        assert selected['phase'] == 'CHOOSE_TOPICS'
        voice_task = cli('tasks', 'show', cli('voice', 'learn')['task_id'])
        sample = voice_task['inputs']['samples'][0]
        voice_result = Path(directory) / 'voice.json'
        voice_result.write_text(json.dumps({'summary': 'Scripted fixture; tentative observations only.',
            'observations': [{'dimension': 'syntax', 'pattern': 'Concrete action followed by its consequence.',
                'guidance': 'Keep the practical action visible.', 'certainty': 'tentative', 'platform': None,
                'medium': 'writing', 'evidence': [{'sample_id': sample['id'], 'quote': sample['text']}]}],
            'unknowns': ['Need more writing examples.'], 'conflicts': []}))
        voice_proposal = cli('tasks', 'complete', voice_task['id'], str(voice_result))[0]
        assert cli('voice', 'apply', voice_proposal['id'])['status'] == 'APPLIED'
        assert cli('voice', 'learn')['id'] == voice_proposal['id']
        assert 'QA voice marker' in voice_path.read_text()
        chosen = selected['candidate_ideas'][:5]
        arguments = []
        for idea in chosen:
            cli('ideas', 'select', idea['id'], '--format', 'short post', '--job', 'Bookmarks / Saves')
            arguments.extend(['--idea', idea['id']])
        drafting = cli('start', *arguments)
        assert drafting['phase'] == 'DRAFTING'
        for pending in drafting['pending_tasks']:
            task = cli('tasks', 'show', pending['id'])
            assert 'QA voice marker' in task['inputs']['creator']['VOICE.md']
            reference = task['inputs']['idea']['source_reference'][0]
            answer = Path(directory) / 'draft.json'
            answer.write_text(json.dumps({'body': reference['quote'], 'title': '',
                'claims': [{'claim': reference['quote'], 'source_reference': reference}],
                'quality_notes': ['Literal fictional fixture, not a writing-quality benchmark.'], 'framework': None}))
            cli('tasks', 'complete', task['id'], str(answer))
        review = cli('start')
        assert review['phase'] == 'REVIEW' and len(review['content_ids']) == 5
        assert cli('start')['content_ids'] == review['content_ids']
        assert all(post['status'] == 'NEEDS_REVIEW' for post in cli('review'))
        assert cli('progress')['stage'] == 'REVIEW'
        searched = cli('sources', 'search', 'client questions')
        assert searched['results'] and searched['returned_chars'] <= searched['max_chars']
        feedback = cli('feedback', 'add', review['content_ids'][0], '--note', 'Keep actual owner details.',
                       '--by', 'Fictional smoke reviewer', '--scope', 'platform')
        revision = cli('revise', review['content_ids'][0], '--direction', 'Remove the speaker label in this fictional fixture.')
        revision_task = cli('tasks', 'show', revision['task_id'])
        revised_body = revision_task['inputs']['revision_target']['body'].replace('Morgan: ', '')
        answer = Path(directory) / 'revision.json'
        answer.write_text(json.dumps({'body': revised_body, 'title': '', 'framework': None,
            'claims': revision_task['inputs']['revision_target']['claims'], 'quality_notes': ['Scripted fixture revision.']}))
        revised = cli('tasks', 'complete', revision['task_id'], str(answer))[0]
        assert revised['id'] == review['content_ids'][0] and revised['revision'] == 2
        assert revised['status'] == 'NEEDS_REVIEW' and revised['approved_at'] is None
        assert cli('revisions', revised['id'])[0]['status'] == 'APPLIED'
        for index, content_id in enumerate(review['content_ids']):
            cli('review', content_id, '--approve')
            cli('status', content_id, 'PUBLISHED', '--url', 'https://example.com/fictional/' + str(index))
        assert cli('progress')['stage'] == 'MEASURE'
        metrics = Path(directory) / 'fictional-metrics.csv'
        with metrics.open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=['content_id', 'observed_at', 'impressions', 'bookmarks'])
            writer.writeheader()
            for index, content_id in enumerate(review['content_ids']):
                writer.writerow({'content_id': content_id, 'observed_at': datetime.now(timezone.utc).isoformat(),
                                 'impressions': 1000, 'bookmarks': 40 if index == 0 else 4})
        cli('analytics', 'import', str(metrics))
        cli('report', 'weekly')
        winner = cli('analytics', 'winners')[0]
        assert winner['lift'] == 10
        original_metric = next(json.loads(p.read_text()) for p in (root / 'data/analytics').glob('metric_*.json')
                               if json.loads(p.read_text())['content_id'] == winner['content_id'])
        manual_file = Path(directory) / 'disputed-observation.json'
        manual_file.write_text(json.dumps({'impressions': 1000, 'bookmarks': 4}))
        disputed = cli('analytics', 'manual', winner['content_id'], '--file', str(manual_file), '--observed-at', original_metric['observed_at'])
        inspection = cli('analytics', 'show', winner['content_id'])
        assert inspection['metric_status'] == 'CONFLICTING_OBSERVATIONS'
        assert len(inspection['observations']) == 2 and cli('analytics', 'winners') == []
        manual_file.write_text(json.dumps({'impressions': 1000, 'bookmarks': 40}))
        corrected = cli('analytics', 'manual', winner['content_id'], '--file', str(manual_file), '--observed-at', original_metric['observed_at'])
        assert corrected['id'] == disputed['id']
        assert cli('analytics', 'show', winner['content_id'])['job_score'] == 40
        experiment_file = Path(directory) / 'experiment.json'
        experiment_file.write_text(json.dumps({'hypothesis': 'Working-note utility improves saves.',
            'start_date': '2020-01-01', 'metric': 'bookmarks_per_1k', 'content_ids': review['content_ids'],
            'learning': 'Scripted fixture interpretation; no causal claim.'}))
        experiment = cli('experiments', 'save', str(experiment_file))
        experiment_file.write_text(json.dumps({'id': experiment['id']}))
        experiment_before = {p.relative_to(root).as_posix(): p.read_bytes() for p in (root / 'data').rglob('*') if p.is_file()}
        cli('experiments', 'save', str(experiment_file))
        experiment_cutoff = datetime.now(timezone.utc).isoformat()
        measured_experiment = cli('experiments', 'measure', experiment['id'], '--as-of', experiment_cutoff)
        assert measured_experiment['sample_size'] == 5
        assert measured_experiment['groups'][0]['median'] == 4
        assert measured_experiment['conclusion'] == 'DESCRIPTIVE_ONLY'
        assert {p.relative_to(root).as_posix(): p.read_bytes() for p in (root / 'data').rglob('*') if p.is_file()} == experiment_before
        pending_compound = cli('compound', winner['content_id'])
        compound_task = cli('tasks', 'show', pending_compound['task_id'])
        parent_ref = compound_task['inputs']['parent_content']['source_reference'][0]
        additional_ref = next(i['source_reference'][0] for i in chosen
                              if i['source_reference'][0] != parent_ref)
        enriched = cli('tasks', 'cite', compound_task['id'], '--source', additional_ref['source_id'],
                       '--start-line', str(additional_ref['start_line']), '--end-line', str(additional_ref['end_line']),
                       '--quote', additional_ref['quote'])
        assert enriched['inputs']['performance'] == compound_task['inputs']['performance']
        assert enriched['inputs']['extra_source_reference'] == [additional_ref]
        moves = [('A decision context field for the next handoff', 'utility', 'checklist', 'Bookmarks / Saves',
                  'Make the next handoff record include the question that changed the decision.', []),
                 ('The handoff case where a named owner was still not enough', 'argument', 'contrarian take', 'Conversation',
                  'Show the scope limit using a documented exception.', ['Capture a real exception before writing.']),
                 ('A working handoff guide with a reusable decision log', 'format', 'X article', 'Authority',
                  'A longer guide with a reusable log and sourced walkthrough.', ['Capture the actual walkthrough and log fields.'])]
        answer = Path(directory) / 'compound.json'
        answer.write_text(json.dumps({'assessment': 'Measured saves beat the matched median; the reason is still a hypothesis.',
            'opportunities': [{'topic': topic, 'addition': addition, 'new_value': value,
                'rationale': 'Scripted fictional opportunity for offline workflow verification.',
                'platform': 'x_article' if fmt == 'X article' else 'x', 'format': fmt, 'job': job,
                'source_reference': [parent_ref, additional_ref], 'evidence_gaps': gaps}
                for topic, addition, fmt, job, value, gaps in moves]}))
        opportunities = cli('tasks', 'complete', pending_compound['task_id'], str(answer))
        assert len(opportunities) == 3
        assert len(cli('compound', winner['content_id'])) == 3
        assert len(cli('progress')['capture_requests']) == 2
        assert cli('progress')['stage'] == 'PLAN'
        extra_idea = next(i for i in cli('ideas', 'list') if i['id'] not in {i['id'] for i in chosen})
        waiting = cli('draft', 'x', '--idea', extra_idea['id'])
        packet = cli('tasks', 'show', waiting['task_id'])
        assert packet['inputs']['creator_feedback'][0]['id'] == feedback['id']
        assert packet['inputs']['source_context']['version'] == 2
        long_file = Path(directory) / 'long-pause.txt'
        long_file.write_text('Moderator: [Pause while reviewing the previously captured notes.]\n' * 400)
        long_source = cli('capture', str(long_file))
        empty = Path(directory) / 'empty-window.json'
        empty.write_text(json.dumps({'ideas': []}))
        while True:
            mining = cli('mine', long_source['id'])
            if isinstance(mining, list):
                break
            assert mining['status'] == 'PENDING'
            window = cli('tasks', 'show', mining['task_id'])
            assert len(window['inputs']['text']) <= 16000
            cli('tasks', 'complete', mining['task_id'], str(empty))
        coverage = cli('mining', long_source['id'])
        assert coverage['status'] == 'COMPLETED' and coverage['total_chunks'] > 1
        assert coverage['source_chars'] == coverage['covered_chars']
        # A new source passage can attach to a supplied earlier topic through
        # the same result contract a stateless model provider receives.
        earlier = chosen[1]
        extra_file = Path(directory) / 'repeated-topic.txt'
        extra_file.write_text(earlier['source_reference'][0]['quote'] + '\n')
        repeat_source = cli('capture', str(extra_file))
        repeat_task = cli('tasks', 'show', cli('mine', repeat_source['id'])['task_id'])
        supplied = next(i for i in repeat_task['inputs']['existing_ideas'] if i['id'] == earlier['id'])
        content_before = {p.name:p.read_bytes() for p in (root / 'data/content').glob('*') if p.is_file()}
        idea_count = len(cli('ideas', 'list'))
        answer.write_text(json.dumps({'ideas': [{'topic': supplied['topic'], 'existing_idea_id': supplied['id'],
            'category': supplied['category'], 'quote': earlier['source_reference'][0]['quote'],
            'start_line': 1, 'end_line': 1}]}))
        attached = cli('tasks', 'complete', repeat_task['id'], str(answer))[0]
        assert attached['id'] == earlier['id'] and len(cli('ideas', 'list')) == idea_count
        assert any(ref['source_id'] == repeat_source['id'] for ref in attached['source_reference'])
        assert {p.name:p.read_bytes() for p in (root / 'data/content').glob('*') if p.is_file()} == content_before
        # Simulate an older bundled asset while retaining real creator state and
        # pending task snapshots. The installed engine supplies the incoming version.
        intelligence = root / '.contentmaxxing'
        upgrade_file = intelligence / 'prompts/quality-checks.md'
        upgrade_file.write_text('Previous fictional release quality checks.\n')
        manifest_path = intelligence / 'intelligence-manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['files']['prompts/quality-checks.md'] = hashlib.sha256(upgrade_file.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest))
        custom_skill = intelligence / 'skills/linkedin/SKILL.md'
        custom_skill.write_text(custom_skill.read_text() + '\nFictional creator customization.\n')
        custom_before = custom_skill.read_bytes()
        data_before = {p.relative_to(root).as_posix(): p.read_bytes() for p in (root / 'data').rglob('*') if p.is_file()}
        preview = cli('upgrade', '--dry-run')
        assert preview['write'] == ['prompts/quality-checks.md']
        upgraded = cli('upgrade')
        assert upgraded['write'] == preview['write']
        assert 'skills/linkedin/SKILL.md' in upgraded['preserved']
        assert upgrade_file.read_bytes() == (package / 'prompts/quality-checks.md').read_bytes()
        assert custom_skill.read_bytes() == custom_before
        assert {p.relative_to(root).as_posix(): p.read_bytes() for p in (root / 'data').rglob('*') if p.is_file()} == data_before
        assert cli('upgrade')['upgrade_id'] is None
        backup = Path(directory) / 'portable.zip'
        cli('export', '--output', str(backup))
        voice = voice_path.read_bytes()
        restored = Path(directory) / 'restored'
        with zipfile.ZipFile(backup) as archive:
            assert not any('.contentmaxxing-agent/' in name for name in archive.namelist())
            archive.extractall(restored)
        assert (restored / 'data/creator/VOICE.md').read_bytes() == voice
        assert (restored / '.contentmaxxing/intelligence-manifest.json').read_bytes() == manifest_path.read_bytes()
        assert (restored / upgraded['report']).is_file()
        assert cli('upgrade', '--dry-run', creator_root=restored)['write'] == []
        assert cli('voice', 'show', voice_proposal['id'], creator_root=restored)['status'] == 'APPLIED'
        assert cli('experiments', 'measure', experiment['id'], '--as-of', experiment_cutoff, creator_root=restored) == measured_experiment
        assert (restored / 'data/feedback' / (feedback['id'] + '.json')).exists()
        assert list((restored / 'data/mining').glob('mine_*.json'))
        assert list((restored / 'data/revisions').glob('rev_*.json'))
        cli('uninstall', '--agent', 'codex', '--path', str(root), workspace=False)
        assert voice_path.read_bytes() == voice
        assert len(list((root / 'data/content').glob('*.json'))) == 5
        editorial_root = Path(directory) / 'editorial-creator'
        def editorial(*args):
            return cli(*args, creator_root=editorial_root)
        editorial('init')
        editorial('onboard', '--profile', str(fixtures / 'creator.json'))
        source = editorial('capture', str(fixtures / 'transcript.txt'))
        mining = editorial('mine', source['id'])
        mine_task = editorial('tasks', 'show', mining['task_id'])
        quote = mine_task['inputs']['text'].splitlines()[1]
        answer = Path(directory) / 'editorial-response.json'
        answer.write_text(json.dumps({'ideas': [{'topic': 'Store the question next to the decision',
            'quote': quote, 'start_line': 2, 'end_line': 2, 'category': 'working process'}]}))
        editorial('tasks', 'complete', mining['task_id'], str(answer))
        pending = editorial('plan', 'week')
        plan_task = editorial('tasks', 'show', pending['task_id'])
        candidate = plan_task['inputs']['candidates'][0]
        answer.write_text(json.dumps({'strategy': 'Keep the original decision context useful.',
            'slots': [{'idea_id': candidate['id'], 'platform': 'x', 'format': 'short post',
                'job': 'Bookmarks / Saves', 'angle': 'Save the question with its decision',
                'reader_payoff': 'Know why the decision was made.', 'reason': 'A directly documented practice.',
                'source_reference': candidate['source_reference'], 'basis': 'source',
                'performance_ids': [], 'experiment_id': None}], 'deferred': [], 'questions': []}))
        plan = editorial('tasks', 'complete', pending['task_id'], str(answer))[0]
        assert editorial('plan', 'week')['id'] == plan['id']
        execution = editorial('create', '--plan', plan['id'])
        draft_id = execution['run']['stages'][1]['slots'][0]['task_id']
        draft = editorial('tasks', 'show', draft_id)
        assert draft['inputs']['editorial_brief']['reader_payoff'] == 'Know why the decision was made.'
        answer.write_text(json.dumps({'body': quote, 'title': '', 'claims': [],
            'quality_notes': ['Literal fictional fixture.'], 'framework': None}))
        editorial('tasks', 'complete', draft_id, str(answer))
        completed = editorial('create', '--plan', plan['id'])
        assert completed['plan']['status'] == 'COMPLETED'
        assert len(editorial('create', '--plan', plan['id'])['plan']['content_ids']) == 1
        assert editorial('progress')['next_action']['command'] == 'review'
        evaluation = Path(directory) / 'editorial-eval'
        prepared = cli('evals', 'prepare', '--output', str(evaluation), '--label', 'installed-smoke', workspace=False)
        assert len(prepared['cases']) == 6
        malformed = evaluation / 'responses/invalid.json'
        malformed.write_text('{unfinished')
        evaluated = cli('evals', 'submit', '--run', str(evaluation), '--case', 'missing-proof', '--file', str(malformed), workspace=False)
        assert next(c for c in evaluated['cases'] if c['id'] == 'missing-proof')['status'] == 'FAIL'
        return {'package': str(package), 'commands': 19, 'drafts': 5, 'winner_lift': 10,
                'voice_analysis_apply_resume_export': 'passed',
                'workspace_upgrade_preservation_and_export': 'passed',
                'mining_existing_topic_attachment': 'passed',
                'experiment_measurement_idempotence_and_export': 'passed',
                'analytics_conflict_inspection_and_correction': 'passed',
                'editorial_eval_cases': 6, 'invalid_eval_response_retained': True,
                'source_retrieval': 'passed', 'feedback_in_next_task_and_export': 'passed',
                'long_source_resume': 'passed', 'same_id_revision_and_history': 'passed',
                'editorial_plan_and_briefs': 'passed',
                'compound_tasks_and_capture_gaps': 'passed',
                'compound_pending_evidence_attachment': 'passed',
                'compound_opportunities': 3, 'connector_calls': 0, 'model_api_calls': 0,
                'export_restore': 'passed', 'uninstall_preserves_creator': 'passed',
                'welcome_sha256': hashlib.sha256((package / 'assets/welcome.png').read_bytes()).hexdigest(),
                'notice': 'Fictional data, literal external-task responses, simulated manual publication. Host discovery and writing quality are not certified by this smoke test.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output')
    args = parser.parse_args()
    keys = {key: '' for key in ('TYPEFULLY_API_KEY', 'CONTENTMAXXING_API_KEY', 'OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'GEMINI_API_KEY')}
    with patch.dict(os.environ, keys), patch('socket.create_connection', side_effect=AssertionError('Network access forbidden in core smoke test')):
        result = smoke()
    text = json.dumps(result, indent=2) + '\n'
    if args.output:
        Path(args.output).write_text(text)
    print(text, end='')
