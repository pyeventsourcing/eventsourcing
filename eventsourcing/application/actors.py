import logging

from thespian.actors import *

from eventsourcing.application.process import ProcessApplication, Prompt
from eventsourcing.application.system import System, SystemRunner
from eventsourcing.domain.model.events import subscribe, unsubscribe
from eventsourcing.exceptions import RecordConflictError
from eventsourcing.interface.notificationlog import RecordManagerNotificationLog

logger = logging.getLogger()

# Todo: Send timer message to run slave every so often (in master or slave?).


DEFAULT_ACTORS_LOGCFG = {
    'version': 1,
    'formatters': {
        'normal': {
            'format': '%(levelname)-8s %(message)s'
        }
    },
    'handlers': {
        # 'h': {
        #     'class': 'logging.FileHandler',
        #     'filename': 'hello.log',
        #     'formatter': 'normal',
        #     'level': logging.INFO
        # }
    },
    'loggers': {
        # '': {'handlers': ['h'], 'level': logging.DEBUG}
    }
}


def start_actor_system(system_base=None, logcfg=DEFAULT_ACTORS_LOGCFG):
    ActorSystem(
        systemBase=system_base,
        logDefs=logcfg,
    )


def shutdown_actor_system():
    ActorSystem().shutdown()


def start_multiproc_tcp_base_system():
    start_actor_system(system_base='multiprocTCPBase')


# def start_multiproc_udp_base_system():
#     start_actor_system(system_base='multiprocUDPBase')
#
#
# def start_multiproc_queue_base_system():
#     start_actor_system(system_base='multiprocQueueBase')


class ActorModelRunner(SystemRunner):
    """
    Uses actor model framework to run a system of process applications.
    """
    def __init__(self, system: System, pipeline_ids, system_actor_name='system', shutdown_on_close=False, **kwargs):
        super(ActorModelRunner, self).__init__(system=system, **kwargs)
        self.pipeline_ids = list(pipeline_ids)
        self.pipeline_actors = {}
        self.system_actor_name = system_actor_name
        # Create the system actor (singleton).
        self.system_actor = self.actor_system.createActor(
            actorClass=SystemActor,
            globalName=self.system_actor_name
        )
        self.shutdown_on_close = shutdown_on_close

    @property
    def actor_system(self):
        return ActorSystem()

    def start(self):
        """
        Starts all the actors to run a system of process applications.
        """
        # Subscribe to broadcast prompts published by a process
        # application in the parent operating system process.
        subscribe(handler=self.forward_prompt, predicate=self.is_prompt)

        # Initialise the system actor.
        msg = SystemInitRequest(
            self.system.process_classes,
            self.infrastructure_class,
            self.system.followings,
            self.pipeline_ids
        )
        response = self.actor_system.ask(self.system_actor, msg)

        # Keep the pipeline actor addresses, to send prompts directly.
        assert isinstance(response, SystemInitResponse), type(response)

        assert list(response.pipeline_actors.keys()) == self.pipeline_ids, (
            "Configured pipeline IDs mismatch initialised system {} {}").format(
            list(self.pipeline_actors.keys()), self.pipeline_ids
        )

        self.pipeline_actors = response.pipeline_actors

        # Todo: Somehow know when to get a new address from the system actor.
        # Todo: Command and response messages to system actor to get new pipeline address.

    @staticmethod
    def is_prompt(event):
        return isinstance(event, Prompt)

    def forward_prompt(self, prompt):
        if prompt.pipeline_id in self.pipeline_actors:
            pipeline_actor = self.pipeline_actors[prompt.pipeline_id]
            self.actor_system.tell(pipeline_actor, prompt)
        # else:
        #     msg = "Pipeline {} is not running.".format(prompt.pipeline_id)
        #     raise ValueError(msg)

    def close(self):
        """Stops all the actors running a system of process applications."""
        super(ActorModelRunner, self).close()
        unsubscribe(handler=self.forward_prompt, predicate=self.is_prompt)
        if self.shutdown_on_close:
            self.shutdown()

    def shutdown(self):
        msg = ActorExitRequest(recursive=True)
        self.actor_system.tell(self.system_actor, msg)


class SystemActor(Actor):
    def __init__(self):
        super(SystemActor, self).__init__()
        self.pipeline_actors = {}
        self.is_initialised = False

    def receiveMessage(self, msg, sender):
        if isinstance(msg, SystemInitRequest):
            if not self.is_initialised:
                self.init_pipelines(msg)
                self.is_initialised = True
            msg = SystemInitResponse(self.pipeline_actors.copy())
            self.send(sender, msg)

    def init_pipelines(self, msg):
        self.process_classes = msg.process_classes
        self.infrastructure_class = msg.infrastructure_class
        self.system_followings = msg.system_followings
        for pipeline_id in msg.pipeline_ids:
            pipeline_actor = self.createActor(PipelineActor)
            self.pipeline_actors[pipeline_id] = pipeline_actor
            msg = PipelineInitRequest(
                self.process_classes,
                self.infrastructure_class,
                self.system_followings,
                pipeline_id
            )
            self.send(pipeline_actor, msg)


