import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from contentmaxxing.cli import main
from contentmaxxing.engine import Engine
from contentmaxxing.experiments import Experiments
from contentmaxxing.export import export_workspace
from contentmaxxing.providers import PendingTask
from contentmaxxing.store import atomic_text
from test_vertical import WorkspaceFixture


class ExperimentTests(WorkspaceFixture, unittest.TestCase):
    def experiment(self, **changes):
        return self.engine.experiment(dict(hypothesis='Working notes help people save the process',
            metric='bookmarks_per_1k', start_date='2026-09-01', **changes))

    def snapshot(self):
        return {str(p.relative_to(self.engine.store.data)): p.read_bytes()
                for p in self.engine.store.data.rglob('*') if p.is_file()}

    def published(self, index, published_at='2026-09-22T12:00:00+00:00', job='Bookmarks / Saves'):
        post = self.post(index, job)
        self.engine.transition(post['id'], 'APPROVED')
        return self.engine.transition(post['id'], 'PUBLISHED',
            url='https://example.com/fictional/' + post['id'], published_at=published_at)

    def test_repeated_save_does_not_repeat_learning_or_rewrite_records(self):
        post = self.post()
        exp = self.experiment(content_ids=[post['id']], learning='Collect a larger sample.')
        before = self.snapshot()
        self.engine.experiment({'id': exp['id']})
        self.assertEqual(self.snapshot(), before)
        self.engine.experiment({'id': exp['id'], 'next_action': 'Try a second topic.'})
        notes = (self.engine.store.data / 'creator/LEARNINGS.md').read_text()
        self.assertEqual(notes.count('Collect a larger sample.'), 1)

    def test_removing_content_clears_reverse_link_preserving_draft(self):
        post = self.post()
        exp = self.experiment(content_ids=[post['id']])
        self.engine.experiment({'id': exp['id'], 'content_ids': []})
        current = self.engine.store.get('content', post['id'])
        self.assertIsNone(current['experiment'])
        self.assertEqual(current['body'], post['body'])
        self.assertEqual(current['revision'], post['revision'])
        self.assertEqual(current['status'], post['status'])

    def test_conflicting_assignment_and_duplicates_reject_before_any_writes(self):
        post = self.post()
        self.experiment(content_ids=[post['id']])
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'already belongs'):
            self.experiment(content_ids=[post['id']])
        self.assertEqual(self.snapshot(), before)
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            self.experiment(content_ids=[post['id'], post['id']])
        self.assertEqual(self.snapshot(), before)

    def test_corrected_or_cleared_learning_preserves_manual_and_legacy_notes(self):
        path = self.engine.store.data / 'creator/LEARNINGS.md'
        legacy = path.read_text() + '\nMy own observation: keep the working notes.\n- Experiment exp_111111111111: Historical note.\n'
        path.write_text(legacy)
        exp = self.experiment(learning='An early interpretation.')
        self.engine.experiment({'id': exp['id'], 'learning': 'Corrected after reviewing the source.'})
        self.assertTrue(path.read_text().startswith(legacy))
        self.assertNotIn('An early interpretation.', path.read_text())
        self.engine.experiment({'id': exp['id'], 'learning': None})
        self.assertNotIn('Corrected after reviewing the source.', path.read_text())
        self.assertTrue(path.read_text().startswith(legacy))

    def test_interrupted_save_repairs_links_and_notes_without_duplicate_learning(self):
        post = self.post()
        exp = self.experiment(content_ids=[post['id']], learning='Tentative.')
        original = self.engine.store.put
        def fail_link(collection, value):
            if collection == 'content':
                raise OSError('Interrupted after experiment commit')
            return original(collection, value)
        with patch.object(self.engine.store, 'put', side_effect=fail_link):
            with self.assertRaises(OSError):
                self.engine.experiment({'id': exp['id'], 'content_ids': [], 'learning': 'Revised.'})
        self.engine.experiment({'id': exp['id']})
        self.assertIsNone(self.engine.store.get('content', post['id'])['experiment'])
        notes = (self.engine.store.data / 'creator/LEARNINGS.md').read_text()
        self.assertNotIn('Tentative.', notes)
        self.assertEqual(notes.count('Revised.'), 1)

    def test_measure_is_read_only_and_separates_metric_from_interpretation(self):
        first = self.published(0)
        second = self.published(1, '2026-09-23T12:00:00+00:00')
        missing = self.published(2)
        draft = self.post(3)
        exp = self.experiment(content_ids=[p['id'] for p in (first, second, missing, draft)],
                              learning='Unverified explanation from the creator.')
        metric = self.engine.manual_metrics(first['id'], {'impressions': 1000, 'bookmarks': 40}, '2026-09-24T12:00:00Z')
        self.engine.manual_metrics(first['id'], {'impressions': 1000, 'bookmarks': 90}, '2026-10-01T12:00:00Z')
        self.engine.manual_metrics(second['id'], {'impressions': 1000, 'bookmarks': 0}, '2026-09-24T12:00:00Z')
        self.engine.manual_metrics(missing['id'], {'impressions': 1000}, '2026-09-24T12:00:00Z')
        before = self.snapshot()
        result = self.engine.measure_experiment(exp['id'], '2026-09-25T00:00:00Z')
        self.assertEqual(result['sample_size'], 2)
        self.assertEqual(result['groups'][0]['median'], 20)
        self.assertEqual(result['groups'][0]['observation_age_hours'], [24, 48])
        rows = {r['content_id']: r for r in result['content']}
        self.assertEqual(rows[first['id']]['measurement_ids'], [metric['id']])
        self.assertEqual(rows[second['id']]['value'], 0)
        self.assertEqual(rows[missing['id']]['status'], 'METRIC_MISSING')
        self.assertEqual(rows[draft['id']]['status'], 'UNPUBLISHED')
        self.assertEqual(result['recorded_interpretation']['learning'], exp['learning'])
        self.assertEqual(result['conclusion'], 'DESCRIPTIVE_ONLY')
        self.assertEqual(self.snapshot(), before)

    def test_manual_edits_inside_generated_notes_are_not_overwritten(self):
        exp = self.experiment(learning='Tentative result.')
        path = self.engine.store.data / 'creator/LEARNINGS.md'
        path.write_text(path.read_text().replace('Tentative result.', 'My correction inside the section.'))
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'notes were edited'):
            self.engine.experiment({'id': exp['id'], 'learning': 'New claim.'})
        self.assertEqual(self.snapshot(), before)

    def test_latest_missing_does_not_fallback_and_tied_origins_conflict(self):
        first, second = self.published(0), self.published(1)
        exp = self.experiment(content_ids=[first['id'], second['id']])
        self.engine.manual_metrics(first['id'], {'impressions': 1000, 'bookmarks': 20}, '2026-09-23T12:00:00Z')
        self.engine.manual_metrics(first['id'], {'impressions': 1000}, '2026-09-24T12:00:00Z')
        manual = self.engine.manual_metrics(second['id'], {'impressions': 1000, 'bookmarks': 20}, '2026-09-24T12:00:00Z')
        path = self.engine.store.root / 'observations.csv'
        path.write_text('content_id,observed_at,impressions,bookmarks\n' + second['id'] + ',2026-09-24T08:00:00-04:00,1000,40\n')
        imported = self.engine.import_csv(path)[0]
        result = self.engine.measure_experiment(exp['id'], '2026-09-25T00:00:00Z')
        self.assertEqual(result['sample_size'], 0)
        self.assertEqual(result['statuses'], {'METRIC_MISSING': 1, 'CONFLICTING_OBSERVATIONS': 1})
        self.assertCountEqual(result['content'][1]['measurement_ids'], [manual['id'], imported['id']])
        # Equal-time records agreeing on the requested metric are one sample,
        # with both provenances retained, even if irrelevant raw values differ.
        path.write_text('content_id,observed_at,impressions,bookmarks\n' + second['id'] + ',2026-09-24T08:00:00-04:00,2000,40\n')
        self.engine.import_csv(path)
        result = self.engine.measure_experiment(exp['id'], '2026-09-25T00:00:00Z')
        self.assertEqual(result['sample_size'], 1)
        self.assertEqual(result['groups'][0]['median'], 20)
        self.assertEqual(len(result['content'][1]['measurement_ids']), 2)

    def test_publication_dates_use_timezone_and_groups_do_not_pool_jobs(self):
        import yaml
        config_path = self.engine.store.root / 'config.yaml'
        config = self.engine.store.config
        config['timezone'] = 'America/New_York'
        atomic_text(config_path, yaml.safe_dump(config))
        outside = self.published(0, '2026-09-22T02:00:00Z')  # September 21 locally.
        saves = self.published(1, '2026-09-22T04:00:00Z')
        reach = self.published(2, '2026-09-23T03:00:00Z', job='Reach')  # September 22 locally.
        exp = self.experiment(content_ids=[p['id'] for p in (outside, saves, reach)], end_date='2026-09-22')
        exp = self.engine.experiment({'id': exp['id'], 'start_date': '2026-09-22'})
        for post in (outside, saves, reach):
            self.engine.manual_metrics(post['id'], {'impressions': 1000, 'bookmarks': 10}, '2026-09-24T12:00:00Z')
        result = self.engine.measure_experiment(exp['id'], '2026-09-25T00:00:00Z')
        self.assertEqual(result['statuses'], {'OUTSIDE_PUBLICATION_WINDOW': 1, 'MEASURED': 2})
        self.assertEqual(len(result['groups']), 2)
        self.assertEqual({g['job'] for g in result['groups']}, {'Reach', 'Bookmarks / Saves'})
        self.assertTrue(all(g['samples'] == 1 for g in result['groups']))
        exp = self.engine.experiment({'id': exp['id'], 'metric': 'trust from customer interviews'})
        result = self.engine.measure_experiment(exp['id'], '2026-09-25T00:00:00Z')
        self.assertFalse(result['metric_supported'])
        self.assertEqual(result['statuses']['MANUAL_METRIC'], 2)
        self.assertEqual(result['groups'], [])

    def test_zero_denominator_and_no_observations_stay_unknown(self):
        first, second = self.published(0), self.published(1)
        exp = self.experiment(content_ids=[first['id'], second['id']])
        self.engine.manual_metrics(first['id'], {'impressions': 0, 'bookmarks': 0}, '2026-09-24T12:00:00Z')
        result = self.engine.measure_experiment(exp['id'], '2026-09-25T00:00:00Z')
        self.assertEqual(result['sample_size'], 0)
        self.assertEqual(result['statuses'], {'METRIC_MISSING': 1, 'NO_OBSERVATION': 1})

    def test_planning_gets_bounded_frozen_measurements_and_current_learning(self):
        from contentmaxxing.editorial import Editorial
        exp = self.experiment(learning='One tentative observation.')
        host = Engine(self.temp.name, provider_name='external')
        report = host.report('2026-09-25T00:00:00Z')
        with self.assertRaises(PendingTask) as pending:
            Editorial(host).request({'x': 1}, 'UTC', report)
        task = host.store.get('tasks', pending.exception.task_id)
        self.assertEqual(task['inputs']['experiments'][0]['id'], exp['id'])
        self.assertEqual(task['inputs']['experiment_measurements'][0]['sample_size'], 0)
        self.assertEqual(task['inputs']['experiment_measurements'][0]['recorded_interpretation']['learning'], exp['learning'])
        self.engine.experiment({'id': exp['id'], 'learning': 'Reconsidered.'})
        self.assertEqual(host.store.get('tasks', task['id']), task)
        context = Experiments(host.store).context(report['end_date'], max_chars=0)
        self.assertEqual(context['experiments'], [])
        self.assertEqual(context['experiment_coverage']['omitted'], 1)
        full = Experiments(host.store).context(report['end_date'])
        exact = Experiments(host.store).context(report['end_date'], max_chars=full['experiment_coverage']['chars'])
        self.assertEqual(exact['experiment_coverage']['supplied'], 1)
        too_small = Experiments(host.store).context(report['end_date'], max_chars=full['experiment_coverage']['chars'] - 1)
        self.assertEqual(too_small['experiment_coverage']['supplied'], 0)

    def test_interrupted_draft_recovery_respects_removed_experiment(self):
        exp = self.experiment()
        idea = self.engine.store.get('ideas', self.ideas[0]['id'])
        idea['experiment'] = exp['id']
        self.engine.store.put('ideas', idea)
        host = Engine(self.temp.name, provider_name='external')
        host.select(idea['id'], job='Bookmarks / Saves')
        with self.assertRaises(PendingTask) as pending:
            host.draft(idea['id'])
        task_id = pending.exception.task_id
        ref = idea['source_reference'][0]
        output = {'body': ref['quote'], 'title': '', 'claims': [], 'quality_notes': [], 'framework': None}
        put = host.store.put
        def fail_checkpoint(collection, item):
            if collection == 'tasks' and item['status'] == 'COMPLETED':
                raise OSError('Interrupted after draft and experiment links')
            return put(collection, item)
        with patch.object(host.store, 'put', side_effect=fail_checkpoint):
            with self.assertRaises(OSError):
                host.complete_task(task_id, output)
        post = host.store.list('content')[0]
        self.assertEqual(host.store.get('experiments', exp['id'])['content_ids'], [post['id']])
        host.experiment({'id': exp['id'], 'content_ids': []})
        host.edit(post['id'], 'Creator corrected the draft after the interruption.')
        recovered = host.complete_task(task_id, output)[0]
        self.assertIsNone(recovered['experiment'])
        self.assertEqual(recovered['body'], 'Creator corrected the draft after the interruption.')
        self.assertEqual(host.store.get('experiments', exp['id'])['content_ids'], [])

    def test_cli_measure_and_export_restore_keep_provenance(self):
        post = self.published(0)
        exp = self.experiment(content_ids=[post['id']], learning='Still tentative.')
        self.engine.manual_metrics(post['id'], {'impressions': 1000, 'bookmarks': 12}, '2026-09-24T12:00:00Z')
        output = StringIO()
        before = self.snapshot()
        with redirect_stdout(output):
            status = main(['--workspace', self.temp.name, 'experiments', 'measure', exp['id'], '--as-of', '2026-09-25T00:00:00Z'])
        self.assertEqual(status, 0)
        expected = json.loads(output.getvalue())
        self.assertEqual(expected['groups'][0]['median'], 12)
        self.assertEqual(self.snapshot(), before)
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / 'creator.zip'
            export_workspace(self.engine.store, archive)
            restored = Path(directory) / 'restored'
            shutil.unpack_archive(str(archive), str(restored))
            moved = Engine(restored)
            self.assertEqual(moved.measure_experiment(exp['id'], '2026-09-25T00:00:00Z'), expected)
            moved.experiment({'id': exp['id']})
            self.assertEqual((restored / 'data/creator/LEARNINGS.md').read_bytes(),
                             (self.engine.store.data / 'creator/LEARNINGS.md').read_bytes())
