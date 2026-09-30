import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from contentmaxxing.analytics import derived, normalize_metrics, winners
from contentmaxxing.engine import Engine
from contentmaxxing.providers import PendingTask
from contentmaxxing.store import Store

FIXTURES = Path(__file__).parent / 'fixtures'


class WorkspaceFixture:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        Store(self.temp.name).init('extractive')
        self.engine = Engine(self.temp.name)
        self.engine.onboard(json.loads((FIXTURES / 'creator.json').read_text()))
        self.source = self.engine.capture(FIXTURES / 'transcript.txt', consent='fictional')
        self.ideas = self.engine.mine(self.source['id'])

    def tearDown(self):
        self.temp.cleanup()

    def post(self, index=0, job='Bookmarks / Saves'):
        idea = self.ideas[index]
        self.engine.select(idea['id'], job=job)
        return self.engine.draft(idea['id'])[0]

    def publish(self, post):
        self.engine.transition(post['id'], 'APPROVED')
        return self.engine.transition(post['id'], 'PUBLISHED', url='https://example.com/' + post['id'],
            published_at=(datetime.now(timezone.utc) - timedelta(days=2)).isoformat())


class WorkspaceTest(WorkspaceFixture, unittest.TestCase):

    def test_extraction_every_topic_with_exact_reference(self):
        self.assertEqual(len(self.ideas), 6)
        for idea in self.ideas:
            self.engine.store.validate_reference(idea['source_reference'][0])
            self.assertIsNone(idea['format'])
            self.assertEqual(idea['status'], 'BACKLOG')
        restored = Engine(self.temp.name).store.list('ideas')
        self.assertEqual({i['id'] for i in restored}, {i['id'] for i in self.ideas})

    def test_capture_and_idea_duplicates_are_idempotent(self):
        self.assertEqual(self.source['id'], self.engine.capture(FIXTURES / 'transcript.txt')['id'])
        self.engine.mine(self.source['id'])
        self.assertEqual(len(self.engine.store.list('ideas')), 6)

    def test_status_requires_review_and_real_publication(self):
        post = self.post()
        self.assertEqual(post['status'], 'NEEDS_REVIEW')
        with self.assertRaises(ValueError):
            self.engine.transition(post['id'], 'PUBLISHED', url='https://example.com')
        with self.assertRaises(ValueError):
            self.engine.transition(post['id'], 'SCHEDULED', scheduled_at=datetime.now(timezone.utc).isoformat())
        self.engine.transition(post['id'], 'APPROVED')
        edited = self.engine.edit(post['id'], post['body'] + ' Check the next owner.')
        self.assertEqual(edited['status'], 'NEEDS_REVIEW')
        self.assertIsNone(edited['approved_at'])

    def test_null_zero_and_job_rates(self):
        metrics = normalize_metrics({'impressions': 1000, 'bookmarks': 20, 'profile_visits': 50,
                                    'new_followers': 10, 'unfollows': 12})
        values = derived(metrics)
        self.assertEqual(values['bookmarks_per_1k'], 20)
        self.assertEqual(values['profile_to_follow_conversion'], .2)
        self.assertEqual(metrics['net_followers'], -2)
        self.assertIsNone(values['share_rate'])
        self.assertIsNone(derived(normalize_metrics({'impressions': 0, 'bookmarks': 0}))['save_rate'])
        self.assertEqual(derived(normalize_metrics({'impressions': 100, 'bookmarks': 0}))['save_rate'], 0)

    def test_winners_and_new_value_compound(self):
        ids = []
        for index in range(5):
            post = self.publish(self.post(index))
            ids.append(post['id'])
            self.engine.manual_metrics(post['id'], {'impressions': 1000, 'bookmarks': 40 if index == 0 else 4})
        found = winners(self.engine.store)
        self.assertEqual([i['content_id'] for i in found], ids[:1])
        ideas = self.engine.compound(ids[0])
        self.assertEqual({i['addition'] for i in ideas}, {'utility', 'argument', 'format'})
        self.assertTrue(all(i['parent_content_id'] == ids[0] for i in ideas))
        self.assertEqual([i['id'] for i in self.engine.compound(ids[0])], [i['id'] for i in ideas])
        with self.assertRaises(ValueError):
            self.engine.compound(ids[1])
        report = self.engine.report()
        self.assertEqual(report['sample_size'], 5)
        self.assertIsNone(report['growth']['attributed_new_followers'])

    def test_unknown_proof_job_does_not_fallback_to_impressions(self):
        for index in range(5):
            post = self.publish(self.post(index, job='Trust'))
            self.engine.manual_metrics(post['id'], {'impressions': 10000 if index == 0 else 100})
        self.assertEqual(winners(self.engine.store), [])

    def test_external_output_checks_provenance_before_persisting(self):
        engine = Engine(self.temp.name, provider_name='external')
        with self.assertRaises(PendingTask) as pending:
            engine.mine(self.source['id'])
        task_id = pending.exception.task_id
        output = {'ideas': [{'topic': 'A fake event', 'category': 'story', 'quote': 'This never happened',
                             'start_line': 1, 'end_line': 1}]}
        with self.assertRaises(ValueError):
            engine.complete_task(task_id, output)
        self.assertEqual(len(engine.store.list('ideas')), 6)
        output['ideas'][0].update(topic='Specific handoff ownership', quote='Morgan: We used to lose client questions because each call lived in a different folder.')
        imported = engine.complete_task(task_id, output)
        self.assertEqual(imported[0]['topic'], 'Specific handoff ownership')
        self.assertEqual(engine.complete_task(task_id, output)[0]['id'], imported[0]['id'])

    def test_brand_and_sources_are_preserved(self):
        voice = self.engine.store.data / 'creator/VOICE.md'
        voice.write_text('Creator edited voice')
        with self.assertRaises(ValueError):
            self.engine.onboard({'name': 'Someone else'})
        self.assertEqual(voice.read_text(), 'Creator edited voice')
        original = self.engine.store.root / self.source['path']
        original.write_text('Changed transcript')
        with self.assertRaises(ValueError):
            self.engine.store.validate_reference(self.ideas[0]['source_reference'][0])


if __name__ == '__main__':
    unittest.main()
