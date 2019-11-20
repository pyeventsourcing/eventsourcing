from __future__ import absolute_import, division, print_function, unicode_literals

from json import JSONDecodeError, JSONDecoder, JSONEncoder
from typing import Optional, Type

import requests

from eventsourcing.application.notificationlog import (
    AbstractNotificationLog,
    LocalNotificationLog,
    Section,
)
from eventsourcing.utils.transcoding import ObjectJSONDecoder


# These classes are imported here only to avoid breaking backwards compatibility.
# Todo: Remove this import statement >= v8.x


class RemoteNotificationLog(AbstractNotificationLog):
    """
    Presents notification log sections retrieved an HTTP API
    that presents notification log sections in JSON format,
    for example by using a NotificationLogView.
    """

    def __init__(
        self, base_url: str, json_decoder_class: Optional[Type[JSONDecoder]] = None
    ):
        """
        Initialises remote notification log object.

        :param str base_url: A URL for the HTTP API.
        :param JSONDecoder json_decoder_class: used to deserialize remote sections.
        """
        self.base_url = base_url
        json_decoder_class_ = json_decoder_class or ObjectJSONDecoder
        self.json_decoder = json_decoder_class_()
        self._section_size = -1

    def json_loads(self, value: str) -> object:
        try:
            return self.json_decoder.decode(value)
        except JSONDecodeError:
            raise ValueError("Couldn't load JSON string: {}".format(value))

    def __getitem__(self, section_id: str) -> Section:
        """
        Returns a section of notification log.

        :param str section_id: ID of the section of the notification log.
        :return: Identified section of notification log.
        :rtype: Section
        """
        section_json = self.get_json(section_id)
        return self.deserialize_section(section_json)

    @property
    def section_size(self) -> int:
        """
        Size of section of notification log.
        """
        if self._section_size == -1:
            resource = self.get_resource(self.make_notification_log_url("section_size"))

            try:
                section_size = self.json_loads(resource)
            except:
                raise ValueError(
                    "Failed to decode JSON 'section_size' resource: {}".format(resource)
                )
            if isinstance(section_size, int):
                self._section_size = section_size
            else:
                raise ValueError(
                    "Section size is not an int: {}".format(type(section_size))
                )
        return self._section_size

    def deserialize_section(self, section_json: str) -> Section:
        try:
            obj = self.json_loads(section_json)
            assert isinstance(obj, dict)
            section = Section(**obj)
        except ValueError as e:
            raise ValueError(
                "Couldn't deserialize notification log section: "
                "{}: {}".format(e, section_json)
            )
        return section

    def get_json(self, section_id: str) -> str:
        notification_log_url = self.make_notification_log_url(section_id)
        return self.get_resource(notification_log_url)

    def make_notification_log_url(self, section_id: str) -> str:
        return "{}/{}/".format(self.base_url.strip("/"), section_id)

    def get_resource(self, doc_url: str) -> str:
        return requests.get(doc_url).content.decode("utf8")


class NotificationLogView(object):
    """
    Presents sections of a notification log in JSON format.

    Can be used to make an HTTP API that can be used
    remotely, for example by a RemoteNotificationLog.
    """

    def __init__(
        self, notification_log: LocalNotificationLog, json_encoder: JSONEncoder
    ):
        """
        Initialises notification log view object.

        :param notification_log: A notification log object
        :param json_encoder_class: JSON encoder class
        """
        assert isinstance(notification_log, LocalNotificationLog), type(
            notification_log
        )
        self.notification_log = notification_log
        self.json_encoder = json_encoder

    def present_resource(self, name: str) -> str:
        """
        Returns a resource of the notification log in JSON format.

        Supports returning section of the notification log.

        Also supports returning section_size of notification
        log, if section_id has special value 'section_size'.

        :param name: Name of the resource, e.g. a section ID.
        :return: Identified resource of notification log view in JSON format.
        """
        if name == 'section_size':
            # Present the notification log's configured section size.
            section_size = self.notification_log.section_size
            resource = self.json_encoder.encode(section_size)
        else:
            # Default to assuming the resource is a section.
            section = self.notification_log[name]
            resource = self.json_encoder.encode(section.__dict__)

        return resource

    def present_section(self, section_id: str) -> str:
        """
        For backwards compatibility (deprecation warning from 7.3.0).
        """
        return self.present_section(section_id)
