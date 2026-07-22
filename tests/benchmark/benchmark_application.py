from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from eventsourcing.pydantic import AggregatesApplication

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture


@pytest.mark.benchmark(group="construct-application")
def test_construct_application(benchmark: BenchmarkFixture) -> None:
    benchmark(AggregatesApplication)
