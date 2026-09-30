"""Manual delivery adapter. Exporting is never a claim of scheduling or publication."""
import json
from pathlib import Path
from ..store import atomic_json, atomic_text, record
from .base import CapabilityError


class FilesystemConnector:
    def __init__(self, directory):
        self.root = Path(directory)
        self.root.mkdir(parents=True, exist_ok=True)

    def list_accounts(self):
        return [{'id': 'manual', 'name': 'Manual file export'}]

    def list_drafts(self):
        return [json.loads(p.read_text()) for p in self.root.glob('export_*.json')]

    def create_draft(self, draft):
        item = {**record('export'), 'content_id': draft.content_id, 'platform': draft.platform,
                'body': draft.body, 'title': draft.title, 'status': 'exported_for_manual_delivery'}
        atomic_json(self.root / (item['id'] + '.json'), item)
        atomic_text(self.root / (item['id'] + '.md'), draft.body + '\n')
        return item

    def update_draft(self, draft_id, draft):
        items = {item['id']: item for item in self.list_drafts()}
        if draft_id not in items:
            raise ValueError('Unknown manual export ID.')
        item = items[draft_id]
        item.update({'body': draft.body, 'title': draft.title})
        atomic_json(self.root / (draft_id + '.json'), item)
        atomic_text(self.root / (draft_id + '.md'), draft.body + '\n')
        return item

    def schedule_draft(self, draft_id, when, approved=False):
        raise CapabilityError('Filesystem delivery has no scheduler. Schedule manually and record the result.')

    def publish_draft(self, draft_id, approved=False):
        raise CapabilityError('Filesystem delivery cannot publish. Publish manually and record the real URL.')

    def get_post_analytics(self, start_date, end_date, platform='x'):
        raise CapabilityError('Import a CSV or manually enter observed metrics.')

    def get_follower_analytics(self, start_date, end_date, platform='x'):
        raise CapabilityError('No account connection in filesystem mode.')
