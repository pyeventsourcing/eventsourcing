# coding=utf-8
from __future__ import unicode_literals

import traceback
import uuid
from multiprocessing.pool import Pool
from unittest.case import TestCase

from eventsourcing.contrib.suffixtrees.application import SuffixTreeApplicationWithPythonObjects, \
    SuffixTreeApplicationWithCassandra, AbstractSuffixTreeApplication
from eventsourcing.contrib.suffixtrees.domain.model.generalizedsuffixtree import GeneralizedSuffixTree, \
    STRING_ID_END
from eventsourcing.tests.suffix_tree_text import LONG_TEXT, LONG_TEXT_CONT
from eventsourcing.tests.test_stored_event_repository_cassandra import CassandraTestCase


class TestGeneralizedSuffixTree(TestCase):

    def setUp(self):
        super(TestGeneralizedSuffixTree, self).setUp()
        self.app = SuffixTreeApplicationWithPythonObjects()

    def tearDown(self):
        self.app.close()
        super(TestGeneralizedSuffixTree, self).tearDown()

    def test_empty_string(self):
        st = self.app.register_new_suffix_tree()
        assert isinstance(st, GeneralizedSuffixTree)
        st.add_string('', '1')
        self.assertEqual(self.app.find_substring_edge('not there', st.id), (None, None))
        self.assertEqual(self.app.find_substring_edge('', st.id), (None, None))
        self.assertFalse(self.app.has_substring('not there', st.id))
        self.assertFalse(self.app.has_substring('', st.id))

    def test_repeated_string(self):
        st = self.app.register_new_suffix_tree()
        st.add_string("aaa", '1')
        edge, ln = self.app.find_substring_edge('a', st.id)
        self.assertEqual(edge.label, 'a')
        edge, ln = self.app.find_substring_edge('aa', st.id)
        self.assertEqual(edge.label, 'a')
        edge, ln = self.app.find_substring_edge('aaa', st.id)
        self.assertEqual(edge.label, 'a1' + STRING_ID_END)
        edge, ln = self.app.find_substring_edge('b', st.id)
        self.assertEqual(edge, None)
        self.assertTrue(self.app.has_substring('a', st.id))
        self.assertTrue(self.app.has_substring('aa', st.id))
        self.assertTrue(self.app.has_substring('aaa', st.id))
        self.assertFalse(self.app.has_substring('aaaa', st.id))
        self.assertFalse(self.app.has_substring('b', st.id))
        # case sensitive by default
        self.assertFalse(self.app.has_substring('A', st.id))

    def test_mississippi(self):
        st = self.app.register_new_suffix_tree()
        st.add_string("mississippi", "$")
        st.add_string("mudpie", "#")
        st.add_string("ball", "%")
        st.add_string("ball", "&")

        # Check there isn't an 'a'.
        self.assertEqual(self.app.find_substring_edge('j', st.id), (None, None))

        # Check 'm'.
        edge, ln = self.app.find_substring_edge('m', st.id)
        self.assertEqual(edge.label, 'm')

        # Check 'missi'.
        edge, ln = self.app.find_substring_edge('missi', st.id)
        self.assertEqual(edge.label, 'ississippi$' + STRING_ID_END)

        # Check 'issi'.
        edge, ln = self.app.find_substring_edge('issi', st.id)
        self.assertEqual(edge.label, 'ssi')

        # Check 'is'.
        edge, ln = self.app.find_substring_edge('is', st.id)
        self.assertEqual(edge.label, 'ssi')

        # Check 'si'.
        edge, ln = self.app.find_substring_edge('si', st.id)
        self.assertEqual(edge.label, 'i')

        # Check 'issip'.
        edge, ln = self.app.find_substring_edge('issip', st.id)
        self.assertEqual(edge.label, 'ppi$' + STRING_ID_END)

        # Check 'ssip'.
        edge, ln = self.app.find_substring_edge('ssip', st.id)
        self.assertEqual(edge.label, 'ppi$' + STRING_ID_END)

        # Check 'sip'.
        edge, ln = self.app.find_substring_edge('sip', st.id)
        self.assertEqual(edge.label, 'ppi$' + STRING_ID_END)

        # Check 'ip'.
        edge, ln = self.app.find_substring_edge('ip', st.id)
        self.assertEqual(edge.label, 'ppi$' + STRING_ID_END)

        # Check 'i'.
        edge, ln = self.app.find_substring_edge('i', st.id)
        self.assertEqual(edge.label, 'i')

        # Check 'ippi'.
        edge, ln = self.app.find_substring_edge('ippi', st.id)
        self.assertEqual(edge.label, 'ppi$' + STRING_ID_END)

        # Check 'mudpie'.
        edge, ln = self.app.find_substring_edge('mudpie', st.id)
        self.assertEqual(edge.label, 'udpie#' + STRING_ID_END)

        # Check 'ball'.
        edge, ln = self.app.find_substring_edge('ball', st.id)
        self.assertEqual(edge.label, 'ball')
        edge, ln = self.app.find_substring_edge('ball%', st.id)
        self.assertEqual(edge.label, '%' + STRING_ID_END)
        edge, ln = self.app.find_substring_edge('ball&', st.id)
        self.assertEqual(edge.label, '&' + STRING_ID_END)

    def test_colours(self):
        st = self.app.register_new_suffix_tree()
        st.add_string("blue", "$")
        st.add_string("red", "#")

        # Check 'b'.
        edge, ln = self.app.find_substring_edge('b', st.id)
        self.assertEqual(edge.label, 'blue$' + STRING_ID_END)

        # Check 'l'.
        edge, ln = self.app.find_substring_edge('l', st.id)
        self.assertEqual(edge.label, 'lue$' + STRING_ID_END)

        # Check 'u'.
        edge, ln = self.app.find_substring_edge('u', st.id)
        self.assertEqual(edge.label, 'ue$' + STRING_ID_END)

        # Check 'e'.
        edge, ln = self.app.find_substring_edge('e', st.id)
        self.assertEqual(edge.label, 'e')

        # Check 'ue'.
        edge, ln = self.app.find_substring_edge('ue', st.id)
        self.assertEqual(edge.label, 'ue$' + STRING_ID_END)

        # Check 'lue'.
        edge, ln = self.app.find_substring_edge('lue', st.id)
        self.assertEqual(edge.label, 'lue$' + STRING_ID_END)

        # Check 'blue'.
        edge, ln = self.app.find_substring_edge('blue', st.id)
        self.assertEqual(edge.label, 'blue$' + STRING_ID_END)

        # Check 're'.
        edge, ln = self.app.find_substring_edge('re', st.id)
        self.assertEqual(edge.label, 'red#' + STRING_ID_END)

        # Check 'ed'.
        edge, ln = self.app.find_substring_edge('ed', st.id)
        self.assertEqual(edge.label, 'd#' + STRING_ID_END)

        # Check 'red'.
        edge, ln = self.app.find_substring_edge('red', st.id)
        self.assertEqual(edge.label, 'red#' + STRING_ID_END)

    def test_find_string_ids(self):
        # This test is the first to involve the children of nodes.
        st = self.app.register_new_suffix_tree()
        string1_id = uuid.uuid4().hex
        string2_id = uuid.uuid4().hex
        string3_id = uuid.uuid4().hex
        string4_id = uuid.uuid4().hex
        st.add_string("blue", string_id=string1_id)
        st.add_string("red", string_id=string2_id)
        st.add_string("blues", string_id=string3_id)
        # st.add_string("ssblu", string_id=string4_id)

        strings = self.app.find_string_ids('$', st.id)
        assert not strings, strings
        strings = self.app.find_string_ids('0', st.id)
        assert not strings, strings
        strings = self.app.find_string_ids('1', st.id)
        assert not strings, strings
        strings = self.app.find_string_ids('2', st.id)
        assert not strings, strings
        strings = self.app.find_string_ids('3', st.id)
        assert not strings, strings
        strings = self.app.find_string_ids('4', st.id)
        assert not strings, strings
        strings = self.app.find_string_ids('5', st.id)
        assert not strings, strings
        strings = self.app.find_string_ids('6', st.id)
        assert not strings, strings
        strings = self.app.find_string_ids('7', st.id)
        assert not strings, strings

        # Find 'b'.
        strings = self.app.find_string_ids('b', st.id)
        self.assertIn(string1_id, strings)
        self.assertNotIn(string2_id, strings)

        # Find 'e'.
        strings = self.app.find_string_ids('e', st.id)
        self.assertEqual(len(strings), 3)
        self.assertIn(string1_id, strings, (string1_id, string2_id, string3_id, strings))
        self.assertIn(string2_id, strings, (string1_id, string2_id, string3_id, strings))
        self.assertIn(string3_id, strings, (string1_id, string2_id, string3_id, strings))

        # Find 'e' - limit 1.
        strings = self.app.find_string_ids('e', st.id, limit=1)
        self.assertEqual(len(strings), 1)

        # Find 'e' - limit 2.
        strings = self.app.find_string_ids('e', st.id, limit=2)
        self.assertEqual(len(strings), 2)

        # Find 'r'.
        strings = self.app.find_string_ids('r', st.id)
        self.assertNotIn(string1_id, strings)
        self.assertIn(string2_id, strings)

        # Find 'd'.
        strings = self.app.find_string_ids('d', st.id)
        self.assertNotIn(string1_id, strings)
        self.assertIn(string2_id, strings)

        # Find 's'.
        strings = self.app.find_string_ids('s', st.id)
        self.assertNotIn(string1_id, strings)
        self.assertNotIn(string2_id, strings)
        self.assertIn(string3_id, strings)

    def test_add_string_to_suffixtree_from_repo(self):
        # Check adding strings after getting the tree from the repo.
        st = self.app.register_new_suffix_tree()

        st = self.app.get_suffix_tree(st.id)
        st.add_string('blue', '1')

        st = self.app.get_suffix_tree(st.id)
        st.add_string('green', '2')

        st = self.app.get_suffix_tree(st.id)
        st.add_string('yellow', '3')

        st = self.app.get_suffix_tree(st.id)
        strings_ids = self.app.find_string_ids('e', st.id)
        self.assertEqual(3, len(strings_ids), strings_ids)
        self.assertEqual(['1', '2', '3'], sorted(strings_ids))

    def test_remove_string_from_suffixtree(self):
        st = self.app.register_new_suffix_tree()
        st.add_string('blue', '1')
        st.add_string('green', '2')

        strings_ids = self.app.find_string_ids('b', st.id)
        self.assertEqual(1, len(strings_ids))

        strings_ids = self.app.find_string_ids('l', st.id)
        self.assertEqual(1, len(strings_ids))

        strings_ids = self.app.find_string_ids('u', st.id)
        self.assertEqual(1, len(strings_ids))

        strings_ids = self.app.find_string_ids('r', st.id)
        self.assertEqual(1, len(strings_ids))

        strings_ids = self.app.find_string_ids('g', st.id)
        self.assertEqual(1, len(strings_ids))

        strings_ids = self.app.find_string_ids('e', st.id)
        self.assertEqual(2, len(strings_ids))

        st.remove_string('blue', '1')

        strings_ids = self.app.find_string_ids('b', st.id)
        self.assertEqual(0, len(strings_ids))

        strings_ids = self.app.find_string_ids('l', st.id)
        self.assertEqual(0, len(strings_ids))

        strings_ids = self.app.find_string_ids('u', st.id)
        self.assertEqual(0, len(strings_ids))

        strings_ids = self.app.find_string_ids('r', st.id)
        self.assertEqual(1, len(strings_ids))

        strings_ids = self.app.find_string_ids('g', st.id)
        self.assertEqual(1, len(strings_ids))

        strings_ids = self.app.find_string_ids('e', st.id)
        self.assertEqual(1, len(strings_ids))

        st.add_string('blue', '1')

        strings_ids = self.app.find_string_ids('b', st.id)
        self.assertEqual(1, len(strings_ids))

        strings_ids = self.app.find_string_ids('l', st.id)
        self.assertEqual(1, len(strings_ids))

        strings_ids = self.app.find_string_ids('u', st.id)
        self.assertEqual(1, len(strings_ids))

        strings_ids = self.app.find_string_ids('r', st.id)
        self.assertEqual(1, len(strings_ids))

        strings_ids = self.app.find_string_ids('g', st.id)
        self.assertEqual(1, len(strings_ids))

        strings_ids = self.app.find_string_ids('e', st.id)
        self.assertEqual(2, len(strings_ids))

    def test_long_string(self):
        st = self.app.register_new_suffix_tree()
        st.add_string(LONG_TEXT[:12000], '1')
        self.assertEqual(self.app.find_string_ids('Ukkonen', st.id), {'1'})
        self.assertEqual(self.app.find_string_ids('Optimal', st.id), {'1'})
        self.assertFalse(self.app.find_string_ids('ukkonen', st.id))
        st.add_string(LONG_TEXT_CONT[:1000], '2')
        self.assertEqual(self.app.find_string_ids('Burrows-Wheeler', st.id), {'2'})
        self.assertEqual(self.app.find_string_ids('suffix', st.id), {'1', '2'})

    def test_split_long_string(self):
        # Split the long string into separate strings, and make some IDs.
        list_of_strings = [w for w in LONG_TEXT[:1000].split(' ') if w]
        string_ids = {}
        for string in list_of_strings:
            string_id = uuid.uuid4().hex
            string_ids[string_id] = string

        # Build the suffix tree.
        st = self.app.register_new_suffix_tree()
        for string_id, string in string_ids.items():
            st.add_string(string, string_id)

        # Check the suffix tree.
        for string_id, string in string_ids.items():
            self.assertIn(string_id, self.app.find_string_ids(string, st.id))

        # Build the suffix tree.
        #  - this time, get the suffix tree afresh from the repo each time
        st = self.app.register_new_suffix_tree()
        for string_id, string in string_ids.items():
            st = self.app.get_suffix_tree(st.id)
            st.add_string(string, string_id)

        # Check the suffix tree.
        for string_id, string in string_ids.items():
            self.assertIn(string_id, self.app.find_string_ids(string, st.id))

    def test_case_insensitivity(self):
        st = self.app.register_new_suffix_tree(case_insensitive=True)
        st.add_string(LONG_TEXT[:12000], '1')
        self.assertEqual(self.app.find_string_ids('ukkonen', st.id), {'1'})
        self.assertEqual(self.app.find_string_ids('Optimal', st.id), {'1'})
        self.assertEqual(self.app.find_string_ids('burrows-wheeler', st.id), set())
        st.add_string(LONG_TEXT_CONT[:1000], '2')
        self.assertEqual(self.app.find_string_ids('ukkonen', st.id), {'1'})
        self.assertEqual(self.app.find_string_ids('Optimal', st.id), {'1'})
        self.assertEqual(self.app.find_string_ids('burrows-wheeler', st.id), {'2'})


