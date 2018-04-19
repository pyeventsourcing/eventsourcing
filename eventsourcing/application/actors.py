import logging

import time
from thespian.actors import *

from eventsourcing.application.process import Prompt
from eventsourcing.domain.model.events import subscribe, unsubscribe
from eventsourcing.infrastructure.sqlalchemy.manager import SQLAlchemyRecordManager
from eventsourcing.interface.notificationlog import RecordManagerNotificationLog
from eventsourcing.utils.uuids import uuid_from_application_name



logger = logging.getLogger('')
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
logger.addHandler(ch)


logcfg = {
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


class Actors(object):
    def __init__(self, system, pipeline_ids, actor_system_base):
        self.system = system
        self.pipeline_ids = pipeline_ids
        self.pipeline_actors = {}
        self.actor_system_base = actor_system_base

    @property
    def actor_system(self):
        return ActorSystem(self.actor_system_base, logDefs=logcfg)

    def start(self):
        # Subscribe to broadcast prompts published by a process
        # application in the parent operating system process.
        subscribe(handler=self.broadcast_prompt, predicate=self.is_prompt)

        for pipeline_id in self.pipeline_ids:
            pipeline_actor = self.actor_system.createActor(PipelineActor)
            time.sleep(0.01)
            self.pipeline_actors[pipeline_id] = pipeline_actor
            msg = InitPipeline(self.system.followings, pipeline_id)
            self.actor_system.tell(pipeline_actor, msg)
            time.sleep(0.01)

    @staticmethod
    def is_prompt(event):
        return isinstance(event, Prompt)

    def broadcast_prompt(self, prompt):
        pipeline_actor = self.pipeline_actors[prompt.pipeline_id]
        self.actor_system.tell(pipeline_actor, prompt)

    def close(self):
        unsubscribe(handler=self.broadcast_prompt, predicate=self.is_prompt)
        for pipeline_actor in self.pipeline_actors.values():
            self.actor_system.tell(pipeline_actor, ActorExitRequest(recursive=True))
        self.actor_system.shutdown()
        time.sleep(0.1)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class PipelineActor(Actor):
    def __init__(self):
        super(PipelineActor, self).__init__()
        self.system = None
        self.process_actors = {}

    def receiveMessage(self, msg, sender):
        try:
            if isinstance(msg, InitPipeline):
                logger.info("pipeline received init: {}".format(msg))
                self.init_pipeline(msg.pipeline_id, msg.system_followings)
            elif isinstance(msg, Prompt):
                logger.info("pipeline received prompt: {}".format(msg))
                self.send_prompt(msg)
            elif isinstance(msg, ActorExitRequest):
                logger.info("pipeline received exit request: {}".format(msg))
                pass
            elif isinstance(msg, ChildActorExited):
                logger.info('pipeline child exited: {}'.format(msg.childAddress))
                # logger.info('pipeline child exited')
            else:
                # logger.warning("unknown msg to pipeline actor: {}".format(msg))
                pass
        except Exception as e:
            logger.error("error in {}: {}".format(self, e))
            raise
            pass

    def init_pipeline(self, pipeline_id, system_followings):
        self.pipeline_id = pipeline_id
        self.system_followings = system_followings

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
            process_actor = self.createActor(ProcessApplicationActor)
            process_name = process_class.__name__.lower()
            self.process_actors[process_name] = process_actor
            upstream_application_names = [c.__name__.lower() for c in self.system_followings[process_class]]
            msg = InitProcess(process_class, pipeline_id, upstream_application_names, self.myAddress)
            self.send(process_actor, msg)

    def send_prompt(self, msg):

        for downstream_class in self.followers[msg.process_name]:
            downstream_name = downstream_class.__name__.lower()
            # logger.warning("sending prompt to process application {}".format(downstream_name))
            process_actor = self.process_actors[downstream_name]
            self.send(process_actor, msg)


class NoneEvent(object):
    pass


class ProcessApplicationActor(Actor):
    def __init__(self):
        self.process = None

    def receiveMessage(self, msg, sender):
        try:
            if isinstance(msg, InitProcess):
                logger.info("process application received init: {}".format(msg))
                self.pipeline_actor = msg.pipeline_actor
                self.init_process(msg.process_application_class, msg.pipeline_id, msg.upstream_application_names)
            elif isinstance(msg, Prompt):
                logger.info("{} process application received prompt: {}".format(self.process.name, msg))
                self.handle_prompt(msg)
            elif isinstance(msg, ActorExitRequest):
                logger.info("process application {} received exit request: {}".format(self.process.name, msg))
                self.process.close()
            else:
                # logger.warning("unknown msg to {}: {}".format(self.process.name, msg))
                pass
        except Exception as e:
            logger.error("error in {}: {}".format(self, e))
            raise
            pass

    def init_process(self, process_application_class, pipeline_id, upstream_application_names):
        self.process = process_application_class(
            pipeline_id=pipeline_id,
            notification_log_section_size=50,
            pool_size=5,
            persist_event_type=NoneEvent,  # Disable persistence subscriber.
        )
        # Cancel publish_prompts().
        self.process.publish_prompt = lambda *args: self.publish_prompt(*args)
        for upstream_application_name in upstream_application_names:
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
                    pipeline_id=pipeline_id
                ),
                section_size=self.process.notification_log_section_size
            )
            self.process.follow(upstream_application_name, notification_log)

    def handle_prompt(self, prompt):
        # logger.info("handling prompt in {} process application".format(self.process.name))
        self.process.run(prompt)

    def publish_prompt(self, end_position=None):
        prompt = Prompt(self.process.name, self.process.pipeline_id, end_position=end_position)
        # logger.info("publishing prompt from {} process application".format(self.process.name))
        self.send(self.pipeline_actor, prompt)
        # logger.info("published prompt from {} process application".format(self.process.name))


class InitPipeline(object):
    def __init__(self, system_followings, pipeline_id):
        self.system_followings = system_followings
        self.pipeline_id = pipeline_id


class InitProcess(object):
    def __init__(self, process_application_class, pipeline_id, upstream_application_names, pipeline_actor):
        self.process_application_class = process_application_class
        self.pipeline_id = pipeline_id
        self.upstream_application_names = upstream_application_names
        self.pipeline_actor = pipeline_actor
