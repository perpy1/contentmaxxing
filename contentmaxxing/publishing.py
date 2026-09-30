"""Review gates and reconciliation around an optional remote publishing adapter."""
import json
from pathlib import Path

from .analytics import timestamp
from .connectors.base import Draft
from .connectors.typefully import normalize_post
from .engine import mutation
from .store import atomic_json, now


class Publishing:
    def __init__(self, engine, connector):
        self.engine, self.connector, self.store = engine, connector, engine.store

    @mutation
    def deliver(self, content_id, action='draft', when=None):
        content = self.store.get('content', content_id)
        if content['status'] not in ('NEEDS_REVIEW', 'APPROVED'):
            raise ValueError('Only unscheduled local drafts can be delivered.')
        if action not in ('draft', 'schedule', 'publish'):
            raise ValueError('Unknown delivery action.')
        approved = content['status'] == 'APPROVED' and bool(content['approved_at'])
        if action != 'draft' and not approved:
            raise ValueError('Review and approve the content before scheduling or publishing.')
        if action == 'schedule' and not when:
            raise ValueError('Provide --at with a future offset timestamp or next-free-slot.')
        remote = content['remote']
        if remote.get('social_set_id') and str(remote['social_set_id']) != self.connector.social_set_id:
            raise ValueError('Remote draft belongs to a different Typefully social set.')
        if content['format'] in ('QRT + original insight', 'QRT + personal story', 'expanded QRT',
                                  'rough document screenshot', 'proof screenshot', 'visual breakdown'):
            raise ValueError('This format needs quote-post/media attachments. Use manual export; media upload is deferred in v1.')
        if remote.get('action_state') in ('uncertain', 'requested', 'pending'):
            raise ValueError('Prior remote action needs reconciliation. Do not resend it.')
        if 'id' not in remote:
            # Missing credentials/platform support are known before any mutation.
            # They must not strand the content in an uncertain remote state.
            self.connector.payload(Draft(content_id, content['platform'], content['body'], content['title'], approved))
            content['remote'] = {'connector': 'typefully', 'action': 'create', 'action_state': 'requested',
                                 'social_set_id': self.connector.social_set_id}
            self.store.put('content', content)
            try:
                response = self.connector.create_draft(Draft(content_id, content['platform'], content['body'], content['title'], approved))
            except Exception:
                content['remote']['action_state'] = 'uncertain'
                self.store.put('content', content)
                raise
            if 'id' not in response:
                content['remote']['action_state'] = 'uncertain'
                self.store.put('content', content)
                raise ValueError('No remote ID returned. Reconcile in Typefully before any retry.')
            content['remote'].update({'id': str(response['id']), 'action_state': 'confirmed', 'revision': content['revision']})
            self.store.put('content', content)
        if action == 'draft':
            return content
        if content['remote'].get('revision') != content['revision']:
            raise ValueError('Remote revision differs from approved local content.')
        # Check remote body before the irreversible commitment: remote edits must be reviewed locally.
        remote_content = self.connector.get_draft(content['remote']['id'])
        if not self.matches(content, remote_content):
            raise ValueError('Remote content changed or has comment markers. Review and reconcile it before publishing.')
        content['remote'].update({'action': action, 'action_state': 'requested'})
        self.store.put('content', content)
        try:
            response = (self.connector.schedule_draft(content['remote']['id'], when, approved=True)
                        if action == 'schedule' else self.connector.publish_draft(content['remote']['id'], approved=True))
        except Exception:
            content['remote']['action_state'] = 'uncertain'
            self.store.put('content', content)
            raise
        content['remote']['action_state'] = 'pending'
        self.store.put('content', content)
        return self.apply_remote(content, response)

    def matches(self, content, response):
        platform = {'substack_note': 'substack'}.get(content['platform'], content['platform'])
        value = response.get('platforms', {}).get(platform, {})
        if platform == 'x_article':
            expected = content['body'] if content['body'].lstrip().startswith('# ') else '# ' + (content['title'] or 'Working notes') + '\n\n' + content['body']
            # Typefully canonicalizes Markdown. Ambiguous differences require manual review.
            return (value.get('content_markdown') or '').strip() == expected.strip()
        return [p.get('text') for p in value.get('posts', [])] == [content['body']]

    def apply_remote(self, content, response):
        content['remote'].update({'status': response.get('status'), 'publish_state': response.get('publish_state'),
                                  'checked_at': now()})
        self.store.put('content', content)
        if response.get('status') == 'published':
            platform = {'substack_note': 'substack'}.get(content['platform'], content['platform'])
            url = response.get(platform + '_published_url')
            if not url:
                raise ValueError('Remote says published but URL is missing; local status preserved for reconciliation.')
            if content['status'] in ('APPROVED', 'SCHEDULED'):
                content = self.engine.transition(content['id'], 'PUBLISHED', url=url,
                    published_at=response.get(platform + '_post_published_at') or response.get('published_at') or now())
            content['remote']['action_state'] = 'confirmed'
        elif response.get('status') == 'scheduled' and response.get('scheduled_date'):
            if content['status'] == 'APPROVED':
                content = self.engine.transition(content['id'], 'SCHEDULED', scheduled_at=response['scheduled_date'])
            content['remote']['action_state'] = 'confirmed'
        elif response.get('publish_state') == 'in_progress' or response.get('status') == 'publishing':
            content['remote']['action_state'] = 'pending'
        elif response.get('status') in ('draft', 'planned', 'error'):
            content['remote']['action_state'] = 'confirmed'
            if content['status'] == 'SCHEDULED':
                # A remote cancellation/failure disarms the local schedule and invalidates approval.
                content.update({'status': 'NEEDS_REVIEW', 'approved_at': None, 'scheduled_at': None})
                content['quality_notes'].append('Remote schedule no longer active; review before rescheduling.')
        self.store.put('content', content)
        return content

    @mutation
    def reconcile(self, content_id, remote_id=None):
        content = self.store.get('content', content_id)
        identifier = remote_id or content['remote'].get('id')
        if not identifier:
            raise ValueError('Provide a verified --remote-id from Typefully to resolve an uncertain creation.')
        response = self.connector.get_draft(identifier)
        if not self.matches(content, response):
            raise ValueError('Remote body differs. Export/read and review that version; it cannot inherit this local approval.')
        content['remote'].update({'id': str(identifier), 'connector': 'typefully',
                                  'social_set_id': self.connector.social_set_id, 'revision': content['revision']})
        return self.apply_remote(content, response)

    @mutation
    def sync_analytics(self, start_date, end_date):
        posts = self.connector.get_post_analytics(start_date, end_date)
        follower_error = None
        try:
            followers = self.connector.get_follower_analytics(start_date, end_date)
        except ValueError as exc:
            followers, follower_error = None, str(exc)
        raw_dir = self.store.data / 'analytics/raw'
        stamp = now().replace(':', '-')
        atomic_json(raw_dir / ('posts_' + stamp + '.json'), {'social_set_id': self.connector.social_set_id, 'posts': posts})
        if followers is not None:
            atomic_json(raw_dir / ('followers_' + stamp + '.json'), followers)
        contents = self.store.list('content')
        by_remote = {str(c['remote']['id']): c for c in contents if c['remote'].get('id') and
                     str(c['remote'].get('social_set_id')) == self.connector.social_set_id}
        by_url = {url: c for c in contents for url in c['published_urls']}
        measurements, unmatched = [], []
        observed = now()
        for post in posts:
            content = by_remote.get(str(post.get('draft_id'))) or by_url.get(post.get('url'))
            if content is None or content['platform'] != 'x' or not content['published_at']:
                unmatched.append(post.get('post_id'))
                continue
            item = self.engine.prepare_measurement(content['id'], normalize_post(post), observed, 'typefully')
            measurements.append(self.engine.persist_measurement(item))
        return {'imported': len(measurements), 'unmatched_post_ids': unmatched,
                'followers_saved': followers is not None, 'follower_error': follower_error,
                'raw_directory': str(raw_dir)}
