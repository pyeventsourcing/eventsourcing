from collections import OrderedDict


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
                if process_class.__name__ not in self.process_classes:
                    self.process_classes[process_class.__name__] = process_class

        self.processes = None
        self.is_session_shared = True

        # Determine which process follows which.
        # A following is a list of process classes followed by a process class.
        self.followings = OrderedDict()
        for pipeline_expr in self.pipelines_exprs:
            previous_class = None
            for process_class in pipeline_expr:
                try:
                    follows = self.followings[process_class.__name__]
                except KeyError:
                    follows = []
                    self.followings[process_class.__name__] = follows

                if previous_class is not None and previous_class not in follows:
                    follows.append(previous_class.__name__)

                previous_class = process_class

    # Todo: Extract function to new 'SinglethreadRunner' class or something (like the 'Multiprocess' class)?
    def setup(self):
        assert self.processes is None, "Already running"
        self.processes = {}

        # Construct the processes.
        for process_class in self.process_classes.values():

            process = self.construct_app(process_class)
            self.processes[process.name] = process

        # Configure which process follows which.
        for follower_class_name, follows in self.followings.items():
            follower = self.processes[follower_class_name.lower()]
            for followed_class_name in follows:
                followed = self.processes[followed_class_name.lower()]
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
        self.processes = None

    def __enter__(self):
        self.setup()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def drop_tables(self):
        for process_class in self.process_classes.values():
            with self.construct_app(process_class, setup_table=False) as process:
                process.drop_table()
