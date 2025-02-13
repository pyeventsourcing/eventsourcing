from typing import ClassVar
from unittest import TestCase

from eventsourcing.domain import WithTopicRegistryDetails


class TestWithTopicRegistryDetails(TestCase):

    def test_get_topics_for_registration_no_explicit_data(self):
        class MyClass(WithTopicRegistryDetails):
            pass

        self.assertEqual(set(), MyClass.get_topics_for_registration())

    def test_get_topics_for_registration_empty(self):
        class MyClass(WithTopicRegistryDetails):
            EXPLICIT_TOPIC = None
            _LEGACY_TOPICS: ClassVar[set] = set()

        self.assertEqual(set(), MyClass.get_topics_for_registration())

    def test_get_topics_for_registration_with_explicit_topic(self):
        test_explicit_topic = "MyTopic"

        class MyClass(WithTopicRegistryDetails):
            EXPLICIT_TOPIC = test_explicit_topic

        self.assertEqual({test_explicit_topic}, MyClass.get_topics_for_registration())

    def test_get_topics_for_registration_with_legacy_topics(self):
        test_legacy_topic = {"LegacyTopic1", "LegacyTopic2"}

        class MyClass(WithTopicRegistryDetails):
            EXPLICIT_TOPIC = None
            _LEGACY_TOPICS = test_legacy_topic

        self.assertEqual(test_legacy_topic, MyClass.get_topics_for_registration())

    def test_get_topics_for_registration_with_explicit_topic_and_legacy_topics(self):
        test_explicit_topic = "MyTopic"
        test_legacy_topic1 = "LegacyTopic1"
        test_legacy_topic2 = "LegacyTopic2"
        test_legacy_topic = {test_legacy_topic1, test_legacy_topic2}

        class MyClass(WithTopicRegistryDetails):
            EXPLICIT_TOPIC = test_explicit_topic
            _LEGACY_TOPICS = test_legacy_topic

        self.assertEqual(
            {test_explicit_topic, test_legacy_topic1, test_legacy_topic2},
            MyClass.get_topics_for_registration(),
        )
