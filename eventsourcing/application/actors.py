import logging
import time

from thespian.actors import *

from eventsourcing.application.process import Prompt
from eventsourcing.application.system import System
from eventsourcing.domain.model.events import subscribe, unsubscribe
from eventsourcing.infrastructure.sqlalchemy.manager import SQLAlchemyRecordManager
from eventsourcing.interface.notificationlog import RecordManagerNotificationLog
from eventsourcing.utils.uuids import uuid_from_application_name

logger = logging.getLogger()


class Actors(object):
    def __init__(self, system, pipeline_ids, system_actor_name='system'):
        assert isinstance(system, System)
        self.system = system
        self.pipeline_ids = pipeline_ids
        self.pipeline_actors = {}
        self.system_actor_name = system_actor_name

    @property
    def actor_system(self):
        return ActorSystem()

    def start(self):
        # Subscribe to broadcast prompts published by a process
        # application in the parent operating system process.
        subscribe(handler=self.forward_prompt, predicate=self.is_prompt)

        # Create the system actor.
        self.system_actor = self.actor_system.createActor(
            actorClass=SystemActor,
            globalName=self.system_actor_name
        )

        # Initialise the system actor.
        command = InitSystem(self.system.followings, self.pipeline_ids)
        response = self.actor_system.ask(self.system_actor, command)

        # Keep the pipeline actor addresses, to send prompts directly.
        self.pipeline_actors = response.pipeline_actors
        # Todo: Somehow know when to get a new address from the system actor.
        # Todo: Command and response messages to system actor to get new pipeline address.

    @staticmethod
    def is_prompt(event):
        return isinstance(event, Prompt)

    def forward_prompt(self, prompt):
        self.actor_system.tell(self.pipeline_actors[prompt.pipeline_id], prompt)

    def close(self):
        unsubscribe(handler=self.forward_prompt, predicate=self.is_prompt)
        self.actor_system.tell(self.system_actor, ActorExitRequest(recursive=True))

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class SystemActor(Actor):
    def __init__(self):
        super(SystemActor, self).__init__()
        self.pipeline_actors = {}

    def receiveMessage(self, msg, sender):
        if isinstance(msg, InitSystem):
            self.init_pipelines(msg)
            self.send(sender, SystemInited(self.pipeline_actors.copy()))
        elif isinstance(msg, Prompt):
            self.forward_prompt(msg)

    def init_pipelines(self, msg):
        self.system_followings = msg.system_followings
        for pipeline_id in msg.pipeline_ids:
            pipeline_actor = self.createActor(PipelineActor)
            self.pipeline_actors[pipeline_id] = pipeline_actor
            self.send(pipeline_actor, InitPipeline(self.system_followings, pipeline_id))

    def forward_prompt(self, prompt):
        pipeline_actor = self.pipeline_actors.get(prompt.pipeline_id)
        if pipeline_actor:
            self.send(pipeline_actor, prompt)


class PipelineActor(Actor):
    def __init__(self):
        super(PipelineActor, self).__init__()
        self.system = None
        self.process_actors = {}
        self.pipeline_id = None

    def receiveMessage(self, msg, sender):
        try:
            if isinstance(msg, InitPipeline):
                # logger.info("pipeline received init: {}".format(msg))
                self.init_pipeline(msg)
            elif isinstance(msg, Prompt):
                # logger.info("pipeline received prompt: {}".format(msg))
                self.forward_prompt(msg)
        except Exception as e:
            logger.error("error in {}: {}".format(self, e))
            raise
            pass

    def init_pipeline(self, msg):
        self.pipeline_id = msg.pipeline_id
        self.system_followings = msg.system_followings

        self.followers = {}
        for process_class, upstream_classes in self.system_followings.items():
            for upstream_class in upstream_classes:
                process_name = upstream_class.__name__.lower()
                if process_name not in self.followers:
                    self.followers[process_name] = []
                downstream_classes = self.followers[process_name]
                if process_class not in downstream_classes:
                    downstream_classes.append(process_class)

        process_classes = self.system_followings.keys()
        for process_class in process_classes:
            process_actor = self.createActor(ProcessMaster)
            process_name = process_class.__name__.lower()
            self.process_actors[process_name] = process_actor

        for process_class in process_classes:
            process_name = process_class.__name__.lower()
            upstream_application_names = [c.__name__.lower() for c in self.system_followings[process_class]]
            downstream_actors = {}
            for downstream_class in self.followers[process_name]:
                downstream_name = downstream_class.__name__.lower()
                # logger.warning("sending prompt to process application {}".format(downstream_name))
                process_actor = self.process_actors[downstream_name]
                downstream_actors[downstream_name] = process_actor

            msg = InitProcess(process_class, self.pipeline_id, upstream_application_names, downstream_actors,
                              self.myAddress)
            self.send(self.process_actors[process_name], msg)

    def forward_prompt(self, msg):
        for downstream_class in self.followers[msg.process_name]:
            downstream_name = downstream_class.__name__.lower()
            process_actor = self.process_actors[downstream_name]
            self.send(process_actor, msg)


class NoneEvent(object):
    pass


