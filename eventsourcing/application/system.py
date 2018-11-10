from collections import OrderedDict
from queue import Queue, Empty
from threading import Lock

from eventsourcing.application.process import Prompt
from eventsourcing.domain.model.events import subscribe, unsubscribe


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
        # A following is a list of process classes followed by a process class.
        self.followings = OrderedDict()
        self.followers = OrderedDict()
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
        self.run_with_iteration_lock = Lock()

    # Todo: Extract function to new 'SinglethreadRunner' class or something (like the 'Multiprocess' class)?
    def setup(self):
        assert self.processes is None, "Already running"
        self.processes = {}

        # Construct the processes.
        for process_class in self.process_classes.values():

            process = self.construct_app(process_class)
            self.processes[process.name] = process

        # Do something to make sure followers' run() method is
        # called when a process application publishes a prompt.
        subscribe(
            predicate=self.is_prompt,
            handler=self.run_followers,
        )

        # Configure which process follows which.
        for followed_name, followers in self.followers.items():
            followed = self.processes[followed_name]
            followed_log = followed.notification_log
            for follower_name in followers:
                follower = self.processes[follower_name]
                follower.follow(followed_name, followed_log)

        # Todo: See if can factor this out, it's confusing.
        for follower_name, follows in self.followings.items():
            follower = self.processes[follower_name]
            for followed_name in follows:
                followed = self.processes[followed_name]
                follower.follow(followed.name, followed.notification_log)

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

    def close(self):
        assert self.processes is not None, "Not running"
        for process in self.processes.values():
            process.close()
        unsubscribe(
            predicate=self.is_prompt,
            handler=self.run_followers,
        )
        self.processes = None

    def is_prompt(self, event):
        return isinstance(event, Prompt)

    def run_followers(self, prompt):
        assert isinstance(prompt, Prompt)
        # self.run_followers_with_recursion(prompt)
        self.run_followers_with_iteration(prompt)

    def run_followers_with_recursion(self, prompt):
        followers = self.followers[prompt.process_name]
        for follower_name in followers:
            follower = self.processes[follower_name]
            follower.run(prompt)

    def run_followers_with_iteration(self, prompt):
        # Put the prompt on the queue.
        self.pending_prompts.put(prompt)

        if self.run_with_iteration_lock.acquire(timeout=0):
            try:
                while True:
                    try:
                        prompt = self.pending_prompts.get(timeout=0)
                    except Empty:
                        break
                    else:
                        followers = self.followers[prompt.process_name]
                        for follower_name in followers:
                            follower = self.processes[follower_name]
                            follower.run(prompt)
            finally:
                self.run_with_iteration_lock.release()

    def __enter__(self):
        self.setup()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def drop_tables(self):
        for process_class in self.process_classes.values():
            with self.construct_app(process_class, setup_table=False) as process:
                process.drop_table()
