"""Typefully public API v2. Verified against https://typefully.com/docs/api.

No mutation retries: a timeout can mean a draft was created or a publish was accepted.
"""
import os
import re
from datetime import datetime, timezone
from urllib.parse import urlencode

from ..analytics import timestamp
from ..providers import http_json
from .base import CapabilityError, Draft


class TypefullyConnector:
    def __init__(self, social_set_id=None, api_key=None, transport=http_json):
        self.social_set_id = str(social_set_id) if social_set_id is not None else None
        if self.social_set_id is not None and not self.social_set_id.isdigit():
            raise ValueError('Typefully social set ID must be an integer.')
        self.api_key = api_key if api_key is not None else os.environ.get('TYPEFULLY_API_KEY', '')
        self.transport = transport
        self._account = None

    def request(self, method, path, body=None, query=None):
        if not self.api_key:
            raise CapabilityError('TYPEFULLY_API_KEY is missing. Use contentmaxxing export for manual mode; no remote draft was created.')
        url = 'https://api.typefully.com/v2/' + path.lstrip('/')
        if query:
            url += '?' + urlencode(query)
        return self.transport(method, url, {'Authorization': 'Bearer ' + self.api_key,
                                           'Content-Type': 'application/json'}, body)

    def account_path(self):
        if self.social_set_id is None:
            raise CapabilityError('Set typefully_social_set_id in config.yaml. Use connect accounts to discover accounts.')
        return 'social-sets/' + self.social_set_id

    def paginate(self, path, query=None, limit=50):
        result, offset = [], 0
        while True:
            response = self.request('GET', path, query={**(query or {}), 'limit': limit, 'offset': offset})
            page = response.get('results')
            if not isinstance(page, list):
                raise ValueError('Invalid Typefully paginated response.')
            result.extend(page)
            if not response.get('next'):
                return result
            if not page or offset > 100000:
                raise ValueError('Typefully pagination did not advance.')
            offset += len(page)

    def list_accounts(self):
        return self.paginate('social-sets')

    def list_drafts(self):
        return self.paginate(self.account_path() + '/drafts')

    def get_draft(self, draft_id):
        return self.request('GET', self.draft_path(draft_id))

    def draft_path(self, draft_id):
        if not str(draft_id).isdigit():
            raise ValueError('Typefully draft ID must be an integer.')
        return self.account_path() + '/drafts/' + str(draft_id)

    def capabilities(self):
        if self._account is None:
            self._account = self.request('GET', self.account_path() + '/')
        return self._account.get('platforms', {})

    def payload(self, draft):
        platform = {'substack_note': 'substack'}.get(draft.platform, draft.platform)
        if platform not in ('x', 'linkedin', 'x_article', 'substack'):
            raise CapabilityError('Typefully adapter does not publish ' + draft.platform + '; use manual export.')
        account_platform = 'x' if platform == 'x_article' else platform
        if not self.capabilities().get(account_platform):
            raise CapabilityError('Platform not connected on this social set: ' + platform)
        if platform == 'x_article':
            body = draft.body if draft.body.lstrip().startswith('# ') else '# ' + (draft.title or 'Working notes') + '\n\n' + draft.body
            value = {'content_markdown': body}
        else:
            value = {'enabled': True, 'posts': [{'text': draft.body}]}
        # Each content record maps to one native platform. An article must be standalone.
        return {'platforms': {platform: value}, 'draft_title': draft.title[:512]}

    def create_draft(self, draft):
        return self.request('POST', self.account_path() + '/drafts', self.payload(draft))

    def update_draft(self, draft_id, draft):
        remote = self.get_draft(draft_id)
        if remote.get('status') in ('scheduled', 'publishing', 'published') or remote.get('publish_state') == 'in_progress':
            raise CapabilityError('Remote draft is active or published; do not overwrite it.')
        payload = self.payload(draft)
        old = remote.get('platforms', {}).get({'substack_note': 'substack'}.get(draft.platform, draft.platform), {})
        old_text = old.get('content_markdown', '') or '\n'.join(p.get('text', '') for p in old.get('posts', []))
        # Exact marker-preserving edits belong in Typefully. Never force-overwrite comments.
        if '<typ:comment-thread' in old_text:
            raise CapabilityError('Remote draft has comment anchors. Edit in Typefully preserving markers, then reconcile; adapter will not strip them.')
        return self.request('PATCH', self.draft_path(draft_id), payload)

    def schedule_draft(self, draft_id, when, approved=False):
        if not approved:
            raise CapabilityError('Explicit content approval required before scheduling.')
        if when != 'next-free-slot':
            if timestamp(when) <= datetime.now(timezone.utc):
                raise ValueError('Schedule must be in the future.')
        return self.request('PATCH', self.draft_path(draft_id), {'publish_at': when})

    def publish_draft(self, draft_id, approved=False):
        if not approved:
            raise CapabilityError('Explicit content approval required before publishing.')
        # Response may be draft + publish_state=in_progress, not published.
        return self.request('PATCH', self.draft_path(draft_id), {'publish_at': 'now'})

    def get_post_analytics(self, start_date, end_date, platform='x'):
        if platform != 'x':
            raise CapabilityError('Typefully API analytics currently supports X only.')
        return self.paginate(self.account_path() + '/analytics/x/posts',
                             {'start_date': start_date, 'end_date': end_date}, limit=100)

    def get_follower_analytics(self, start_date, end_date, platform='x'):
        if platform != 'x':
            raise CapabilityError('Typefully follower analytics currently supports X only.')
        return self.request('GET', self.account_path() + '/analytics/x/followers',
                            query={'start_date': start_date, 'end_date': end_date})

    def get_queue(self, start_date, end_date):
        return self.request('GET', self.account_path() + '/queue',
                            query={'start_date': start_date, 'end_date': end_date})


def normalize_post(post):
    metrics = post.get('metrics', {})
    engagement = metrics.get('engagement') or {}
    # Do not invent per-post follows: Typefully returns account follower totals separately.
    values = {'impressions': metrics.get('impressions'), 'engagements': engagement.get('total'),
              'likes': engagement.get('likes'), 'replies': engagement.get('comments'),
              'shares': engagement.get('shares'), 'bookmarks': engagement.get('saves'),
              'profile_visits': engagement.get('profile_clicks'), 'link_clicks': engagement.get('link_clicks')}
    return values