class PipelineActor(Actor):
    def __init__(self):
        super(PipelineActor, self).__init__()
        self.system = None
        self.process_actors = {}
        self.pipeline_id = None

    def receiveMessage(self, msg, sender):
        if isinstance(msg, PipelineInitRequest):
            # logger.info("pipeline received init: {}".format(msg))
            self.init_pipeline(msg)
        elif isinstance(msg, Prompt):
            # logger.info("pipeline received prompt: {}".format(msg))
            self.forward_prompt(msg)

    def init_pipeline(self, msg):
        self.pipeline_id = msg.pipeline_id
        self.process_classes = msg.process_classes
        self.infrastructure_class = msg.infrastructure_class
        self.system_followings = msg.system_followings

        self.followers = {}
        for process_class_name, upstream_class_names in self.system_followings.items():
            for upstream_class_name in upstream_class_names:
                process_name = upstream_class_name.lower()
                if process_name not in self.followers:
                    self.followers[process_name] = []
                downstream_class_names = self.followers[process_name]
                if process_class_name not in downstream_class_names:
                    downstream_class_names.append(process_class_name)

        process_class_names = self.system_followings.keys()
        for process_class_name in process_class_names:
            process_actor = self.createActor(ProcessMaster)
            process_name = process_class_name.lower()
            self.process_actors[process_name] = process_actor

        for process_class_name in process_class_names:
            process_name = process_class_name.lower()
            upstream_application_names = [c.lower() for c in self.system_followings[process_class_name]]
            downstream_actors = {}
            for downstream_class_name in self.followers[process_name]:
                downstream_name = downstream_class_name.lower()
                # logger.warning("sending prompt to process application {}".format(downstream_name))
                process_actor = self.process_actors[downstream_name]
                downstream_actors[downstream_name] = process_actor
            process_class = self.process_classes[process_class_name]
            msg = ProcessInitRequest(
                process_class,
                self.infrastructure_class,
                self.pipeline_id,
                upstream_application_names,
                downstream_actors,
                self.myAddress
            )
            self.send(self.process_actors[process_name], msg)

    def forward_prompt(self, msg):
        for downstream_class_name in self.followers[msg.process_name]:
            downstream_name = downstream_class_name.lower()
            process_actor = self.process_actors[downstream_name]
            self.send(process_actor, msg)


class ProcessMaster(Actor):
    def __init__(self):
        super(ProcessMaster, self).__init__()
        self.is_slave_running = False
        self.last_prompts = {}
        self.slave_actor = None

    def receiveMessage(self, msg, sender):
        if isinstance(msg, ProcessInitRequest):
            self.init_process(msg)
        elif isinstance(msg, Prompt):
            # logger.warning("{} master received prompt: {}".format(self.process_application_class.__name__, msg))
            self.consume_prompt(prompt=msg)
        elif isinstance(msg, SlaveRunResponse):
            # logger.info("process application master received slave finished run: {}".format(msg))
            self.handle_slave_run_response()

    def init_process(self, msg):
        self.process_application_class = msg.process_application_class
        self.infrastructure_class = msg.infrastructure_class
        self.slave_actor = self.createActor(ProcessSlave)
        self.send(self.slave_actor, msg)
        self.run_slave()

    def consume_prompt(self, prompt):
        self.last_prompts[prompt.process_name] = prompt
        self.run_slave()

    def handle_slave_run_response(self):
        self.is_slave_running = False
        if self.last_prompts:
            self.run_slave()

    def run_slave(self):
        # Don't send to slave if we think it's running, or we'll
        # probably get blocked while sending the message and have
        # to wait until the slave runs its loop (thespian design).
        if self.slave_actor and not self.is_slave_running:
            self.send(self.slave_actor, SlaveRunRequest(self.last_prompts, self.myAddress))
            self.is_slave_running = True
            self.last_prompts = {}


