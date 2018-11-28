import time
from abc import ABCMeta, abstractmethod
from collections import OrderedDict
from threading import Lock, Thread, Event, Timer

import six
from six import with_metaclass
from six.moves.queue import Empty, Queue

from eventsourcing.application.process import Prompt
from eventsourcing.domain.model.decorators import retry
from eventsourcing.domain.model.events import subscribe, unsubscribe
from eventsourcing.exceptions import CausalDependencyFailed

DEFAULT_POLL_INTERVAL = 5


class System(object):
    def __init__(self, *pipeline_exprs, **kwargs):
        """
        Initialises a "process network" system object.

        :param pipeline_exprs: Pipeline expressions involving process application classes.

        Each pipeline expression of process classes shows directly which process
        follows which other process in the system.

        For example, the pipeline expression (A | B | C) shows that B follows A,
        and C follows B.

        The pipeline expression (A | A) shows that A follows A.

        The pipeline expression (A | B | A) shows that B follows A, and A follows B.

        The pipeline expressions ((A | B | A), (A | C | A)) are equivalent to (A | B | A | C | A).
        """
        self.pipelines_exprs = pipeline_exprs
        self.setup_tables = kwargs.get('setup_tables', False)
        self.infrastructure_class = kwargs.get('infrastructure_class', None)

        self.session = kwargs.get('session', None)

        self.process_classes = OrderedDict()
        for pipeline_expr in self.pipelines_exprs:
            for process_class in pipeline_expr:
                process_name = process_class.__name__.lower()
                if process_name not in self.process_classes:
                    self.process_classes[process_name] = process_class

        self.processes = None
        self.is_session_shared = True

        # Determine which process follows which.
        self.followers = OrderedDict()
        # A following is a list of process classes followed by a process class.
        # Todo: Factor this out, it's confusing. (Only used in ActorsRunner now).
        self.followings = OrderedDict()
        for pipeline_expr in self.pipelines_exprs:
            previous_name = None
            for process_class in pipeline_expr:
                process_name = process_class.__name__.lower()
                try:
                    follows = self.followings[process_name]
                except KeyError:
                    follows = []
                    self.followings[process_name] = follows

                try:
                    self.followers[process_name]
                except KeyError:
                    self.followers[process_name] = []

                if previous_name and previous_name not in follows:
                    follows.append(previous_name)
                    followers = self.followers[previous_name]
                    followers.append(process_name)

                previous_name = process_name
        self.pending_prompts = Queue()
        self.iteration_lock = Lock()

    def construct_app(self, process_class, **kwargs):
        kwargs = dict(kwargs)
        if 'setup_table' not in kwargs:
            kwargs['setup_table'] = self.setup_tables
        if 'session' not in kwargs and process_class.is_constructed_with_session:
            kwargs['session'] = self.session

        if self.infrastructure_class:
            process_class = process_class.mixin(self.infrastructure_class)

        process = process_class(**kwargs)

        if process_class.is_constructed_with_session and self.is_session_shared:
            if self.session is None:
                self.session = process.session

        return process

    def is_prompt(self, event):
        return isinstance(event, Prompt)

    def run_followers(self, prompt):
        """
        First caller adds a prompt to queue and
        runs followers until there are no more
        pending prompts.

        Subsequent callers just add a prompt
        to the queue, avoiding recursion.
        """
        assert isinstance(prompt, Prompt)
        # Put the prompt on the queue.
        self.pending_prompts.put(prompt)

        if self.iteration_lock.acquire(False):
            try:
                while True:
                    try:
                        prompt = self.pending_prompts.get(False)
                    except Empty:
                        break
                    else:
                        followers = self.followers[prompt.process_name]
                        for follower_name in followers:
                            follower = self.processes[follower_name]
                            follower.run(prompt)
                        self.pending_prompts.task_done()
            finally:
                self.iteration_lock.release()

    # This is the old way of doing it, with recursion.
    # def run_followers_with_recursion(self, prompt):
    #     followers = self.followers[prompt.process_name]
    #     for follower_name in followers:
    #         follower = self.processes[follower_name]
    #         follower.run(prompt)
    #

    def __enter__(self):
        self.__runner = SingleThreadRunner(self)
        self.__runner.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.__runner.__exit__(exc_type, exc_val, exc_tb)
        del(self.__runner)

    def drop_tables(self):
        for process_class in self.process_classes.values():
            with self.construct_app(process_class, setup_table=False) as process:
                process.drop_table()


class SystemRunner(with_metaclass(ABCMeta)):

    def __init__(self, system: System):
        self.system = system

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def close(self):
        pass


class InProcessRunner(SystemRunner):
    """
    Runs a system in the current process,
    either in the current thread, or with
    a thread for each process in the system.
    """

    def start(self):
        assert self.system.processes is None, "Already running"
        self.system.processes = {}

        # Construct the processes.
        for process_class in self.system.process_classes.values():

            process = self.system.construct_app(process_class)
            self.system.processes[process.name] = process

        # Do something to make sure followers' run() method is
        # called when a process application publishes a prompt.
        subscribe(
            predicate=self.system.is_prompt,
            handler=self.handle_prompt,
        )

        # Configure which process follows which.
        for followed_name, followers in self.system.followers.items():
            followed = self.system.processes[followed_name]
            followed_log = followed.notification_log
            for follower_name in followers:
                follower = self.system.processes[follower_name]
                follower.follow(followed_name, followed_log)

    @abstractmethod
    def handle_prompt(self, prompt):
        pass

    def close(self):
        assert self.system.processes is not None, "Not running"
        for process in self.system.processes.values():
            process.close()
        unsubscribe(
            predicate=self.system.is_prompt,
            handler=self.handle_prompt,
        )
        self.processes = None


