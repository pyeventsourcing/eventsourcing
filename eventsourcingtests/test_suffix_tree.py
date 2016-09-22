# coding=utf-8

import os
import unittest

from eventsourcing.domain.model.suffixtree import register_new_suffix_tree


LONG_TEXT_FIXTURE_PATH = os.path.join(os.path.dirname(__file__), 'test_suffix_tree.txt')


class SuffixTreeTest(unittest.TestCase):
    """Some functional tests.
    """

    def test_empty_string(self):
        st = register_new_suffix_tree('')
        self.assertEqual(st.find_substring('not there'), -1)
        self.assertEqual(st.find_substring(''), -1)
        self.assertFalse(st.has_substring('not there'))
        self.assertFalse(st.has_substring(''))

    def test_repeated_string(self):
        st = register_new_suffix_tree("aaa")
        self.assertEqual(st.find_substring('a'), 0)
        self.assertEqual(st.find_substring('aa'), 0)
        self.assertEqual(st.find_substring('aaa'), 0)
        self.assertEqual(st.find_substring('b'), -1)
        self.assertTrue(st.has_substring('a'))
        self.assertTrue(st.has_substring('aa'))
        self.assertTrue(st.has_substring('aaa'))
        self.assertFalse(st.has_substring('aaaa'))
        self.assertFalse(st.has_substring('b'))
        # case sensitive by default
        self.assertFalse(st.has_substring('A'))

    def test_long_string(self):
        f = open(LONG_TEXT_FIXTURE_PATH)
        st = register_new_suffix_tree(f.read())
        self.assertEqual(st.find_substring('Ukkonen'), 1498)
        self.assertEqual(st.find_substring('Optimal'), 11074)
        self.assertFalse(st.has_substring('ukkonen'))

    def test_case_sensitivity(self):
        f = open(LONG_TEXT_FIXTURE_PATH)
        st = register_new_suffix_tree(f.read(), case_insensitive=True)
        self.assertEqual(st.find_substring('ukkonen'), 1498)
        self.assertEqual(st.find_substring('Optimal'), 1830)
