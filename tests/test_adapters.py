import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from contentmaxxing.connectors.base import CapabilityError, Draft, PublishingConnector
from contentmaxxing.connectors.filesystem import FilesystemConnector
from contentmaxxing.connectors.typefully import TypefullyConnector, normalize_post
from contentmaxxing.providers import ExternalProvider, OpenAICompatibleProvider, PendingTask
from contentmaxxing.publishing import Publishing
from test_vertical import WorkspaceFixture


class AdapterTests(unittest.TestCase):
    def test_compatible_provider_uses_one_contract_for_operations(self):
        calls = []
        def transport(method, url, headers, body):
            calls.append((method, url, headers, body))
            return {'choices': [{'message': {'content': '{"answer": "sourced"}'}, 'finish_reason': 'stop'}]}
        provider = OpenAICompatibleProvider('https://models.example.test/v1', 'test-model', 'test-only-key', transport)
        task = {'id': 'task_012345abcdef', 'instructions': 'a modular skill', 'inputs': {'quote': 'real'}, 'output_contract': {'type': 'object'}}
        for operation in [provider.generate, provider.extract, provider.analyze, provider.classify]:
            self.assertEqual(operation(task), {'answer': 'sourced'})
        self.assertEqual(calls[0][1], 'https://models.example.test/v1/chat/completions')
        self.assertEqual(calls[0][3]['messages'][0]['content'], 'a modular skill')
        self.assertNotIn('test-only-key', json.dumps(task))
        with self.assertRaises(PendingTask):
            ExternalProvider().generate(task)

    def test_invalid_model_output_and_missing_model_fail(self):
        with self.assertRaises(ValueError):
            OpenAICompatibleProvider('https://models.example.test', '', '')
        provider = OpenAICompatibleProvider('http://localhost:1234/v1', 'model', '',
            lambda *args: {'choices': [{'message': {'content': 'not json'}}]})
        with self.assertRaises(ValueError):
            provider.generate({'instructions': 'skill', 'inputs': {}, 'output_contract': {}})

    def test_connector_protocol_and_missing_credentials(self):
        connector = TypefullyConnector(1, api_key='')
        self.assertIsInstance(connector, PublishingConnector)
        with self.assertRaisesRegex(CapabilityError, 'manual mode'):
            connector.list_accounts()
        with tempfile.TemporaryDirectory() as folder:
            fs = FilesystemConnector(folder)
            self.assertIsInstance(fs, PublishingConnector)
            item = fs.create_draft(Draft('post_012345abcdef', 'tiktok', 'Actual script'))
            self.assertEqual(len(fs.list_drafts()), 1)
            with self.assertRaises(CapabilityError):
                fs.publish_draft(item['id'], approved=True)

    def test_typefully_payload_platform_capabilities_and_no_auto_publish(self):
        calls = []
        def transport(method, url, headers, body):
            calls.append((method, url, headers, body))
            if url.endswith('/social-sets/7/'):
                return {'platforms': {'x': {'username': 'demo'}, 'linkedin': {'username': 'demo'}, 'substack': {'username': 'demo'}}}
            return {'id': 81, 'status': 'draft'}
        connector = TypefullyConnector(7, 'fictional-key', transport)
        for platform in ['x', 'linkedin', 'x_article', 'substack_note']:
            connector.create_draft(Draft('post_012345abcdef', platform, 'Working notes', 'Title'))
        payloads = [c[3] for c in calls if c[0] == 'POST']
        self.assertTrue(all('publish_at' not in body and 'share' not in body for body in payloads))
        article = payloads[2]['platforms']['x_article']
        self.assertEqual(article, {'content_markdown': '# Title\n\nWorking notes'})
        self.assertEqual(payloads[3]['platforms']['substack']['posts'], [{'text': 'Working notes'}])
        self.assertEqual(calls[0][2]['Authorization'], 'Bearer fictional-key')
        with self.assertRaises(CapabilityError):
            connector.create_draft(Draft('post_012345abcdef', 'tiktok', 'demo'))
        connector._account = {'platforms': {'x': {}}}
        with self.assertRaises(CapabilityError):
            connector.create_draft(Draft('post_012345abcdef', 'substack_note', 'demo'))

    def test_typefully_pagination_and_real_metric_shape(self):
        offsets = []
        def transport(method, url, headers, body):
            query = parse_qs(urlparse(url).query)
            offset = int(query['offset'][0])
            offsets.append(offset)
            return {'results': [{'post_id': str(offset), 'metrics': {'impressions': 1200,
                    'engagement': {'total': 80, 'saves': 6, 'profile_clicks': 12}}}],
                    'next': 'next' if offset == 0 else None}
        connector = TypefullyConnector(7, 'fictional-key', transport)
        posts = connector.get_post_analytics('2026-01-01', '2026-01-07')
        self.assertEqual(offsets, [0, 1])
        self.assertEqual(normalize_post(posts[0])['bookmarks'], 6)
        self.assertNotIn('new_followers', normalize_post(posts[0]))
        with self.assertRaises(CapabilityError):
            connector.get_post_analytics('2026-01-01', '2026-01-07', platform='linkedin')

    def test_publish_review_gate_async_and_comment_markers(self):
        calls = []
        def transport(method, url, headers, body):
            calls.append(body)
            return {'id': 8, 'status': 'draft', 'publish_state': 'in_progress'}
        connector = TypefullyConnector(7, 'fictional-key', transport)
        with self.assertRaises(CapabilityError):
            connector.publish_draft('8')
        result = connector.publish_draft('8', approved=True)
        self.assertEqual(result['publish_state'], 'in_progress')
        self.assertEqual(calls, [{'publish_at': 'now'}])
        with self.assertRaises(ValueError):
            connector.schedule_draft('8', '2020-01-01T00:00:00+00:00', approved=True)
        connector._account = {'platforms': {'x': {'username': 'demo'}}}
        connector.transport = lambda *args: {'status': 'draft', 'platforms': {'x': {'posts': [{'text': '<typ:comment-thread id="1">text</typ:comment-thread>'}]}}}
        with self.assertRaisesRegex(CapabilityError, 'comment anchors'):
            connector.update_draft('8', Draft('post_012345abcdef', 'x', 'changed'))


