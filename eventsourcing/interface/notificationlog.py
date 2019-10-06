from __future__ import absolute_import, division, print_function, unicode_literals

import json

import requests

from eventsourcing.application.notificationlog import (
    Section,
    AbstractNotificationLog,
    LocalNotificationLog,
)
from eventsourcing.utils.transcoding import (
    ObjectJSONDecoder,
    ObjectJSONEncoder,
    json_dumps,
)


# These classes are imported here only to avoid breaking backwards compatibility.
# Todo: Remove this import statement >= v8.x
from eventsourcing.application.notificationlog import (
    RecordManagerNotificationLog,
    BigArrayNotificationLog,
)


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
        :param JSONDecoder json_decoder_class: JSON decoder class used to decode remote sections.
        """
        self.base_url = base_url
        self.json_decoder_class = json_decoder_class

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
            decoder_class = self.json_decoder_class or ObjectJSONDecoder
            section = Section(**json.loads(section_json, cls=decoder_class))
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

    def __init__(self, notification_log: LocalNotificationLog, json_encoder_class=None):
        """
        Initialises notification log view object.

        :param LocalNotificationLog notification_log: A notification log object
        :param JSONEncoder json_encoder_class: JSON encoder class
        """
        assert isinstance(notification_log, LocalNotificationLog), type(
            notification_log
        )
        self.notification_log = notification_log
        self.json_encoder_class = json_encoder_class or ObjectJSONEncoder

    def present_section(self, section_id):
        """

        Returns a section of notification log in JSON format.

        :param section_id: ID of the section of the notification log.
        :return: Identified section of notification log in JSON format.

        :rtype: str
        """
        section = self.notification_log[section_id]
        is_archived = bool(section.next_id)
        section_json = json_dumps(section.__dict__, self.json_encoder_class)
        return section_json, is_archived
