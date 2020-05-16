from unittest import skip

from eventsourcing.application.django import DjangoApplication
from eventsourcing.tests.sequenced_item_tests.test_django_record_manager import (
    DjangoTestCase,
)
from eventsourcing.tests.test_ray_runner import TestRayRunner


@skip("This doesn't work at the moment (same forking/setup problem?)")
class DontTestRayRunnerWithDjango(DjangoTestCase, TestRayRunner):
    infrastructure_class = DjangoApplication


# Don't let this be found here.
del TestRayRunner