class PublishingTests(WorkspaceFixture, unittest.TestCase):
    # Reuse the vertical-slice fixture, not its tests.
    def connector(self, body, published=False, error=False):
        calls = []
        def transport(method, url, headers, payload):
            calls.append((method, url, payload))
            if url.endswith('/7/'):
                return {'platforms': {'x': {'username': 'demo'}}}
            if method == 'POST':
                if error:
                    raise ValueError('Transport timed out')
                return {'id': 8, 'status': 'draft'}
            if method == 'PATCH':
                return {'id': 8, 'status': 'draft', 'publish_state': 'in_progress'}
            return {'id': 8, 'status': 'published' if published else 'draft',
                    'platforms': {'x': {'posts': [{'text': body}]}},
                    'x_published_url': 'https://x.com/demo/status/8', 'published_at': datetime.now(timezone.utc).isoformat()}
        return TypefullyConnector(7, 'fictional-key', transport), calls

    def test_local_gate_and_async_reconciliation(self):
        post = self.post()
        connector, calls = self.connector(post['body'])
        publishing = Publishing(self.engine, connector)
        with self.assertRaises(ValueError):
            publishing.deliver(post['id'], 'publish')
        self.assertEqual(calls, [])
        self.engine.transition(post['id'], 'APPROVED')
        result = publishing.deliver(post['id'], 'publish')
        self.assertEqual(result['status'], 'APPROVED')
        self.assertEqual(result['remote']['action_state'], 'pending')
        with self.assertRaises(ValueError):
            publishing.deliver(post['id'], 'publish')
        connector, _ = self.connector(post['body'], published=True)
        reconciled = Publishing(self.engine, connector).reconcile(post['id'])
        self.assertEqual(reconciled['status'], 'PUBLISHED')
        self.assertEqual(reconciled['published_urls'], ['https://x.com/demo/status/8'])

    def test_uncertain_creation_is_not_automatically_retried(self):
        post = self.post()
        connector, calls = self.connector(post['body'], error=True)
        publishing = Publishing(self.engine, connector)
        with self.assertRaises(ValueError):
            publishing.deliver(post['id'])
        with self.assertRaisesRegex(ValueError, 'reconciliation'):
            publishing.deliver(post['id'])
        self.assertEqual(sum(c[0] == 'POST' for c in calls), 1)

    def test_changed_remote_content_cannot_inherit_approval(self):
        post = self.post()
        self.engine.transition(post['id'], 'APPROVED')
        connector, calls = self.connector('Remote changed without local review')
        publishing = Publishing(self.engine, connector)
        with self.assertRaisesRegex(ValueError, 'changed'):
            publishing.deliver(post['id'], 'publish')
        self.assertEqual(sum(c[0] == 'PATCH' for c in calls), 0)

    def test_missing_credentials_preserve_local_draft(self):
        post = self.post()
        with self.assertRaises(CapabilityError):
            Publishing(self.engine, TypefullyConnector(7, api_key='')).deliver(post['id'])
        self.assertEqual(self.engine.store.get('content', post['id'])['remote'], {})

    def test_sync_documented_metrics_even_when_follower_service_is_unavailable(self):
        post = self.publish(self.post())
        def transport(method, url, headers, body):
            if '/followers?' in url:
                raise ValueError('Follower API temporarily unavailable')
            return {'results': [{'post_id': '8', 'draft_id': 8,
                                 'url': post['published_urls'][0],
                                 'metrics': {'impressions': 1200, 'engagement': {'total': 80, 'saves': 6}}}],
                    'next': None}
        connector = TypefullyConnector(7, 'fictional-key', transport)
        result = Publishing(self.engine, connector).sync_analytics('2026-09-01', '2026-09-29')
        self.assertEqual(result['imported'], 1)
        self.assertFalse(result['followers_saved'])
        self.assertIn('unavailable', result['follower_error'])
        metric = self.engine.store.list('analytics')[0]
        self.assertEqual(metric['metrics']['bookmarks'], 6)
        self.assertIsNone(metric['metrics']['new_followers'])
        self.assertTrue(list((self.engine.store.data / 'analytics/raw').glob('posts_*.json')))
