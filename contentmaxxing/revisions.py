"""Inspectable before/after history and optimistic concurrency for local drafts."""
import hashlib
import json

from .store import record


def fingerprint(item):
    return hashlib.sha256(json.dumps({k: v for k, v in item.items() if k != 'updated_at'},
                                    sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def editable(item):
    if item['status'] not in ('NEEDS_REVIEW', 'APPROVED') or item['remote']:
        raise ValueError('Revision requires a local unscheduled draft without a remote copy. Published or remote work needs its existing reconciliation/new-version flow.')


def same_revision(left, right):
    # Review/publication can legitimately follow the content write before a
    # crashed task is reconciled. Compare the actual editorial revision.
    return all(left.get(key) == right.get(key) for key in
               ('id', 'revision', 'body', 'title', 'claims', 'source_reference', 'quality_notes',
                'generation_mode', 'framework', 'platform', 'format', 'primary_job', 'topic'))


class Revisions:
    def __init__(self, store):
        self.store = store

    def identifier(self, task_id):
        return 'rev_' + hashlib.sha256(task_id.encode()).hexdigest()[:12]

    def prepared(self, task):
        identifier = self.identifier(task['id'])
        if self.store.path('revisions', identifier).exists():
            return self.store.get('revisions', identifier)
        return None

    def applied(self, change, current):
        if change['status'] == 'APPLIED' or same_revision(current, change['after']):
            return True
        # A later journal's before-snapshot proves the earlier revision existed,
        # even when its process died just before recording APPLIED.
        return any(other['content_id'] == change['content_id'] and
                   same_revision(other['before'], change['after']) for other in self.store.list('revisions')
                   if other['id'] != change['id'])

    def commit(self, change):
        current = self.store.get('content', change['content_id'])
        if change['status'] == 'ABANDONED':
            raise ValueError('This revision was abandoned; start a new revision from the current draft.')
        if not self.applied(change, current):
            if fingerprint(current) != fingerprint(change['before']):
                raise ValueError('Draft changed while the revision was pending. Preserve the newer work; cancel this revision task and start from the current draft.')
            editable(current)
            # A prepared candidate can outlive the original process. Recheck its
            # immutable evidence before the first actual content write.
            self.store.validate('content-item', change['after'])
            references = change['after']['source_reference'] + [c['source_reference'] for c in change['after']['claims']]
            for reference in references:
                self.store.validate_reference(reference)
            current = self.store.put('content', change['after'])
        else:
            self.store.put('content', current)  # Restore sidecar after an interrupted content write.
        change['status'] = 'APPLIED'
        self.store.put('revisions', change)
        return current

    def prepare(self, before, after, kind, task_id=None):
        change = {**record('rev'), 'content_id': before['id'], 'kind': kind, 'task_id': task_id,
                  'status': 'PREPARED', 'before': before, 'after': after, 'reason': None}
        if task_id:
            change['id'] = self.identifier(task_id)
        self.store.validate('content-item', after)
        current = self.store.get('content', before['id'])
        if fingerprint(current) != fingerprint(before):
            raise ValueError('Draft changed while the revision was pending. Cancel this revision task and start from the current draft.')
        editable(current)
        return self.store.put('revisions', change)

    def apply_task(self, task, candidate=None):
        change = self.prepared(task)
        if change is None:
            before = task['inputs']['revision_target']
            after = {**candidate, 'id': before['id'], 'created_at': before['created_at'],
                     'revision': before['revision'] + 1}
            change = self.prepare(before, after, 'agent', task['id'])
        item = self.commit(change)
        idea = self.store.get('ideas', item['idea_id'])
        idea['status'] = item['status']
        self.store.put('ideas', idea)
        task.update(status='COMPLETED', result_ids=[item['id']], revision_id=change['id'], error=None)
        self.store.put('tasks', task)
        return [item]

    def manual(self, before, after):
        return self.commit(self.prepare(before, after, 'manual'))

    def cancel(self, task_id, reason):
        with self.store.lock():
            task = self.store.get('tasks', task_id)
            if not task['inputs'].get('revision_target') or task['status'] == 'COMPLETED':
                raise ValueError('Only a pending revision task can be cancelled here.')
            if not reason.strip():
                raise ValueError('Supply a reason for cancelling this revision.')
            if task['status'] == 'CANCELLED':
                return task
            change = self.prepared(task)
            if change:
                if self.applied(change, self.store.get('content', change['content_id'])):
                    self.apply_task(task)  # Work already committed; reconcile instead of calling it cancelled.
                    return self.store.get('tasks', task_id)
                change.update(status='ABANDONED', reason=reason.strip())
                self.store.put('revisions', change)
            task.update(status='CANCELLED', error=None, cancellation_reason=reason.strip())
            return self.store.put('tasks', task)

    def history(self, content_id):
        self.store.get('content', content_id)
        return [c for c in self.store.list('revisions') if c['content_id'] == content_id]
