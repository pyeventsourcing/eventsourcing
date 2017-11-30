# from unittest.case import TestCase
# from uuid import uuid4
#
# from eventsourcing.domain.model.entity import EntityIsDiscarded, WithReflexiveMutator
# from eventsourcing.example.domainmodel import Example
# from eventsourcing.utils.topic import get_topic
#
#
# class ExampleWithReflexiveMutatorDefaultsToBaseClass(WithReflexiveMutator, Example):
#     """Doesn't redefine events with mutate methods, calls parent method instead."""
#
#
# class ExampleWithReflexiveMutator(WithReflexiveMutator, Example):
#     class Event(Example.Event):
#         """Supertype for events of example entities with reflexive mutator."""
#
#     class Created(Event, Example.Created):
#         def mutate(self, cls):
#             constructor_args = self.__dict__.copy()
#             constructor_args['id'] = constructor_args.pop('originator_id')
#             constructor_args['version'] = constructor_args.pop('originator_version')
#             return cls(**constructor_args)
#
#     class AttributeChanged(Event, Example.AttributeChanged):
#         def mutate(self, entity):
#             entity._validate_originator(self)
#             setattr(entity, self.name, self.value)
#             entity._last_modified = self.timestamp
#             entity._increment_version()
#             return entity
#
#     class Discarded(Event, Example.Discarded):
#         def mutate(self, entity):
#             entity._validate_originator(self)
#             entity._is_discarded = True
#             entity._increment_version()
#             return None
#
#
# class TestWithReflexiveMutatorDefaultsToBaseClass(TestCase):
#     def test(self):
#         # Create an entity.
#         entity_id = uuid4()
#         created = ExampleWithReflexiveMutatorDefaultsToBaseClass.Created(originator_id=entity_id, a=1, b=2)
#         entity = ExampleWithReflexiveMutatorDefaultsToBaseClass._mutate(event=created)
#         self.assertIsInstance(entity, ExampleWithReflexiveMutatorDefaultsToBaseClass)
#         self.assertEqual(entity.id, entity_id)
#         self.assertEqual(entity.a, 1)
#         self.assertEqual(entity.b, 2)
#
#         # Check the attribute changed event can be applied.
#         entity.a = 3
#         self.assertEqual(entity.a, 3)
#
#         # Check the discarded event can be applied.
#         entity.discard()
#         with self.assertRaises(EntityIsDiscarded):
#             entity.a = 4
#
#
# class TestWithReflexiveMutatorCallsEventMethod(TestCase):
#     def test(self):
#         # Create an entity.
#         entity_id = uuid4()
#         created = ExampleWithReflexiveMutator.Created(
#             originator_id=entity_id,
#             originator_topic=get_topic(ExampleWithReflexiveMutator),
#             a=1, b=2,
#         )
#         entity = ExampleWithReflexiveMutator._mutate(initial=None, event=created)
#         self.assertIsInstance(entity, ExampleWithReflexiveMutator)
#         self.assertEqual(entity.id, entity_id)
#         self.assertEqual(entity.a, 1)
#         self.assertEqual(entity.b, 2)
#
#         # Check the attribute changed event can be applied.
#         entity.a = 3
#         self.assertEqual(entity.a, 3)
#
#         # Check the discarded event can be applied.
#         entity.discard()
#         with self.assertRaises(EntityIsDiscarded):
#             entity.a = 4
