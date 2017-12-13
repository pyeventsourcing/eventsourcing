from unittest import TestCase, skipIf
from uuid import uuid4

import sqlite3

from decimal import Decimal

import six


# This doesn't work with Python 2.7, which returns only 2 decimal
# places. Django seems to work though, somehow, to get 6 places.
@skipIf(six.PY2, "Skipping sqlite3 decimal field test on Python 2.7")
class Test(TestCase):
    """
    This test case demonstrates that sqlite3 truncates decimal places
    before the value of a decimal field is given to the converter,
    when a decimal converter is registered, otherwise it returns a
    float with full precision. Seems a little odd to give the converter
    less than is returns without a converter?
    """
    def test(self):

        # Set up sqlite3 table with decimal column.
        conn = sqlite3.connect(':memory:', detect_types=1)
        c = conn.cursor()
        c.execute("""
CREATE TABLE t (
        id BINARY(16) NOT NULL,
        position DECIMAL(24,8) NOT NULL,
        PRIMARY KEY (id)
);
""")
        # Insert a float with 8 decimal places.
        f = 1234567891.12345678
        sql = 'INSERT INTO t VALUES ("{}", "{}")'.format(uuid4().hex, f)
        c.execute(sql)
        conn.commit()

        # Get the value and check it's the same.
        c.execute("SELECT position from t")
        r = c.fetchone()
        position = r[0]
        # self.assertEqual(f, position)

        # Now, register a decimal converter with sqlite3.
        sqlite3.register_converter("decimal", lambda s: Decimal(s.decode()))

        # Then, the value which seems to be in the database loses precision!
        c.execute("SELECT position from t")
        r = c.fetchone()
        position = r[0]
        self.assertEqual(Decimal('1234567891.12346'), position)
