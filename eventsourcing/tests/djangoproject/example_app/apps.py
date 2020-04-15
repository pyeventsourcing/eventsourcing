from __future__ import annotations

from eventsourcing.infrastructure.django.apps import StandaloneEventSourcingAppConfig


class ExampleAppConfig(StandaloneEventSourcingAppConfig):
    name = "example_app"
    label = "example_app"
    verbose_name = "Example Application"
