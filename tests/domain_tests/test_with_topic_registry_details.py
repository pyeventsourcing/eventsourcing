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
            _LEGACY_TOPICS = set()

        self.assertEqual(set(), MyClass.get_topics_for_registration())

    def test_get_topics_for_registration_with_explicit_topic(self):
        TEST_EXPLICIT_TOPIC = "MyTopic"

        class MyClass(WithTopicRegistryDetails):
            EXPLICIT_TOPIC = TEST_EXPLICIT_TOPIC

        self.assertEqual({TEST_EXPLICIT_TOPIC}, MyClass.get_topics_for_registration())

    def test_get_topics_for_registration_with_legacy_topics(self):
        TEST_LEGACY_TOPICS = {"LegacyTopic1", "LegacyTopic2"}

        class MyClass(WithTopicRegistryDetails):
            EXPLICIT_TOPIC = None
            _LEGACY_TOPICS = TEST_LEGACY_TOPICS

        self.assertEqual(TEST_LEGACY_TOPICS, MyClass.get_topics_for_registration())

    def test_get_topics_for_registration_with_explicit_topic_and_legacy_topics(self):
        TEST_EXPLICIT_TOPIC = "MyTopic"
        TEST_LEGACY_TOPIC_1 = "LegacyTopic1"
        TEST_LEGACY_TOPIC_2 = "LegacyTopic2"
        TEST_LEGACY_TOPICS = {TEST_LEGACY_TOPIC_1, TEST_LEGACY_TOPIC_2}

        class MyClass(WithTopicRegistryDetails):
            EXPLICIT_TOPIC = TEST_EXPLICIT_TOPIC
            _LEGACY_TOPICS = TEST_LEGACY_TOPICS

        self.assertEqual(
            {TEST_EXPLICIT_TOPIC, TEST_LEGACY_TOPIC_1, TEST_LEGACY_TOPIC_2},
            MyClass.get_topics_for_registration(),
        )
