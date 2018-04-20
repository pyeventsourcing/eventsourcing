from collections import OrderedDict


class System(object):
    def __init__(self, *pipelines):
        """
        Initialises a "process network" system object.

        :param pipelines: Pipelines of process classes.

        Each pipeline of process classes shows directly which process
        follows which other process in the system.

        For example, the pipeline (A | B | C) shows that B follows A,
        and C follows B.

        The pipeline (A | A) shows that A follows A.

        The pipeline (A | B | A) shows that B follows A, and A follows B.

        The pipelines ((A | B | A), (A | C | A)) is equivalent to (A | B | A | C | A).
        """
        self.pipelines = pipelines
        self.process_classes = set([c for l in self.pipelines for c in l])
        self.processes_by_name = None
        self.is_session_shared = True

        # Determine which process follows which.
        self.followings = OrderedDict()
        for pipeline in self.pipelines:
            previous_class = None
            for process_class in pipeline:
                # Follower follows the followed.
                try:
                    follows = self.followings[process_class]
                except KeyError:
                    follows = []
                    self.followings[process_class] = follows

                if previous_class is not None and previous_class not in follows:
                    follows.append(previous_class)

                previous_class = process_class

    # Todo: Extract function to new 'SinglethreadRunner' class or something (like the 'Multiprocess' class)?
    def setup(self):
        assert self.processes_by_name is None, "Already running"
        self.processes_by_name = {}

        # Construct the processes.
        session = None
        for process_class in self.process_classes:
            process = process_class(session=session, setup_tables=bool(session is None))
            self.processes_by_name[process.name] = process
            if self.is_session_shared:
                if session is None:
                    session = process.session

        # Configure which process follows which.
        for follower_class, follows in self.followings.items():
            follower = self.processes_by_name[follower_class.__name__.lower()]
            for followed_class in follows:
                followed = self.processes_by_name[followed_class.__name__.lower()]
                follower.follow(followed.name, followed.notification_log)

    def __getattr__(self, process_name):
        assert self.processes_by_name is not None, "Not running"
        return self.processes_by_name[process_name]

    def close(self):
        assert self.processes_by_name is not None, "Not running"
        for process in self.processes_by_name.values():
            process.close()
        self.processes_by_name = None

    def __enter__(self):
        self.setup()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
