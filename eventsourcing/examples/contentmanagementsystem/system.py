from __future__ import annotations

from eventsourcing.examples.contentmanagement.application import (
    ContentManagementApplication,
)
from eventsourcing.examples.contentmanagementsystem.application import (
    SearchIndexApplication,
)
from eventsourcing.system import System


class ContentManagementSystem(System):
    def __init__(self) -> None:
        super().__init__(pipes=[[ContentManagementApplication, SearchIndexApplication]])
