from __future__ import absolute_import, division, print_function, unicode_literals

from json import JSONDecodeError

import requests

from eventsourcing.application.notificationlog import (
    AbstractNotificationLog,
    LocalNotificationLog,
    Section,
    RecordManagerNotificationLog)
from eventsourcing.utils.transcoding import ObjectJSONDecoder


# These classes are imported here only to avoid breaking backwards compatibility.
# Todo: Remove this import statement >= v8.x


class RemoteNotificationLog(AbstractNotificationLog):
    """
    Presents notification log sections retrieved an HTTP API
    that presents notification log sections in JSON format,
    for example by using a NotificationLogView.
    """

    def __init__(self, base_url, json_decoder_class=None):
        """
        Initialises remote notification log object.

        :param str base_url: A URL for the HTTP API.
        :param JSONDecoder json_decoder_class: used to deserialize remote sections.
        """
        self.base_url = base_url
        json_decoder_class = json_decoder_class or ObjectJSONDecoder
        self.json_decoder = json_decoder_class()

    def json_loads(self, value: str):
        try:
            return self.json_decoder.decode(value)
        except JSONDecodeError:
            raise ValueError("Couldn't load JSON string: {}".format(value))

    def __getitem__(self, section_id):
        """
        Returns a section of notification log.

        :param str section_id: ID of the section of the notification log.
        :return: Identified section of notification log.
        :rtype: Section
        """
        section_json = self.get_json(section_id)
        return self.deserialize_section(section_json)

    def deserialize_section(self, section_json):
        try:
            section = Section(**self.json_loads(section_json))
        except ValueError as e:
            raise ValueError(
                "Couldn't deserialize notification log section: "
                "{}: {}".format(e, section_json)
            )
        return section

    def get_json(self, section_id):
        notification_log_url = self.make_notification_log_url(section_id)
        return self.get_resource(notification_log_url)

    def get_resource(self, doc_url):
        representation = requests.get(doc_url).content
        if isinstance(representation, type(b"")):
            representation = representation.decode("utf8")
        return representation

    def make_notification_log_url(self, section_id):
        return "{}/{}/".format(self.base_url.strip("/"), section_id)


class NotificationLogView(object):
    """
    Presents sections of a notification log in JSON format.

    Can be used to make an HTTP API that can be used
    remotely, for example by a RemoteNotificationLog.
    """

    def __init__(self, notification_log: RecordManagerNotificationLog, json_encoder):
        """
        Initialises notification log view object.

        :param LocalNotificationLog notification_log: A notification log object
        :param JSONEncoder json_encoder_class: JSON encoder class
        """
        assert isinstance(notification_log, LocalNotificationLog), type(
            notification_log
        )
        self.notification_log = notification_log
        self.json_encoder = json_encoder

    def present_section(self, section_id):
        """

        Returns a section of notification log in JSON format.

        :param section_id: ID of the section of the notification log.
        :return: Identified section of notification log in JSON format.

        :rtype: str
        """
        section = self.notification_log[section_id]
        is_archived = bool(section.next_id)
        section_json = self.json_encoder.encode(section.__dict__)
        return section_json, is_archived
