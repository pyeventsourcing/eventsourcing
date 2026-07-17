from unittest import skip

from eventsourcing.dataclasses.legacy import LegacyJSONTranscoder, UUIDAsHex
from eventsourcing.persistence import Transcoder
from eventsourcing.tests.persistence import (
    CustomType1AsDict,
    CustomType2AsDict,
    TranscoderTestCase,
)


class TestJSONTranscoder(TranscoderTestCase):
    def construct_transcoder(self) -> Transcoder:
        transcoder = LegacyJSONTranscoder()
        transcoder.register(CustomType1AsDict())
        transcoder.register(CustomType2AsDict())
        transcoder.register(UUIDAsHex())
        return transcoder

    @skip("test_tuple(): JSONTranscoder converts tuples to lists")
    def test_tuple(self) -> None:
        pass

    @skip("test_mixed(): JSONTranscoder converts tuples to lists")
    def test_mixed(self) -> None:
        pass

    @skip("test_dict_subclass(): JSONTranscoder converts dict subclasses to dict")
    def test_dict_subclass(self) -> None:
        pass

    @skip("test_list_subclass(): JSONTranscoder converts list subclasses to list")
    def test_list_subclass(self) -> None:
        pass

    @skip("test_str_subclass(): JSONTranscoder converts str subclasses to str")
    def test_str_subclass(self) -> None:
        pass

    @skip("test_int_subclass(): JSONTranscoder converts int subclasses to int")
    def test_int_subclass(self) -> None:
        pass


del TranscoderTestCase
