from unittest.case import TestCase

from eventsourcing.domain.model.decorators import mutator, retry


class TestDecorators(TestCase):

    def test_retry_without_arg(self):
        def func(*args):
            """func docstring"""
            return 1

        def func_raises(exc=Exception):
            """func_raises docstring"""
            raise exc

        # Check docstrings of decorated functions.
        self.assertEqual(retry(func).__doc__, func.__doc__)
        self.assertEqual(retry()(func).__doc__, func.__doc__)
        self.assertEqual(retry(func_raises).__doc__, func_raises.__doc__)
        self.assertEqual(retry()(func_raises).__doc__, func_raises.__doc__)

        # Check func returns correctly after it is decorated.
        self.assertEqual(retry(func)(), 1)
        self.assertEqual(retry()(func)(), 1)

        # Check func raises correctly after it is decorated.
        with self.assertRaises(Exception):
            retry(func_raises, wait=0)()
        with self.assertRaises(Exception):
            retry(wait=0)(func_raises)()

        with self.assertRaises(NotImplementedError):
            retry(func_raises, wait=0)(NotImplementedError)
        with self.assertRaises(NotImplementedError):
            retry(wait=0)(func_raises)(NotImplementedError)

        with self.assertRaises(NotImplementedError):
            retry(func_raises, wait=0, max_retries=0)(NotImplementedError)
        with self.assertRaises(NotImplementedError):
            retry(wait=0, max_retries=0)(func_raises)(NotImplementedError)

        # Check TypeError is raised if args have incorrect values.
        with self.assertRaises(TypeError):
            retry(max_retries='')  # needs to be an int

        with self.assertRaises(TypeError):
            retry(exc=TestCase)  # need to be subclass of Exception

        with self.assertRaises(TypeError):
            retry(wait='')  # needs to be a float


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
