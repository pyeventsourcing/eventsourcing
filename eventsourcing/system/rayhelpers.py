import traceback
from datetime import datetime
from threading import Event, Lock

from eventsourcing.application.notificationlog import AbstractNotificationLog
from eventsourcing.application.process import Prompt


class RayDbJob(object):
    def __init__(self, method, args, kwargs):
        self.method = method
        self.args = args
        self.kwargs = kwargs
        self.is_done = Event()
        self.is_cancelled = Event()
        self.constructed = datetime.now()
        self.completed = None
        self.error = None
        self.time_lock = Lock()

    def __repr__(self):
        return "RayDbJob(method=%s)" % self.method

    def execute(self):
        self.started = datetime.now()
        try:
            self.result = self.method(*self.args, **self.kwargs)
        except Exception as e:
            self.error = e
            print(traceback.format_exc())
            print("Error in db thread:", e)
        finally:
            self.completed = datetime.now()
            self.is_done.set()

    def wait(self, timeout=None):
        return self.is_done.wait(timeout=timeout)

    @property
    def delay(self):
        if self.constructed and self.started:
            return self.started - self.constructed

    @property
    def duration(self):
        if self.completed and self.started:
            return self.completed - self.started


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
    def __init__(self, process_name: str, pipeline_id: int, head_notification_id=None):
        self.process_name: str = process_name
        self.pipeline_id: int = pipeline_id
        self.head_notification_id = head_notification_id

    def __repr__(self) -> str:
        return "{}({}={}, {}={}, {}={})".format(
            type(self).__name__,
            "process_name",
            self.process_name,
            "pipeline_id",
            self.pipeline_id,
            "head_notification_id",
            self.head_notification_id,
        )



class ProcessHasStopped(Exception): pass