class TestMultiprocessingWithGeneralizedSuffixTree(CassandraTestCase):

    def setUp(self):
        super(TestMultiprocessingWithGeneralizedSuffixTree, self).setUp()

    def tearDown(self):
        super(TestMultiprocessingWithGeneralizedSuffixTree, self).tearDown()
        if self.app is not None:
            self.app.close()

    def test(self):
        # Split the long string into separate strings, and make some IDs.
        list_of_args = [w for w in LONG_TEXT[:100].split(' ') if w]
        string_ids = {}
        for string in list_of_args:
            string_id = uuid.uuid4().hex
            string_ids[string_id] = string

        # Create a new suffix tree.
        self.app = SuffixTreeApplicationWithCassandra()
        st = self.app.register_new_suffix_tree()
        assert st.id in self.app.suffix_tree_repo

        # Close the app, so the pool doesn't inherit it.
        self.app.close()

        # Start the pool.
        pool = Pool(initializer=pool_initializer, processes=1)

        list_of_args = [[s, sid, st.id] for sid, s in string_ids.items() if s]
        results = pool.map(add_string_to_suffix_tree, list_of_args)
        for result in results:
            if isinstance(result, Exception):
                print(result.args[0][1])
                raise result

        # Creat the app again.
        self.app = SuffixTreeApplicationWithCassandra()

        # Check the suffix tree.
        for string_id, string in string_ids.items():
            results = self.app.find_string_ids(string, st.id)
            self.assertIn(string_id, results, (string, string_id))

        # string_ids = self.app.find_string_ids('computer', suffix_tree.id)
        # self.assertEqual(sorted(string_ids), ['1'])
        # # string_ids = self.app.find_string_ids('Ukkonen', suffix_tree.id)
        # # self.assertEqual(sorted(string_ids), ['1'])
        # string_ids = self.app.find_string_ids('ba', suffix_tree.id)
        # self.assertEqual(sorted(string_ids), ['2'])
        # # string_ids = self.app.find_string_ids('konen', suffix_tree.id)
        # # self.assertEqual(sorted(string_ids), ['1'])
        # string_ids = self.app.find_string_ids('o', suffix_tree.id)
        # self.assertEqual(sorted(string_ids), ['1'])
        # string_ids = self.app.find_string_ids('a', suffix_tree.id)
        # self.assertEqual(sorted(string_ids), ['1', '2'])
        # string_ids = self.app.find_string_ids('n', suffix_tree.id)
        # self.assertEqual(sorted(string_ids), ['1', '2'])
        # # self.assertEqual(sorted(string_ids), ['1', '2', '3'])


worker_app = None


def pool_initializer():
    global worker_app
    worker_app = SuffixTreeApplicationWithCassandra()


def add_string_to_suffix_tree(args):
    # random.seed()
    string, string_id, suffix_tree_id = args
    try:
        assert isinstance(worker_app, AbstractSuffixTreeApplication)
        suffix_tree = worker_app.get_suffix_tree(suffix_tree_id)
        assert isinstance(suffix_tree, GeneralizedSuffixTree)
        suffix_tree.add_string(string, string_id)
    except Exception as e:
        msg = traceback.format_exc()
        return Exception((e, msg, string, string_id))
    return string_id


if __name__ == "__main__":
    pass
