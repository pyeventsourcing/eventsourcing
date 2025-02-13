from typing import ClassVar
from unittest import TestCase

from eventsourcing.domain import WithTopicRegistryDetails


class TestWithTopicRegistryDetails(TestCase):

    def test_get_topics_for_registration_no_class_data(self):
        class MyClass(WithTopicRegistryDetails):
            pass

        self.assertEqual(set(), MyClass.get_topics_for_registration())

    def test_get_topics_for_registration_empty(self):
        class MyClass(WithTopicRegistryDetails):
            class_topic = None
            _legacy_topics: ClassVar[set] = set()

        self.assertEqual(set(), MyClass.get_topics_for_registration())

    def test_get_topics_for_registration_with_class_topic(self):
        test_class_topic = "MyTopic"

        class MyClass(WithTopicRegistryDetails):
            class_topic = test_class_topic

        self.assertEqual({test_class_topic}, MyClass.get_topics_for_registration())

    def test_get_topics_for_registration_with_legacy_topics(self):
        test_legacy_topic = {"LegacyTopic1", "LegacyTopic2"}

        class MyClass(WithTopicRegistryDetails):
            class_topic = None
            _legacy_topics = test_legacy_topic

        self.assertEqual(test_legacy_topic, MyClass.get_topics_for_registration())

    def test_get_topics_for_registration_with_class_topic_and_legacy_topics(self):
        test_class_topic = "MyTopic"
        test_legacy_topic1 = "LegacyTopic1"
        test_legacy_topic2 = "LegacyTopic2"
        test_legacy_topic = {test_legacy_topic1, test_legacy_topic2}

        class MyClass(WithTopicRegistryDetails):
            class_topic = test_class_topic
            _legacy_topics = test_legacy_topic

        self.assertEqual(
            {test_class_topic, test_legacy_topic1, test_legacy_topic2},
            MyClass.get_topics_for_registration(),
        )