class SingleThreadRunner(InProcessRunner):
    """
    Runs a system in the current thread.
    """

    def handle_prompt(self, prompt):
        self.system.run_followers(prompt)


class MultiThreadedRunner(InProcessRunner):
    """
    Runs a system with a thread for each process.
    """
    def __init__(self, system: System, poll_interval=None, clock_speed=None):
        super(MultiThreadedRunner, self).__init__(system=system)
        self.poll_interval = poll_interval or DEFAULT_POLL_INTERVAL
        assert isinstance(system, System)
        self.threads = {}
        self.clock_speed = clock_speed
        self.stop_clock = Event()

    def start(self):
        super(MultiThreadedRunner, self).start()
        assert not self.threads, "Already started"

        self.inboxes = {}
        self.outboxes = {}

        # Setup queues.
        for process_name, upstream_names in self.system.followings.items():
            inbox_id = process_name.lower()
            if inbox_id not in self.inboxes:
                self.inboxes[inbox_id] = Queue()
            for upstream_class_name in upstream_names:
                outbox_id = upstream_class_name.lower()
                if outbox_id not in self.outboxes:
                    self.outboxes[outbox_id] = Outbox()
                if inbox_id not in self.outboxes[outbox_id].downstream_inboxes:
                    self.outboxes[outbox_id].downstream_inboxes[inbox_id] = self.inboxes[inbox_id]

        # Construct application threads.
        for process_name, process in self.system.processes.items():
            process_instance_id = process_name
            if self.clock_speed:
                clock_event = Event()
                process.clock_event = clock_event
            else:
                clock_event = None
            thread = ApplicationThread(
                process=process,
                poll_interval=self.poll_interval,
                inbox=self.inboxes[process_instance_id],
                outbox=self.outboxes[process_instance_id],
                clock_event=clock_event
            )
            self.threads[process_instance_id] = thread

        # Start application threads.
        for thread in self.threads.values():
            thread.start()

        # Start clock.
        self.start_clock()

    def start_clock(self):
        clock_events = [t.clock_event for t in self.threads.values()]
        if self.clock_speed:
            tick_interval = 1 / self.clock_speed
            self.last_tick = None

            def set_clock_events():
                this_tick = time.time()
                # if self.last_tick is not None:
                #     tick_size = (this_tick - self.last_tick)
                #     tick_error = tick_size - tick_interval
                #     tick_error_percentage = 100 * tick_error / tick_interval
                #     if tick_error_percentage > 0:
                #         print(
                #             f"Warning: tick error: {tick_size:.6f}s, {tick_error_percentage:.0f}%"
                #         )
                #     else:
                #         print(
                #             f"Warning: tick ok: {tick_size:.6f}s, {tick_interval:.6f}%"
                #         )
                self.last_tick = this_tick

                for clock_event in clock_events:
                    clock_event.set()
                if not self.stop_clock.is_set():
                    set_timer()

            def set_timer():
                if self.last_tick is not None:
                    interval_remaining = tick_interval - (time.time() - self.last_tick)
                    if interval_remaining < 0:
                        print(f"Warning: negative interval remaining: {interval_remaining}")
                        interval_remaining = tick_interval
                else:
                    interval_remaining = 0
                timer = Timer(interval_remaining, set_clock_events)
                timer.start()

            set_timer()

    def handle_prompt(self, prompt):
        self.broadcast_prompt(prompt)

    def broadcast_prompt(self, prompt):
        outbox_id = prompt.process_name
        assert outbox_id in self.outboxes, (outbox_id, self.outboxes.keys())
        self.outboxes[outbox_id].put(prompt)

    @staticmethod
    def is_prompt(event):
        return isinstance(event, Prompt)

    def close(self):
        super(MultiThreadedRunner, self).close()
        for thread in self.threads.values():
            thread.inbox.put('QUIT')

        for thread in self.threads.values():
            thread.join(timeout=10)

        self.threads.clear()

        self.stop_clock.set()



class ApplicationThread(Thread):

    def __init__(self, process, poll_interval=DEFAULT_POLL_INTERVAL,
                 inbox=None, outbox=None, clock_event=None, *args, **kwargs):
        super(ApplicationThread, self).__init__(*args, **kwargs)
        self.process = process
        self.poll_interval = poll_interval
        self.inbox = inbox
        self.outbox = outbox
        self.clock_event = clock_event

    def run(self):
        self.loop_on_prompts()

    @retry(CausalDependencyFailed, max_attempts=100, wait=0.1)
    def loop_on_prompts(self):

        # Loop on getting prompts.
        while True:
            try:
                # Todo: Make the poll interval gradually increase if there are only timeouts?
                prompt = self.inbox.get(timeout=self.poll_interval)
                self.inbox.task_done()

                if prompt == 'QUIT':
                    self.process.close()
                    break

                else:
                    if self.clock_event is not None:
                        self.clock_event.wait()
                        self.clock_event.clear()
                    started = time.time()
                    self.process.run(prompt)
                    if self.clock_event is not None:
                        ended = time.time()
                        duration = ended - started
                        if self.clock_event.is_set():
                            print(f"Warning: Process {self.process.name} overran clock cycle: {duration}")
                        else:
                            print(f"Info: Process {self.process.name} ran within clock cycle: {duration}")

            except six.moves.queue.Empty:
                # Basically, we're polling after a timeout.
                if self.clock_event is None:
                    self.process.run()


class Outbox(object):
    def __init__(self):
        self.downstream_inboxes = {}

    def put(self, msg):
        for q in self.downstream_inboxes.values():
            q.put(msg)
