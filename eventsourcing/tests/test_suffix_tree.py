# coding=utf-8
from __future__ import unicode_literals

import os
import unittest

from eventsourcing.contrib.suffixtrees.domain.model.suffixtree import register_new_suffix_tree, SuffixTree,\
    SuffixTreeApplication
from eventsourcing.tests.unit_test_fixtures_suffix_tree_text import LONG_TEXT

LONG_TEXT_FIXTURE_PATH = os.path.join(os.path.dirname(__file__), 'test_suffix_tree.txt')


class SuffixTreeTest(unittest.TestCase):

    def setUp(self):
        self.app = SuffixTreeApplication()

    def tearDown(self):
        self.app.close()

    def test_empty_string(self):
        st = register_new_suffix_tree()
        assert isinstance(st, SuffixTree)
        st.add_string('')
        self.assertEqual(self.app.find_substring('not there', st.id), -1)
        self.assertEqual(self.app.find_substring('', st.id), -1)
        self.assertFalse(self.app.has_substring('not there', st.id))
        self.assertFalse(self.app.has_substring('', st.id))

    def test_repeated_string(self):
        st = register_new_suffix_tree()
        st.add_string("aaa")
        self.assertEqual(self.app.find_substring('a', st.id), 0)
        self.assertEqual(self.app.find_substring('aa', st.id), 0)
        self.assertEqual(self.app.find_substring('aaa', st.id), 0)
        self.assertEqual(self.app.find_substring('b', st.id), -1)
        self.assertTrue(self.app.has_substring('a', st.id))
        self.assertTrue(self.app.has_substring('aa', st.id))
        self.assertTrue(self.app.has_substring('aaa', st.id))
        self.assertFalse(self.app.has_substring('aaaa', st.id))
        self.assertFalse(self.app.has_substring('b', st.id))
        # case sensitive by default
        self.assertFalse(self.app.has_substring('A', st.id))

    def test_mississippi(self):
        st = register_new_suffix_tree()
        st.add_string("mississippi")
        self.assertEqual(self.app.find_substring('a', st.id), -1)
        self.assertEqual(self.app.find_substring('m', st.id), 0)
        self.assertEqual(self.app.find_substring('i', st.id), 1)

    def test_long_string(self):
        st = register_new_suffix_tree()
        st.add_string(LONG_TEXT)
        self.assertEqual(self.app.find_substring('Ukkonen', st.id), 1498)
        self.assertEqual(self.app.find_substring('Optimal', st.id), 11074)
        self.assertFalse(self.app.has_substring('ukkonen', st.id))

    def test_case_insensitivity(self):
        st = register_new_suffix_tree(case_insensitive=True)
        st.add_string(LONG_TEXT)
        self.assertEqual(self.app.find_substring('ukkonen', st.id), 1498)
        self.assertEqual(self.app.find_substring('Optimal', st.id), 1830)
