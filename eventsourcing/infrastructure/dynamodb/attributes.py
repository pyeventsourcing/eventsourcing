import json
from uuid import UUID

from pynamodb.attributes import Attribute
from pynamodb.constants import DEFAULT_ENCODING, NUMBER, STRING


class UUIDAttribute(Attribute):
    """
    A UUID attribute
    """
    attr_type = STRING

    def serialize(self, value):
        """
        Returns a UUID in string format (with dashes)
        """
        if value is None:
            return None
        return str(value)  # value.hex doesn't give dashes, str does

    def deserialize(self, value):
        """
        Returns a UUID
        """
        if not isinstance(value, str):
            return None
        try:
            return UUID(value)
        except ValueError:
            return None


class BytesAttribute(Attribute):
    """
    A bytes attribute - needs to be converted to string for saving in DynamoDB
    """
    attr_type = STRING

    def serialize(self, value):
        """
        Returns a string
        """
        if value is None:
            return None
        elif isinstance(value, bytes):
            return value.decode(DEFAULT_ENCODING)
        else:
            return str(value)

    def deserialize(self, value):
        """
        Returns a byte string
        """
        if value is None:
            return None
        elif isinstance(value, str):
            return value.encode(DEFAULT_ENCODING)
        else:
            return bytes(value)


class DecimalAttribute(Attribute):
    """
    A decimal attribute
    """
    attr_type = NUMBER

    def serialize(self, value):
        """
        Encode decimals as JSON
        """
        if value is None:
            return
        return json.dumps(float(value))

    def deserialize(self, value):
        """
        Decode decimals from JSON
        """
        if value is None:
            return
        return json.loads(value)