class ProcessMaster(Actor):
    def __init__(self):
        super(ProcessMaster, self).__init__()
        self.is_worker_running = False
        self.last_prompts = {}

    def receiveMessage(self, msg, sender):
        try:
            if isinstance(msg, InitProcess):
                self.init_process(msg)
            elif isinstance(msg, Prompt):
                # logger.warning("{} master received prompt: {}".format(self.process_application_class.__name__, msg))
                self.consume_prompt(prompt=msg)
            elif isinstance(msg, WorkerFinishedRun):
                # logger.info("process application master received worker finished run: {}".format(msg))
                self.handle_worker_finished_run()
        except Exception as e:
            logger.error("error in {}: {} {}".format(self, type(e), e))
            raise

    def init_process(self, msg):
        self.process_application_class = msg.process_application_class
        self.worker_actor = self.createActor(ProcessSlave)
        self.send(self.worker_actor, msg)
        self.run_worker()

    def consume_prompt(self, prompt):
        self.last_prompts[prompt.process_name] = prompt
        if not self.is_worker_running:
            # logger.info("worker not running, sending last prompts to worker")
            self.run_worker()
        # else:
        #     logger.info("worker is running, prompt was held")

    def handle_worker_finished_run(self):
        # logger.info("worker finished running ")
        self.is_worker_running = False
        if self.last_prompts:
            # logger.info("more last prompts so running worker again")
            self.run_worker()
        # Todo: Send timer message to self to run worker every so often.
        # else:
            # self.run_worker()

    def run_worker(self):
        self.is_worker_running = True
        self.send(self.worker_actor, RunWorker(self.last_prompts))
        self.last_prompts = {}


class ProcessSlave(Actor):
    def __init__(self):
        super(ProcessSlave, self).__init__()
        self.process = None

    def receiveMessage(self, msg, sender):
        try:
            if isinstance(msg, InitProcess):
                # logger.info("process application worker received init: {}".format(msg))
                self.init_process(msg)
            elif isinstance(msg, RunWorker):
                # logger.info("{} process application worker received last prompts: {}".format(self.process.name, msg))
                self.run_process(msg, sender)
            elif isinstance(msg, ActorExitRequest):
                # logger.info("{} process application worker received exit request: {}".format(self.process.name, msg))
                self.process.close()
            # elif isinstance(msg, ChildActorExited):
            #     logger.info("{} process application worker received exit request: {}".format(self.process.name, msg))
            #     pass
            # else:
            #     logger.warning("unknown msg to slave {}: {}".format(self.process.name, msg))
            #     pass
        except Exception as e:
            # logger.error("error in {}: {}".format(self, e))
            raise

    def init_process(self, msg):
        self.pipeline_actor = msg.pipeline_actor
        self.downstream_actors = msg.downstream_actors
        self.pipeline_id = msg.pipeline_id
        self.upstream_application_names = msg.upstream_application_names

        self.process = msg.process_application_class(
            pipeline_id=self.pipeline_id,
            notification_log_section_size=5,
            pool_size=3,
            persist_event_type=NoneEvent,  # Disable persistence subscriber.
        )
        # Cancel publish_prompt().
        self.process.publish_prompt = lambda *args: self.publish_prompt(*args)

        # Construct and follow upstream notification logs.
        for upstream_application_name in self.upstream_application_names:
            record_manager = self.process.event_store.record_manager
            assert isinstance(record_manager, SQLAlchemyRecordManager)
            upstream_application_id = uuid_from_application_name(upstream_application_name)
            notification_log = RecordManagerNotificationLog(
                record_manager=type(record_manager)(
                    session=record_manager.session,
                    record_class=record_manager.record_class,
                    contiguous_record_ids=record_manager.contiguous_record_ids,
                    sequenced_item_class=record_manager.sequenced_item_class,
                    application_id=upstream_application_id,
                    pipeline_id=self.pipeline_id
                ),
                section_size=self.process.notification_log_section_size
            )
            self.process.follow(upstream_application_name, notification_log)

    def run_process(self, msg, master):
        # logger.warning("---- running {} process application".format(self.process.name))
        if msg.last_prompts:
            for prompt in msg.last_prompts.values():
                self.process.run(prompt)
        else:
            self.process.run()
        # while self.process.run():
        # #     while self.process.run():
        # #         while self.process.run():
        # #             logger.warning("---- continuing running {} process application".format(self.process.name))
        # #             time.sleep(0.1)
        # #         logger.warning("---- continuing running {} process application".format(self.process.name))
        # #         time.sleep(0.5)
        #     logger.warning("---- continuing running {} process application".format(self.process.name))
            # time.sleep(0.1)
        #
        # logger.warning("---- finished running {} process application".format(self.process.name))

        # Report to master.
        self.send(master, WorkerFinishedRun())

    def publish_prompt(self, end_position=None):
        prompt = Prompt(self.process.name, self.process.pipeline_id, end_position=end_position)
        # logger.info("publishing prompt from {} process application".format(self.process.name))
        for downstream_name, downstream_actor in self.downstream_actors.items():
            self.send(downstream_actor, prompt)
            # logger.warning("published prompt from {} to {} in pipeline {}".format(self.process.name, downstream_name,
            #                                                                    self.pipeline_id))


class InitSystem(object):
    def __init__(self, system_followings, pipeline_ids):
        self.system_followings = system_followings
        self.pipeline_ids = pipeline_ids


class SystemInited(object):
    def __init__(self, pipeline_actors):
        self.pipeline_actors = pipeline_actors


class InitPipeline(object):
    def __init__(self, system_followings, pipeline_id):
        self.system_followings = system_followings
        self.pipeline_id = pipeline_id


class InitProcess(object):
    def __init__(self, process_application_class, pipeline_id, upstream_application_names, downstream_actors,
                 pipeline_actor):
        self.process_application_class = process_application_class
        self.pipeline_id = pipeline_id
        self.upstream_application_names = upstream_application_names
        self.downstream_actors = downstream_actors
        self.pipeline_actor = pipeline_actor


class RunWorker(object):
    def __init__(self, last_prompts):
        self.last_prompts = last_prompts


class WorkerFinishedRun(object):
    pass
