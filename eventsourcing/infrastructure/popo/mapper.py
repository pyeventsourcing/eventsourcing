from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper


class SequencedItemMapperForPopo(SequencedItemMapper):
    def get_event_class_and_attrs(self, topic, data):
        return topic, data

    def get_item_topic_and_state(self, domain_event_class, event_attrs):
        return domain_event_class, event_attrs
