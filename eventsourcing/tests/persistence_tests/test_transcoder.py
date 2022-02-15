from unittest import skip

from eventsourcing.persistence import JSONTranscoder, UUIDAsHex
from eventsourcing.tests.persistence import (
    CustomType1AsDict,
    CustomType2AsDict,
    TranscoderTestCase,
)


class TestJSONTranscoder(TranscoderTestCase):
    def construct_transcoder(self):
        transcoder = JSONTranscoder()
        transcoder.register(CustomType1AsDict())
        transcoder.register(CustomType2AsDict())
        transcoder.register(UUIDAsHex())
        return transcoder

    @skip("test_tuple(): JSONTranscoder converts tuples to lists")
    def test_tuple(self):
        pass

    @skip("test_mixed(): JSONTranscoder converts tuples to lists")
    def test_mixed(self):
        pass

    @skip("test_dict_subclass(): JSONTranscoder converts dict subclasses to dict")
    def test_dict_subclass(self):
        pass

    @skip("test_list_subclass(): JSONTranscoder converts list subclasses to list")
    def test_list_subclass(self):
        pass

    @skip("test_str_subclass(): JSONTranscoder converts str subclasses to str")
    def test_str_subclass(self):
        pass

    @skip("test_int_subclass(): JSONTranscoder converts int subclasses to int")
    def test_int_subclass(self):
        pass


del TranscoderTestCase
