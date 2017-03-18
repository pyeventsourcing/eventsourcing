from eventsourcing.domain.model.events import subscribe


def subscribe_to(event_class):
    """ Decorator for making a custom event handler function subscribe to a certain event type
    Args:
        event_class: DomainEvent class or its child classes that the handler function should subscribe to

    Example usage:
        # this example shows a custom handler that reacts to Todo.Created
        # event and saves a projection of a Todo model object
        @subscribe_to(Todo.Created)
        def new_todo_projection(event):
            todo = TodoProjection(id=event.entity_id, title=event.title)
            todo.save()
    """

    def event_type_predicate(event):
        return isinstance(event, event_class)

    def wrap(handler_func):
        subscribe(event_type_predicate, handler_func)
        return handler_func

    return wrap