class ProcessSlave(Actor):
    def __init__(self):
        super(ProcessSlave, self).__init__()
        self.process = None

    def receiveMessage(self, msg, sender):
        if isinstance(msg, ProcessInitRequest):
            # logger.info("process application slave received init: {}".format(msg))
            self.init_process(msg)
        elif isinstance(msg, SlaveRunRequest):
            # logger.info("{} process application slave received last prompts: {}".format(self.process.name, msg))
            self.run_process(msg)
        elif isinstance(msg, ActorExitRequest):
            # logger.info("{} process application slave received exit request: {}".format(self.process.name, msg))
            self.close()

    def init_process(self, msg):
        self.pipeline_actor = msg.pipeline_actor
        self.downstream_actors = msg.downstream_actors
        self.pipeline_id = msg.pipeline_id
        self.upstream_application_names = msg.upstream_application_names

        # Construct the process application class.
        process_class = msg.process_application_class
        if msg.infrastructure_class:
            process_class = process_class.mixin(msg.infrastructure_class)

        # Reset the database connection (for Django).
        process_class.reset_connection_after_forking()

        # Construct the process application.
        self.process = process_class(
            pipeline_id=self.pipeline_id,
        )
        assert isinstance(self.process, ProcessApplication)

        # Subscribe the slave actor's send_prompt() method.
        #  - the process application will call publish_prompt()
        #    and the actor will receive the prompt and send it
        #    as a message.
        subscribe(
            predicate=self.is_my_prompt,
            handler=self.send_prompt
        )

        # Close the process application persistence policy.
        #  - slave actor process application doesn't publish
        #    events, so we don't need this
        self.process.persistence_policy.close()

        # Unsubscribe process application's publish_prompt().
        #  - slave actor process application doesn't publish
        #    events, so we don't need this
        unsubscribe(
            predicate=self.process.persistence_policy.is_event,
            handler=self.process.publish_prompt
        )


        # Construct and follow upstream notification logs.
        for upstream_application_name in self.upstream_application_names:
            record_manager = self.process.event_store.record_manager
            # assert isinstance(record_manager, ACIDRecordManager), type(record_manager)
            notification_log = RecordManagerNotificationLog(
                record_manager=record_manager.clone(
                    application_name=upstream_application_name,
                    pipeline_id=self.pipeline_id
                ),
                section_size=self.process.notification_log_section_size
            )
            self.process.follow(upstream_application_name, notification_log)

    def run_process(self, msg):
        notification_count = 0
        # Just process one notification so prompts are dispatched promptly, sent
        # messages only dispatched from actor after receive_message() returns.
        advance_by = 1

        try:
            if msg.last_prompts:
                for prompt in msg.last_prompts.values():
                    notification_count += self.process.run(prompt, advance_by=advance_by)
            else:
                notification_count += self.process.run(advance_by=advance_by)
        except RecordConflictError:
            # Run again.
            self.send(self.myAddress, SlaveRunRequest(last_prompts={}, master=msg.master))
        else:
            if notification_count:
                # Run again, until nothing was done.
                self.send(self.myAddress, SlaveRunRequest(last_prompts={}, master=msg.master))
            else:
                # Report back to master.
                self.send(msg.master, SlaveRunResponse())

    def close(self):
        unsubscribe(
            predicate=self.is_my_prompt,
            handler=self.send_prompt
        )

        self.process.close()

    def is_my_prompt(self, prompt):
        return (
            isinstance(prompt, Prompt)
            and prompt.process_name == self.process.name
            and prompt.pipeline_id == self.pipeline_id
        )

    def send_prompt(self, prompt):
        for downstream_name, downstream_actor in self.downstream_actors.items():
            self.send(downstream_actor, prompt)


class SystemInitRequest(object):
    def __init__(self, process_classes, infrastructure_class, system_followings, pipeline_ids):
        self.process_classes = process_classes
        self.infrastructure_class = infrastructure_class
        self.system_followings = system_followings
        self.pipeline_ids = pipeline_ids


class SystemInitResponse(object):
    def __init__(self, pipeline_actors):
        self.pipeline_actors = pipeline_actors


class PipelineInitRequest(object):
    def __init__(self, process_classes, infrastructure_class, system_followings, pipeline_id):
        self.process_classes = process_classes
        self.infrastructure_class = infrastructure_class
        self.system_followings = system_followings
        self.pipeline_id = pipeline_id


class ProcessInitRequest(object):
    def __init__(self, process_application_class, infrastructure_class, pipeline_id,
                 upstream_application_names,
                 downstream_actors,
                 pipeline_actor):
        self.process_application_class = process_application_class
        self.infrastructure_class = infrastructure_class
        self.pipeline_id = pipeline_id
        self.upstream_application_names = upstream_application_names
        self.downstream_actors = downstream_actors
        self.pipeline_actor = pipeline_actor


class SlaveRunRequest(object):
    def __init__(self, last_prompts, master):
        self.last_prompts = last_prompts
        self.master = master


class SlaveRunResponse(object):
    pass
