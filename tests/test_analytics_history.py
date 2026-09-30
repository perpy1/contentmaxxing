import json
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

from contentmaxxing.analytics import inspect_measurement, latest_snapshots, score, winners
from contentmaxxing.editorial import Editorial
from contentmaxxing.cli import main
from contentmaxxing.compounding import Compounding
from contentmaxxing.engine import Engine
from contentmaxxing.providers import PendingTask
from contentmaxxing.store import new_id
from test_vertical import WorkspaceFixture


class AnalyticsHistoryTests(WorkspaceFixture, unittest.TestCase):
    def published(self, index=0, job='Bookmarks / Saves'):
        post = self.post(index, job)
        self.engine.transition(post['id'], 'APPROVED')
        return self.engine.transition(post['id'], 'PUBLISHED',
            url='https://example.com/fictional/' + post['id'], published_at='2026-09-20T12:00:00Z')

    def csv(self, post, values, observed_at='2026-09-24T12:00:00Z'):
        path = self.engine.store.root / 'metrics.csv'
        path.write_text('content_id,observed_at,' + ','.join(values) + '\n' + post['id'] + ',' + observed_at + ',' + ','.join(str(v) for v in values.values()) + '\n')
        return self.engine.import_csv(path)[0]

    def snapshot(self):
        return {str(p.relative_to(self.engine.store.data)):p.read_bytes()
                for p in self.engine.store.data.rglob('*') if p.is_file()}

    def test_backfilled_older_measurement_does_not_replace_idea_performance(self):
        post = self.published()
        self.engine.manual_metrics(post['id'], {'impressions': 1000, 'bookmarks': 40}, '2026-09-24T12:00:00Z')
        before = self.engine.store.get('ideas', post['idea_id'])
        self.engine.manual_metrics(post['id'], {'impressions': 100, 'bookmarks': 1}, '2026-09-21T12:00:00Z')
        self.assertEqual(self.engine.store.get('ideas', post['idea_id']), before)
        self.assertEqual(len(self.engine.store.list('analytics')), 2)

    def test_equivalent_timestamp_is_same_observation_and_repeat_is_read_only(self):
        post = self.published()
        first = self.csv(post, {'impressions': 1000, 'bookmarks': 40})
        before = self.snapshot()
        again = self.csv(post, {'impressions': 1000, 'bookmarks': 40}, '2026-09-24T08:00:00-04:00')
        self.assertEqual(first['id'], again['id'])
        self.assertEqual(self.snapshot(), before)
        corrected = self.csv(post, {'impressions': 1000, 'bookmarks': 4}, '2026-09-24T08:00:00-04:00')
        self.assertEqual(corrected['id'], first['id'])
        self.assertEqual(len(self.engine.store.list('analytics')), 1)
        self.assertEqual(self.engine.store.get('ideas', post['idea_id'])['performance'][post['id']]['metrics']['bookmarks'], 4)

    def test_conflicting_origins_cannot_create_winner_or_editorial_precedent(self):
        posts = [self.published(i) for i in range(4)]
        for index, post in enumerate(posts):
            self.engine.manual_metrics(post['id'], {'impressions': 1000, 'bookmarks': 40 if index == 0 else 4}, '2026-09-24T12:00:00Z')
        self.assertEqual(winners(self.engine.store)[0]['content_id'], posts[0]['id'])
        self.csv(posts[0], {'impressions': 1000, 'bookmarks': 4})
        self.assertEqual(winners(self.engine.store), [])
        report = self.engine.report('2026-09-25T00:00:00Z')
        self.assertNotIn(posts[0]['id'], report['top_posts'])
        self.assertEqual(report['compound'], [])
        host = Engine(self.temp.name, provider_name='external')
        before = len(host.store.list('tasks'))
        with self.assertRaisesRegex(ValueError, 'Not a measured winner'):
            host.compound(posts[0]['id'], as_of='2026-09-25T00:00:00Z')
        self.assertEqual(len(host.store.list('tasks')), before)

    def test_future_import_does_not_poison_current_idea_performance(self):
        post = self.published()
        self.engine.manual_metrics(post['id'], {'impressions': 1000, 'bookmarks': 4}, '2026-09-24T12:00:00Z')
        before = self.engine.store.get('ideas', post['idea_id'])
        self.engine.manual_metrics(post['id'], {'impressions': 1000, 'bookmarks': 400}, '2099-09-24T12:00:00Z')
        self.assertEqual(self.engine.store.get('ideas', post['idea_id']), before)

    def test_conflicts_are_per_metric_and_do_not_borrow_unknown_denominators(self):
        post = self.published(job='Reach')
        manual = self.engine.manual_metrics(post['id'], {'impressions': 1000, 'bookmarks': 40}, '2026-09-24T12:00:00Z')
        imported = self.csv(post, {'impressions': 1000, 'bookmarks': 4})
        snapshot = latest_snapshots(self.engine.store)[post['id']]
        self.assertEqual(score(post, snapshot, self.engine.store.registry), 1000)
        self.assertIsNone(snapshot['derived']['bookmarks_per_1k'])
        self.assertIn('bookmarks', snapshot['conflicts']['metrics'])
        self.assertCountEqual(snapshot['measurement_ids'], [manual['id'], imported['id']])
        # A partial import is not permission to borrow another origin's counts.
        self.csv(post, {'bookmarks': 40})
        snapshot = latest_snapshots(self.engine.store)[post['id']]
        self.assertEqual(snapshot['metrics']['bookmarks'], 40)
        self.assertIsNone(snapshot['metrics']['impressions'])
        self.assertIsNone(snapshot['derived']['bookmarks_per_1k'])
        self.assertIsNone(score(post, snapshot, self.engine.store.registry))

    def test_derived_agreement_uses_complete_observations_not_merged_counts(self):
        post = self.published()
        self.engine.manual_metrics(post['id'], {'impressions': 1000, 'bookmarks': 20}, '2026-09-24T12:00:00Z')
        self.csv(post, {'impressions': 2000, 'bookmarks': 40})
        snapshot = latest_snapshots(self.engine.store)[post['id']]
        self.assertEqual(score(post, snapshot, self.engine.store.registry), 20)
        self.assertIsNone(snapshot['metrics']['impressions'])
        self.assertIsNone(snapshot['metrics']['bookmarks'])
        self.assertEqual(snapshot['conflicts']['derived'], [])
        exp = self.engine.experiment({'hypothesis': 'Test saves.', 'start_date': '2026-09-01',
                                      'metric': 'bookmarks_per_1k', 'content_ids': [post['id']]})
        measured = self.engine.measure_experiment(exp['id'], '2026-09-25T00:00:00Z')
        self.assertEqual(measured['content'][0]['value'], 20)
        self.assertEqual(measured['content'][0]['measurement_ids'], snapshot['measurement_ids'])

    def test_resolution_is_independent_of_ingestion_order_and_raw_records_are_preserved(self):
        post = self.published()
        self.engine.manual_metrics(post['id'], {'impressions': 1000, 'bookmarks': 40}, '2026-09-24T08:00:00-04:00')
        self.csv(post, {'impressions': 1000, 'bookmarks': 4})
        before = self.snapshot()
        expected = latest_snapshots(self.engine.store)
        original = self.engine.store.list
        with patch.object(self.engine.store, 'list', side_effect=lambda collection: list(reversed(original(collection)))):
            self.assertEqual(latest_snapshots(self.engine.store), expected)
        self.assertEqual(expected[post['id']]['observed_at'], '2026-09-24T12:00:00+00:00')
        self.assertEqual(self.snapshot(), before)

    def test_legacy_equivalent_timestamp_duplicates_keep_ids_and_receive_same_correction(self):
        post = self.published()
        first = self.csv(post, {'impressions': 1000, 'bookmarks': 40})
        duplicate = dict(first, id=new_id('metric'), observed_at='2026-09-24T08:00:00-04:00')
        duplicate['metrics'] = dict(first['metrics'], bookmarks=4)
        self.engine.store.put('analytics', duplicate)
        self.assertIsNone(latest_snapshots(self.engine.store)[post['id']]['metrics']['bookmarks'])
        self.csv(post, {'impressions': 1000, 'bookmarks': 7})
        records = self.engine.store.list('analytics')
        self.assertEqual({r['id'] for r in records}, {first['id'], duplicate['id']})
        self.assertEqual({r['metrics']['bookmarks'] for r in records}, {7})
        self.assertEqual(latest_snapshots(self.engine.store)[post['id']]['derived']['bookmarks_per_1k'], 7)
        before = self.snapshot()
        self.csv(post, {'impressions': 1000, 'bookmarks': 7})
        self.assertEqual(self.snapshot(), before)

    def test_latest_unknown_does_not_fallback_and_asof_inspection_is_read_only(self):
        post = self.published()
        first = self.engine.manual_metrics(post['id'], {'impressions': 1000, 'bookmarks': 40}, '2026-09-23T12:00:00Z')
        self.engine.manual_metrics(post['id'], {'impressions': 1000}, '2026-09-24T12:00:00Z')
        before = self.snapshot()
        older = inspect_measurement(self.engine.store, post['id'], '2026-09-23T13:00:00Z')
        self.assertEqual(older['job_score'], 40)
        self.assertEqual(older['observations'][0]['id'], first['id'])
        latest = inspect_measurement(self.engine.store, post['id'], '2026-09-25T00:00:00Z')
        self.assertIsNone(latest['job_score'])
        self.assertEqual(latest['metric_status'], 'METRIC_MISSING')
        output = StringIO()
        with redirect_stdout(output):
            code = main(['--workspace', self.temp.name, 'analytics', 'show', post['id'], '--as-of', '2026-09-25T00:00:00Z'])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue()), latest)
        self.assertEqual(self.snapshot(), before)

    def test_new_plan_exposes_conflicts_and_old_compound_task_stays_frozen(self):
        posts = [self.published(i) for i in range(4)]
        for index, post in enumerate(posts):
            self.engine.manual_metrics(post['id'], {'impressions': 1000, 'bookmarks': 40 if index == 0 else 4}, '2026-09-24T12:00:00Z')
        host = Engine(self.temp.name, provider_name='external')
        with self.assertRaises(PendingTask) as pending:
            host.compound(posts[0]['id'], as_of='2026-09-25T00:00:00Z')
        frozen = host.store.get('tasks', pending.exception.task_id)
        self.csv(posts[0], {'impressions': 1000, 'bookmarks': 4})
        report = host.report('2026-09-25T00:00:00Z')
        context = Editorial(host).context({'x': 1}, 'UTC', report, 'standalone')
        measured = next(row for row in context['performance'] if row['content_id'] == posts[0]['id'])
        self.assertIsNone(measured['job_score'])
        self.assertEqual(measured['metric_status'], 'CONFLICTING_OBSERVATIONS')
        self.assertEqual(len(measured['measurement_ids']), 2)
        self.assertEqual(host.store.get('tasks', frozen['id']), frozen)
        with self.assertRaises(PendingTask) as reused:
            host.compound(posts[0]['id'])
        self.assertEqual(reused.exception.task_id, frozen['id'])
        Compounding(host).cancel(frozen['id'], 'Review new conflicting observations before another analysis.')
        with self.assertRaisesRegex(ValueError, 'Not a measured winner'):
            host.compound(posts[0]['id'], fresh=True, as_of='2026-09-25T00:00:00Z')

    def test_cli_winners_and_compound_share_explicit_cutoff(self):
        posts = [self.published(i) for i in range(4)]
        for index, post in enumerate(posts):
            self.engine.manual_metrics(post['id'], {'impressions': 1000, 'bookmarks': 40 if index == 0 else 4}, '2026-09-23T12:00:00Z')
            self.engine.manual_metrics(post['id'], {'impressions': 1000, 'bookmarks': 4}, '2026-09-24T12:00:00Z')
        args = ['--workspace', self.temp.name]
        output = StringIO()
        with redirect_stdout(output):
            code = main(args + ['analytics', 'winners', '--as-of', '2026-09-23T13:00:00Z'])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())[0]['content_id'], posts[0]['id'])
        self.assertEqual(winners(self.engine.store), [])
        output = StringIO()
        with redirect_stdout(output):
            code = main(args + ['compound', posts[0]['id'], '--as-of', '2026-09-23T13:00:00Z'])
        self.assertEqual(code, 0)
        self.assertEqual(len(json.loads(output.getvalue())), 3)

    def test_explicit_custom_derived_metrics_survive_but_builtin_rates_are_recomputed(self):
        post = self.published()
        item = self.engine.manual_metrics(post['id'], {'impressions': 1000, 'bookmarks': 20}, '2026-09-24T12:00:00Z')
        item['derived'].update(creator_qualified_inquiries=3, bookmarks_per_1k=999)
        self.engine.store.put('analytics', item)  # Simulate an inspectable custom metric extension.
        snapshot = latest_snapshots(self.engine.store)[post['id']]
        self.assertEqual(snapshot['derived']['bookmarks_per_1k'], 20)
        self.assertEqual(snapshot['derived']['creator_qualified_inquiries'], 3)
        exp = self.engine.experiment({'hypothesis': 'Test qualified inquiries.', 'start_date': '2026-09-01',
            'metric': 'creator_qualified_inquiries', 'content_ids': [post['id']]})
        self.assertEqual(self.engine.measure_experiment(exp['id'])['content'][0]['value'], 3)
        self.csv(post, {'impressions': 1000, 'bookmarks': 20})
        measured = self.engine.measure_experiment(exp['id'])
        self.assertEqual(measured['sample_size'], 0)
        self.assertEqual(measured['content'][0]['status'], 'CONFLICTING_OBSERVATIONS')


if __name__ == '__main__':
    unittest.main()
