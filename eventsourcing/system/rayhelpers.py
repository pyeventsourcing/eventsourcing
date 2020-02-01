from eventsourcing.application.notificationlog import AbstractNotificationLog
from eventsourcing.application.process import Prompt


class RayNotificationLog(AbstractNotificationLog):
    def __init__(self, upstream_process, section_size, ray_get):
        self._upstream_process = upstream_process
        self._section_size = section_size
        self._ray_get = ray_get

    def __getitem__(self, item):
        return self._ray_get(
            self._upstream_process.get_notification_log_section.remote(
                section_id=item
            )
        )

    @property
    def section_size(self) -> int:
        """
        Size of section of notification log.
        """
        return self._section_size


class RayPrompt(Prompt):
    def __init__(self, process_name: str, pipeline_id: int):
        self.process_name: str = process_name
        self.pipeline_id: int = pipeline_id

