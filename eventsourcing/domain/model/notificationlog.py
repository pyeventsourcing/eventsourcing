# from singledispatch import singledispatch
#
# from eventsourcing.domain.model.entity import AbstractEntityRepository, TimestampedVersionedEntity, Created,
# entity_mutator
# from eventsourcing.domain.model.events import publish
# from eventsourcing.exceptions import RepositoryKeyError
#
#
# class NotificationLog(TimestampedVersionedEntity):
#     class Started(Created):
#         pass
#
#     def __init__(self, name, bucket_size=None, sequence_size=None, **kwargs):
#         super(NotificationLog, self).__init__(**kwargs)
#         self._name = name
#         self._sequence_size = sequence_size
#         self._bucket_size = bucket_size
#
#     @property
#     def name(self):
#         return self._name
#
#     @property
#     def sequence_size(self):
#         return self._sequence_size
#
#     @property
#     def bucket_size(self):
#         return self._bucket_size
#
#     @staticmethod
#     def _mutator(event, initial):
#         return notification_log_mutator(event, initial)
#
#
# @singledispatch
# def notification_log_mutator(event, initial):
#     return entity_mutator(event, initial)
#
#
# class NotificationLogRepository(AbstractEntityRepository):
#     def get_or_create(self, log_name, timebucket_size=None, sequence_size=None):
#         """
#         Gets or creates a log.
#
#         :rtype: NotificationLog
#         """
#         try:
#             return self[log_name]
#         except RepositoryKeyError:
#             return start_notification_log(
#                 log_name=log_name,
#                 timebucket_size=timebucket_size,
#                 sequence_size=sequence_size,
#             )
#
#
# def start_notification_log(log_name, timebucket_size=None, sequence_size=None):
#     event = NotificationLog.Started(
#         originator_id=log_name,
#         name=log_name,
#         bucket_size=timebucket_size,
#         sequence_size=sequence_size,
#     )
#     entity = NotificationLog.mutate(event=event)
#     publish(event)
#     return entity
