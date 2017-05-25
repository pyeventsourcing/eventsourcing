# from eventsourcing.example.application import ExampleApplication
# from eventsourcing.example.domainmodel import Example
# from eventsourcing.exceptions import ConcurrencyError, SequencedItemError
# from eventsourcing.tests.example_application_tests.base import ExampleApplicationTestCase
# from eventsourcing.tests.sequenced_item_tests.test_sqlalchemy_active_record_strategy import \
#     WithSQLAlchemyActiveRecordStrategies
#
#
# class TestFastForward(WithSQLAlchemyActiveRecordStrategies, ExampleApplicationTestCase):
#
#     def test(self):
#         with self.construct_application() as app:
#             assert isinstance(app, ExampleApplication)
#             example = app.create_new_example(1, 2)
#             instance1 = app.example_repo[example.id]
#             instance2 = app.example_repo[example.id]
#
#             assert isinstance(instance1, Example)
#             assert isinstance(instance2, Example)
#
#             self.assertEqual(instance1.version, 1)
#             self.assertEqual(instance2.version, 1)
#
#             # Evolve instance1 by a version.
#             instance1.beat_heart()
#             self.assertEqual(instance1.version, 2)
#
#             # Fail to evolve instance2 in the same way.
#             # Todo: This needs to be a deepcopy.
#             preop_state = instance2.__dict__.copy()
#             with self.assertRaises(SequencedItemError):
#                 instance2.beat_heart()
#
#             # Reset instance2 to its pre-op state.
#             instance2.__dict__.update(preop_state)
#             self.assertEqual(instance2.version, 1)
#
#             # Fast forward instance2 from pre-op state.
#             instance3 = app.example_repo.fastforward(instance2)
#             self.assertEqual(instance2.version, 1)
#             self.assertEqual(instance3.version, 2)
#
#             # Try again to beat heart.
#             instance3.beat_heart()
#             self.assertEqual(instance3.version, 3)
#
#             # Try to evolve instance1 from its stale version.
#             preop_state = instance1.__dict__.copy()
#             with self.assertRaises(ConcurrencyError):
#                 instance1.beat_heart()
#
#             # Reset instance1 to pre-op state.
#             instance1.__dict__.update(preop_state)
#
#             # Fast forward instance1 from pre-op state.
#             instance4 = app.example_repo.fastforward(instance1)
#             self.assertEqual(instance1.version, 2)
#             self.assertEqual(instance4.version, 3)
#
#             # Try again to beat heart.
#             instance4.beat_heart()
#             self.assertEqual(instance4.version, 4)
