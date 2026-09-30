"""Explicit creator direction, scoped and inspectable; never inferred from approval."""
import hashlib

from .store import record


CATEGORIES = ('voice', 'evidence', 'structure', 'angle', 'cta', 'other')
SCOPES = ('content', 'platform', 'creator')


class Feedback:
    def __init__(self, store):
        self.store = store

    def add(self, content_id, note, author, scope='content', category='other', excerpt=None, replacement=None):
        with self.store.lock():
            content = self.store.get('content', content_id)
            if scope not in SCOPES or category not in CATEGORIES:
                raise ValueError('Unknown feedback scope/category.')
            if not note.strip() or not author.strip():
                raise ValueError('Feedback needs the creator direction and a declared author.')
            if excerpt is not None and (not excerpt.strip() or excerpt not in content['body']):
                raise ValueError('Feedback excerpt must match the current content exactly.')
            if replacement is not None and excerpt is None:
                raise ValueError('A replacement example needs an exact excerpt.')
            value = {**record('fb'), 'content_id': content_id,
                'content_revision': content['revision'],
                'content_sha256': hashlib.sha256(content['body'].encode()).hexdigest(),
                'content_snapshot': content['body'], 'platform': content['platform'],
                'note': note.strip(), 'author': author.strip(), 'scope': scope,
                'category': category, 'excerpt': excerpt, 'replacement': replacement,
                'status': 'ACTIVE', 'retirement_reason': None}
            # A retried command should not accumulate the same rule or change its priority.
            keys = ('content_id', 'content_revision', 'content_sha256', 'platform', 'note',
                    'author', 'scope', 'category', 'excerpt', 'replacement', 'status')
            duplicate = next((f for f in self.store.list('feedback') if all(f[k] == value[k] for k in keys)), None)
            return duplicate or self.store.put('feedback', value)

    def list(self, content_id=None, scope=None, status=None):
        return [item for item in self.store.list('feedback')
                if (content_id is None or item['content_id'] == content_id)
                and (scope is None or item['scope'] == scope)
                and (status is None or item['status'] == status)]

    def retire(self, identifier, reason):
        if not reason.strip():
            raise ValueError('Explain why this feedback no longer applies.')
        with self.store.lock():
            item = self.store.get('feedback', identifier)
            if item['status'] == 'RETIRED':
                return item
            item.update(status='RETIRED', retirement_reason=reason.strip())
            return self.store.put('feedback', item)

    def context(self, platform, content_id=None):
        import json
        from .retrieval import bounded_integer
        budget = self.store.config.get('feedback', {}).get('max_context_chars', 8000)
        bounded_integer(budget, 'feedback.max_context_chars', 256, 200000)
        selected = []
        for item in self.list(status='ACTIVE'):
            if item['scope'] == 'creator' or (item['scope'] == 'platform' and item['platform'] == platform) or (
                    item['scope'] == 'content' and item['content_id'] == content_id):
                selected.append({key: item[key] for key in ('id', 'scope', 'category', 'note', 'excerpt',
                    'replacement', 'author', 'content_id', 'content_revision', 'created_at')})
        if len(json.dumps(selected, ensure_ascii=False)) > budget:
            raise ValueError('Active creator feedback exceeds feedback.max_context_chars. Retire superseded rules, narrow their scope, or explicitly increase the budget; feedback was not silently dropped.')
        return selected
