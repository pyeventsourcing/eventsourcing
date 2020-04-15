from typing import ClassVar

from django.apps import AppConfig
from django.contrib import admin
from django.core.exceptions import ImproperlyConfigured

__all__ = (
    "EventSourcingAppConfig",
    "StandaloneEventSourcingAppConfig",
)


class StandaloneEventSourcingAppConfig(AppConfig):
    """Base event sourced Django application config that provides independent
    infrastructure (database tables) for specific event sourced applications."""

    label: ClassVar[str]
    name: ClassVar[str]
    verbose_name: ClassVar[str]

    def __init__(self, app_name, app_module):
        for attr in ("label", "name", "verbose_name"):
            if not hasattr(self, attr):
                raise ImproperlyConfigured(f"Please provide {attr} class attribute")

        super().__init__(app_name, app_module)

    def ready(self):
        from eventsourcing.infrastructure.django.models import ABSTRACT_MODELS

        for abstract_class in ABSTRACT_MODELS:
            concrete_class_name = abstract_class.__name__.lstrip("Abstract")
            self._create_model(
                abstract_class=abstract_class,
                name=concrete_class_name,
                app_label=self.label,
                module=self.module.__package__,
            )

    @staticmethod
    def _create_model(
        abstract_class,
        name,
        fields=None,
        app_label="",
        module="",
        options=None,
        admin_opts=None,
    ):
        # Using type('Meta', ...) gives a dictproxy error during model creation
        class Meta(abstract_class.Meta):
            pass

        # app_label must be set using the Meta inner class
        if app_label:
            setattr(Meta, "app_label", app_label)

        # Update Meta with any options that were provided
        if options is not None:
            for key, value in options.items():
                setattr(Meta, key, value)

        # Set up a dictionary to simulate declarations within a class
        attrs = {"__module__": module, "Meta": Meta}

        # Add in any fields that were provided
        if fields:
            attrs.update(fields)

        # Create the class, which automatically triggers ModelBase processing
        model = type(name, (abstract_class,), attrs)

        # Create an Admin class if admin options were provided
        if admin_opts is not None:

            class Admin(admin.ModelAdmin):
                pass

            for key, value in admin_opts:
                setattr(Admin, key, value)
            admin.site.register(model, Admin)

        return model


class EventSourcingAppConfig(StandaloneEventSourcingAppConfig):
    """Base event sourced Django application config that use shared infrastructure
    (database tables) for all event sourced applications."""

    label = "eventsourcing"
    name = "eventsourcing.infrastructure.django"
    verbose_name = "Event Sourcing"
