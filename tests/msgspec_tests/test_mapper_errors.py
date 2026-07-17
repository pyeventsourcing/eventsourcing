# from unittest import TestCase
# from uuid import uuid4
#
# from eventsourcing.msgspec.immutable import DomainEvent
# from eventsourcing.msgspec.mapper import MsgspecMapper
# from eventsourcing.persistence import NullTranscoder
#
#
# class TestMsgspecMapper(TestCase):
#     def setUp(self) -> None:
#         self.mapper = MsgspecMapper(transcoder=NullTranscoder())
#
#     def test_raises_if_signature_has_type_var(self) -> None:
#         # Define a class that hasn't got type args for all type params.
#         class MyEvent(DomainEvent):
#             pass
#
#         event = MyEvent(
#             originator_id=uuid4(),
#             originator_version=1,
#         )
#
#         stored = self.mapper.to_stored_event(event)
#
#         with self.assertRaises(TypeError) as cm:
#             self.mapper.to_domain_event(stored)
#
#         self.assertIn("Failed to decode msgspec struct", str(cm.exception))
#         self.assertIn("originator_id: ~TAggregateID", str(cm.exception))
