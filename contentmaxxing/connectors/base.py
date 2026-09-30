from dataclasses import dataclass
from typing import Any, Dict, List, Protocol, runtime_checkable


class CapabilityError(ValueError):
    pass


@dataclass(frozen=True)
class Draft:
    content_id: str
    platform: str
    body: str
    title: str = ''
    approved: bool = False


@runtime_checkable
class PublishingConnector(Protocol):
    def list_accounts(self) -> List[Dict[str, Any]]: ...
    def list_drafts(self) -> List[Dict[str, Any]]: ...
    def create_draft(self, draft: Draft) -> Dict[str, Any]: ...
    def update_draft(self, draft_id: str, draft: Draft) -> Dict[str, Any]: ...
    def schedule_draft(self, draft_id: str, when: str, approved: bool = False) -> Dict[str, Any]: ...
    def publish_draft(self, draft_id: str, approved: bool = False) -> Dict[str, Any]: ...
    def get_post_analytics(self, start_date: str, end_date: str, platform: str = 'x') -> List[Dict[str, Any]]: ...
    def get_follower_analytics(self, start_date: str, end_date: str, platform: str = 'x') -> Dict[str, Any]: ...
