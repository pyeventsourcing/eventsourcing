from unittest.case import TestCase

from eventsourcing.domain.model.decorators import mutator


class TestDecorators(TestCase):

    def test_mutate_without_arg(self):
        # Define an entity class, and event class, and a mutator function.

        class Entity(object): pass

        class Event(object): pass

        @mutator
        def mutate_entity(initial, event):
            """Docstring for function mutate()."""
            raise NotImplementedError()

        # Check the function looks like the original.
        self.assertEqual(mutate_entity.__doc__, "Docstring for function mutate().")

        # Check it is capable of registering event handlers.
        @mutate_entity.register(Event)
        def mutate_with_event(initial, event):
            return Entity()

        # Check it dispatches on type of last arg.
        self.assertIsInstance(mutate_entity(None, Event()), Entity)

        # Check it handles unregistered types.
        with self.assertRaises(NotImplementedError):
            mutate_entity(None, None)

    def test_mutate_with_arg(self):
        # Define an entity class, and event class, and a mutator function.

        class Entity(object): pass

        class Event(object): pass

        @mutator(Entity)
        def mutate_entity(initial, event):
            """Docstring for function mutate()."""
            raise NotImplementedError()

        # Check the function looks like the original.
        self.assertEqual(mutate_entity.__doc__, "Docstring for function mutate().")

        # Check it is capable of registering event handlers.
        @mutate_entity.register(Event)
        def mutate_with_event(initial, event):
            return initial()

        # Check it dispatches on type of last arg.
        self.assertIsInstance(mutate_entity(None, Event()), Entity)

        # Check it handles unregistered types.
        with self.assertRaises(NotImplementedError):
            mutate_entity(None, None)
