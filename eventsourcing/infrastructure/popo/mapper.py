from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper


class SequencedItemMapperForPopo(SequencedItemMapper):
    def get_class_and_state(self, topic, data):
        return topic, data

    def get_topic_and_data(self, domain_event_class, event_attrs):
        return domain_event_class, event_attrs
