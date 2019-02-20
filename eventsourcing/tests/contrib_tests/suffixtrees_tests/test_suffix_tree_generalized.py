# # coding=utf-8
# from __future__ import unicode_literals
#
# import datetime
# import traceback
# import uuid
# from multiprocessing.pool import Pool
# from unittest.case import TestCase, skip
#
# from eventsourcing.contrib.suffixtrees.application import SuffixTreeApplication
# from eventsourcing.contrib.suffixtrees.domain.model.generalizedsuffixtree import GeneralizedSuffixTree, \
#     STRING_ID_END, SuffixTreeEdge, SuffixTreeNode
# from eventsourcing.tests.base import notquick
# from eventsourcing.tests.datastore_tests.test_cassandra import CassandraDatastoreTestCase
# from eventsourcing.tests.unit_test_fixtures_suffix_tree_text import LONG_TEXT, LONG_TEXT_CONT
#
#
# class GeneralizedSuffixTreeTestCase(TestCase):
#     def setUp(self):
#         super(GeneralizedSuffixTreeTestCase, self).setUp()
#         self.app = SuffixTreeApplication(
#             stored_event_repository=PythonObjectsStoredEventRepository()
#         )
#
#     def tearDown(self):
#         self.app.close()
#         super(GeneralizedSuffixTreeTestCase, self).tearDown()
#
#     def add_string_to_suffix_tree(self, string, string_id, suffix_tree):
#         print("Adding string to suffix tree: {}".format(repr(string[:100])))
#         started = datetime.datetime.now()
#         suffix_tree.add_string(string, string_id=string_id)
#         print(" - added string in: {}".format(datetime.datetime.now() - started))
#
#
# @skip
# @notquick
# class TestGeneralizedSuffixTreeFast(GeneralizedSuffixTreeTestCase):
#     def test_empty_string(self):
#         st = self.app.register_new_suffix_tree()
#         assert isinstance(st, GeneralizedSuffixTree)
#         self.add_string_to_suffix_tree('', '1', st)
#         self.assertEqual(self.app.find_substring_edge('not there', st.id), (None, None))
#         self.assertEqual(self.app.find_substring_edge('', st.id), (None, None))
#         self.assertFalse(self.app.has_substring('not there', st.id))
#         self.assertFalse(self.app.has_substring('', st.id))
#
#     def test_add_prefix_of_previous(self):
#         st = self.app.register_new_suffix_tree()
#         assert isinstance(st, GeneralizedSuffixTree)
#         self.add_string_to_suffix_tree('aba', '1', st)
#         self.add_string_to_suffix_tree('a', '2', st)
#
#         # Check the string ID is returned.
#         result_ids = self.app.find_string_ids('a', st.id)
#         self.assertEqual(result_ids, {'1', '2'})
#
#     def test_given_add_duplicate_when_query_with_suffix_then_results_have_both(self):
#         st = self.app.register_new_suffix_tree()
#         assert isinstance(st, GeneralizedSuffixTree)
#         self.add_string_to_suffix_tree('ab', '1', st)
#         self.add_string_to_suffix_tree('ab', '2', st)
#
#         # Check the string ID is returned.
#         result_ids = self.app.find_string_ids('b', st.id)
#         self.assertEqual(result_ids, {'1', '2'})
#
#     def test_extended_copy_of_previous_string(self):
#         st = self.app.register_new_suffix_tree()
#         assert isinstance(st, GeneralizedSuffixTree)
#         self.add_string_to_suffix_tree('a', '1', st)
#         self.add_string_to_suffix_tree('ab', '2', st)
#
#         # Check the common prefix can be found.
#         result_ids = self.app.find_string_ids('a', st.id)
#         self.assertEqual(result_ids, {'1', '2'})
#
#         # Check the string ID is returned.
#         result_ids = self.app.find_string_ids('ab', st.id)
#         self.assertEqual(result_ids, {'2'})
#
#     def test_trucated_copy_of_previous_string(self):
#         st = self.app.register_new_suffix_tree()
#         assert isinstance(st, GeneralizedSuffixTree)
#         self.add_string_to_suffix_tree('1a', '2', st)
#         self.add_string_to_suffix_tree('1ab', '1', st)
#
#         # Check the common prefix can be found.
#         result_ids = self.app.find_string_ids('a', st.id)
#         self.assertEqual(result_ids, {'1', '2'})
#
#         # Check the string ID is returned.
#         result_ids = self.app.find_string_ids('ab', st.id)
#         self.assertEqual(result_ids, {'1'})
#
#         # Check the string ID is returned.
#         result_ids = self.app.find_string_ids('b', st.id)
#         self.assertEqual(result_ids, {'1'})
#
#     def test_extended_copy_of_longer_previous_string(self):
#         st = self.app.register_new_suffix_tree()
#         assert isinstance(st, GeneralizedSuffixTree)
#         self.add_string_to_suffix_tree('ab', '1', st)
#         self.add_string_to_suffix_tree('abc', '2', st)
#
#         # Check the common prefix can be found.
#         result_ids = self.app.find_string_ids('a', st.id)
#         self.assertEqual(result_ids, {'1', '2'})
#
#         # Check the common prefix can be found.
#         result_ids = self.app.find_string_ids('ab', st.id)
#         self.assertEqual(result_ids, {'1', '2'})
#
#         # Check the extention can be found.
#         result_ids = self.app.find_string_ids('c', st.id)
#         self.assertEqual(result_ids, {'2'})
#
#         # Check the extended string can be found.
#         result_ids = self.app.find_string_ids('abc', st.id)
#         self.assertEqual(result_ids, {'2'})
#
#     def test_non_repeating_string(self):
#         st = self.app.register_new_suffix_tree()
#         assert isinstance(st, GeneralizedSuffixTree)
#         string_id = '1'
#         string = 'abc'
#         self.add_string_to_suffix_tree(string, string_id, st)
#
#         # Check various non-substrings aren't in the tree.
#         self.assertEqual(self.app.find_substring_edge('not there', st.id), (None, None))
#         self.assertEqual(self.app.find_substring_edge('', st.id), (None, None))
#         self.assertFalse(self.app.has_substring('not there', st.id))
#         self.assertFalse(self.app.has_substring('', st.id))
#
#         # Check substrings are in the tree.
#         edge, ln = self.app.find_substring_edge('abc', st.id)
#         assert isinstance(edge, SuffixTreeEdge)
#         # self.assertEqual(edge.label, string + STRING_ID_END)
#         # self.assertEqual(edge.label, string + string_id + STRING_ID_END)
#
#         # Check the edge has a node.
#         node = self.app.node_repo[edge.dest_node_id]
#         assert isinstance(node, SuffixTreeNode)
#
#         # Check the node has a string ID.
#         self.assertEqual(node.string_id, string_id)
#
#         # Check the string ID is returned.
#         result_ids = self.app.find_string_ids(string, st.id)
#         self.assertEqual(result_ids, {string_id})
#
#     def test_repeating_string(self):
#         st = self.app.register_new_suffix_tree()
#         self.add_string_to_suffix_tree("aaa", '1', st)
#
#         edge, ln = self.app.find_substring_edge('a', st.id)
#         # self.assertEqual(edge.label, 'a')
#         edge, ln = self.app.find_substring_edge('aa', st.id)
#         # self.assertEqual(edge.label, 'a')
#         edge, ln = self.app.find_substring_edge('aaa', st.id)
#         # self.assertEqual(edge.label, 'a1' + STRING_ID_END)
#         edge, ln = self.app.find_substring_edge('b', st.id)
#         self.assertEqual(edge, None)
#         self.assertTrue(self.app.has_substring('a', st.id))
#         self.assertTrue(self.app.has_substring('aa', st.id))
#         self.assertTrue(self.app.has_substring('aaa', st.id))
#         self.assertFalse(self.app.has_substring('aaaa', st.id))
#         self.assertFalse(self.app.has_substring('b', st.id))
#         # case sensitive by default
#         self.assertFalse(self.app.has_substring('A', st.id))
#
#         # Check ID is returned.
#         self.assertEqual(self.app.find_string_ids('a', st.id), {'1'})
#         self.assertEqual(self.app.find_string_ids('aa', st.id), {'1'})
#         self.assertEqual(self.app.find_string_ids('aaa', st.id), {'1'})
#
#     def test_two_identical_strings(self):
#         st = self.app.register_new_suffix_tree()
#         assert isinstance(st, GeneralizedSuffixTree)
#         string1_id = '1'
#         string1 = 'abc'
#         string2_id = '2'
#         string2 = 'abc'
#         self.add_string_to_suffix_tree(string1, string1_id, st)
#         self.add_string_to_suffix_tree(string2, string2_id, st)
#
#         # Check various non-substrings aren't in the tree.
#         self.assertEqual(self.app.find_substring_edge('not there', st.id), (None, None))
#         self.assertEqual(self.app.find_substring_edge('', st.id), (None, None))
#         self.assertFalse(self.app.has_substring('not there', st.id))
#         self.assertFalse(self.app.has_substring('', st.id))
#
#         # Check substrings of string1 are in the tree.
#         edge, ln = self.app.find_substring_edge(string1, st.id)
#         assert isinstance(edge, SuffixTreeEdge)
#         # self.assertEqual(edge.label, string1 + STRING_ID_END)
#         # self.assertEqual(edge.label, string1 + string1_id + STRING_ID_END)
#         # self.assertEqual(edge.label, string1 + string1_id )
#
#         # Check the edge has a node.
#         node = self.app.node_repo[edge.dest_node_id]
#         assert isinstance(node, SuffixTreeNode)
#
#         # Check the node doesn't have a string ID.
#         # self.assertEqual(node.string_id, None)
#
#         # Check both IDs are returned.
#         result_ids = self.app.find_string_ids(string1, st.id)
#         self.assertEqual(result_ids, {string1_id, string2_id}, (result_ids))
#
#     def test_two_non_repeating_strings(self):
#         st = self.app.register_new_suffix_tree()
#         assert isinstance(st, GeneralizedSuffixTree)
#         string1_id = '1'
#         string1 = 'abc'
#         string2_id = '2'
#         string2 = 'def'
#         self.add_string_to_suffix_tree(string1, string1_id, st)
#         self.add_string_to_suffix_tree(string2, string2_id, st)
#
#         # Check various non-substrings aren't in the tree.
#         self.assertEqual(self.app.find_substring_edge('not there', st.id), (None, None))
#         self.assertEqual(self.app.find_substring_edge('', st.id), (None, None))
#         self.assertFalse(self.app.has_substring('not there', st.id))
#         self.assertFalse(self.app.has_substring('', st.id))
#
#         # Check substrings of string1 are in the tree.
#         edge, ln = self.app.find_substring_edge(string1, st.id)
#         assert isinstance(edge, SuffixTreeEdge)
#         # self.assertEqual(edge.label, string1 + STRING_ID_END)
#         # self.assertEqual(edge.label, string1 + string1_id + STRING_ID_END)
#
#         # Check the edge has a node.
#         node = self.app.node_repo[edge.dest_node_id]
#         assert isinstance(node, SuffixTreeNode)
#
#         # Check the node has a string ID.
#         self.assertEqual(node.string_id, string1_id)
#
#         # Check the string1 ID is returned.
#         result_ids = self.app.find_string_ids(string1, st.id)
#         self.assertEqual(result_ids, {string1_id})
#
#         # Check substrings of string2 are in the tree.
#         edge, ln = self.app.find_substring_edge(string2, st.id)
#         assert isinstance(edge, SuffixTreeEdge)
#         # self.assertEqual(edge.label, string2 + STRING_ID_END)
#         # self.assertEqual(edge.label, string2 + string2_id+ STRING_ID_END)
#
#         # Check the edge has a node.
#         node = self.app.node_repo[edge.dest_node_id]
#         assert isinstance(node, SuffixTreeNode)
#
#         # Check the node has a string ID.
#         self.assertEqual(node.string_id, string2_id)
#
#         # Check the string2 ID is returned.
#         result_ids = self.app.find_string_ids(string2, st.id)
#         self.assertEqual(result_ids, {string2_id})
#
#     def test_common_prefix_two_non_repeating_strings_with(self):
#         st = self.app.register_new_suffix_tree()
#         assert isinstance(st, GeneralizedSuffixTree)
#         common_prefix = 'z'
#         string1_id = '1'
#         string1 = common_prefix + 'abc'
#         string2_id = '2'
#         string2 = common_prefix + 'def'
#         self.add_string_to_suffix_tree(string1, string1_id, st)
#         self.add_string_to_suffix_tree(string2, string2_id, st)
#
#         # Check various non-substrings aren't in the tree.
#         self.assertEqual(self.app.find_substring_edge('not there', st.id), (None, None))
#         self.assertEqual(self.app.find_substring_edge('', st.id), (None, None))
#         self.assertFalse(self.app.has_substring('not there', st.id))
#         self.assertFalse(self.app.has_substring('', st.id))
#
#         # Check substrings of string1 are in the tree.
#         edge, ln = self.app.find_substring_edge(string1, st.id)
#         assert isinstance(edge, SuffixTreeEdge)
#         # self.assertEqual(edge.label, string1[1:] + STRING_ID_END)
#         # self.assertEqual(edge.label, string1[1:] + string1_id + STRING_ID_END)
#
#         # Check the edge has a node.
#         node = self.app.node_repo[edge.dest_node_id]
#         assert isinstance(node, SuffixTreeNode)
#
#         # Check the node has a string ID.
#         self.assertEqual(node.string_id, string1_id)
#
#         # Check the string1 ID is returned.
#         result_ids = self.app.find_string_ids(string1, st.id)
#         self.assertEqual(result_ids, {string1_id})
#
#         # Check substrings of string2 are in the tree.
#         edge, ln = self.app.find_substring_edge(string2, st.id)
#         assert isinstance(edge, SuffixTreeEdge)
#         # self.assertEqual(edge.label, string2[1:] + STRING_ID_END)
#         # self.assertEqual(edge.label, string2[1:] + string2_id + STRING_ID_END)
#
#         # Check the edge has a node.
#         node = self.app.node_repo[edge.dest_node_id]
#         assert isinstance(node, SuffixTreeNode)
#
#         # Check the node has a string ID.
#         self.assertEqual(node.string_id, string2_id)
#
#         # Check the string2 ID is returned.
#         result_ids = self.app.find_string_ids(string2, st.id)
#         self.assertEqual(result_ids, {string2_id})
#
#         # Check common prefix is in the tree.
#         edge, ln = self.app.find_substring_edge(common_prefix, st.id)
#         assert isinstance(edge, SuffixTreeEdge)
#         self.assertEqual(edge.label, common_prefix)
#
#         # Check the edge has a node.
#         node = self.app.node_repo[edge.dest_node_id]
#         assert isinstance(node, SuffixTreeNode)
#
#         # Check the node has a string ID.
#         self.assertEqual(node.string_id, None)
#
#         # Check both IDs are returned.
#         result_ids = self.app.find_string_ids(common_prefix, st.id)
#         self.assertEqual(result_ids, {string1_id, string2_id})
#
#     def test_common_suffix_two_non_repeating_strings_with(self):
#         st = self.app.register_new_suffix_tree()
#         assert isinstance(st, GeneralizedSuffixTree)
#         common_suffix = 'z'
#         string1_id = '1'
#         string1 = 'abc' + common_suffix
#         string2_id = '2'
#         string2 = 'def' + common_suffix
#         self.add_string_to_suffix_tree(string1, string1_id, st)
#         self.add_string_to_suffix_tree(string2, string2_id, st)
#
#         # Check various non-substrings aren't in the tree.
#         self.assertEqual(self.app.find_substring_edge('not there', st.id), (None, None))
#         self.assertEqual(self.app.find_substring_edge('', st.id), (None, None))
#         self.assertFalse(self.app.has_substring('not there', st.id))
#         self.assertFalse(self.app.has_substring('', st.id))
#
#         # Check substrings of string1 are in the tree.
#         edge, ln = self.app.find_substring_edge(string1, st.id)
#         assert isinstance(edge, SuffixTreeEdge)
#         # self.assertEqual(edge.label, string1 + STRING_ID_END)
#         # self.assertEqual(edge.label, string1 + string1_id + STRING_ID_END)
#
#         # Check the edge has a node.
#         node = self.app.node_repo[edge.dest_node_id]
#         assert isinstance(node, SuffixTreeNode)
#
#         # Check the node has a string ID.
#         self.assertEqual(node.string_id, string1_id)
#
#         # Check the string1 ID is returned.
#         result_ids = self.app.find_string_ids(string1, st.id)
#         self.assertEqual(result_ids, {string1_id})
#
#         # Check substrings of string2 are in the tree.
#         edge, ln = self.app.find_substring_edge(string2, st.id)
#         assert isinstance(edge, SuffixTreeEdge)
#         # self.assertEqual(edge.label, string2 + STRING_ID_END)
#         # self.assertEqual(edge.label, string2 + string2_id + STRING_ID_END)
#
#         # Check the edge has a node.
#         node = self.app.node_repo[edge.dest_node_id]
#         assert isinstance(node, SuffixTreeNode)
#
#         # Check the node has a string ID.
#         self.assertEqual(node.string_id, string2_id)
#
#         # Check the string2 ID is returned.
#         result_ids = self.app.find_string_ids(string2, st.id)
#         self.assertEqual(result_ids, {string2_id})
#
#         # Check common suffix is in the tree.
#         edge, ln = self.app.find_substring_edge(common_suffix, st.id)
#         assert isinstance(edge, SuffixTreeEdge)
#         # self.assertEqual(edge.label, common_suffix + STRING_ID_END)
#         # self.assertEqual(edge.label, common_suffix)
#
#         # Check the edge has a node.
#         node = self.app.node_repo[edge.dest_node_id]
#         assert isinstance(node, SuffixTreeNode)
#
#         # Check the node doesn't have a string ID.
#         # self.assertEqual(node.string_id, None)
#
#         # Check both IDs are returned.
#         result_ids = self.app.find_string_ids(common_suffix, st.id)
#         self.assertEqual(result_ids, {string1_id, string2_id})
#
#     def test_mississippi(self):
#         st = self.app.register_new_suffix_tree()
#         self.add_string_to_suffix_tree("mississippi", "$", st)
#         self.add_string_to_suffix_tree("mudpie", "#", st)
#         self.add_string_to_suffix_tree("ball", "%", st)
#         self.add_string_to_suffix_tree("ball", "&", st)
#
#         # Check there isn't an 'a'.
#         self.assertEqual(self.app.find_substring_edge('j', st.id), (None, None))
#
#         # Check 'm'.
#         edge, ln = self.app.find_substring_edge('m', st.id)
#         # self.assertEqual(edge.label, 'm')
#         self.assertEqual(self.app.find_string_ids('m', st.id), {'$', '#'})
#
#         # Check 'mi'.
#         edge, ln = self.app.find_substring_edge('mi', st.id)
#         # self.assertEqual(edge.label, 'ississippi' + STRING_ID_END)
#         self.assertEqual(self.app.find_string_ids('mi', st.id), {'$'})
#
#         # Check 'mu'.
#         edge, ln = self.app.find_substring_edge('mu', st.id)
#         # self.assertEqual(edge.label, 'udpie' + STRING_ID_END)
#         self.assertEqual(self.app.find_string_ids('mu', st.id), {'#'})
#
#         # Check 'missi'.
#         edge, ln = self.app.find_substring_edge('missi', st.id)
#         self.assertEqual(edge.label, 'ississippi' + STRING_ID_END)
#
#         # Check 'issi'.
#         edge, ln = self.app.find_substring_edge('issi', st.id)
#         self.assertEqual(edge.label, 'ssi')
#
#         # Check 'is'.
#         edge, ln = self.app.find_substring_edge('is', st.id)
#         self.assertEqual(edge.label, 'ssi')
#
#         # Check 'si'.
#         edge, ln = self.app.find_substring_edge('si', st.id)
#         self.assertEqual(edge.label, 'i')
#
#         # Check 'issip'.
#         edge, ln = self.app.find_substring_edge('issip', st.id)
#         self.assertEqual(edge.label, 'ppi' + STRING_ID_END)
#
#         # Check 'ssip'.
#         edge, ln = self.app.find_substring_edge('ssip', st.id)
#         self.assertEqual(edge.label, 'ppi' + STRING_ID_END)
#
#         # Check 'sip'.
#         edge, ln = self.app.find_substring_edge('sip', st.id)
#         self.assertEqual(edge.label, 'ppi' + STRING_ID_END)
#
#         # Check 'ip'.
#         edge, ln = self.app.find_substring_edge('ip', st.id)
#         self.assertEqual(edge.label, 'ppi' + STRING_ID_END)
#
#         # Check 'i'.
#         edge, ln = self.app.find_substring_edge('i', st.id)
#         self.assertEqual(edge.label, 'i')
#
#         # Check 'ippi'.
#         edge, ln = self.app.find_substring_edge('ippi', st.id)
#         self.assertEqual(edge.label, 'ppi' + STRING_ID_END)
#
#         # Check 'mudpie'.
#         edge, ln = self.app.find_substring_edge('mudpie', st.id)
#         self.assertEqual(edge.label, 'udpie' + STRING_ID_END)
#
#         # Check 'ball'.
#         edge, ln = self.app.find_substring_edge('ball', st.id)
#         self.assertEqual(edge.label, 'ball' + STRING_ID_END)
#
#         # Check ID is returned.
#         self.assertEqual(self.app.find_string_ids('mi', st.id), {'$'})
#         self.assertEqual(self.app.find_string_ids('si', st.id), {'$'})
#         self.assertEqual(self.app.find_string_ids('pp', st.id), {'$'})
#         self.assertEqual(self.app.find_string_ids('mu', st.id), {'#'})
#         self.assertEqual(self.app.find_string_ids('m', st.id), {'$', '#'})
#         self.assertEqual(self.app.find_string_ids('b', st.id), {'%', '&'})
#
#     def test_colours(self):
#         st = self.app.register_new_suffix_tree()
#         self.add_string_to_suffix_tree("blue", "$", st)
#         self.add_string_to_suffix_tree("red", "#", st)
#
#         # Check 'b'.
#         edge, ln = self.app.find_substring_edge('b', st.id)
#         self.assertEqual(edge.label, 'blue' + STRING_ID_END)
#
#         # Check 'l'.
#         edge, ln = self.app.find_substring_edge('l', st.id)
#         self.assertEqual(edge.label, 'lue' + STRING_ID_END)
#
#         # Check 'u'.
#         edge, ln = self.app.find_substring_edge('u', st.id)
#         self.assertEqual(edge.label, 'ue' + STRING_ID_END)
#
#         # Check 'e'.
#         edge, ln = self.app.find_substring_edge('e', st.id)
#         self.assertEqual(edge.label, 'e')
#
#         # Check 'ue'.
#         edge, ln = self.app.find_substring_edge('ue', st.id)
#         self.assertEqual(edge.label, 'ue' + STRING_ID_END)
#
#         # Check 'lue'.
#         edge, ln = self.app.find_substring_edge('lue', st.id)
#         self.assertEqual(edge.label, 'lue' + STRING_ID_END)
#
#         # Check 'blue'.
#         edge, ln = self.app.find_substring_edge('blue', st.id)
#         self.assertEqual(edge.label, 'blue' + STRING_ID_END)
#
#         # Check 're'.
#         edge, ln = self.app.find_substring_edge('re', st.id)
#         self.assertEqual(edge.label, 'red' + STRING_ID_END)
#
#         # Check 'ed'.
#         edge, ln = self.app.find_substring_edge('ed', st.id)
#         self.assertEqual(edge.label, 'd' + STRING_ID_END)
#
#         # Check 'red'.
#         edge, ln = self.app.find_substring_edge('red', st.id)
#         self.assertEqual(edge.label, 'red' + STRING_ID_END)
#
#     def test_find_string_ids(self):
#         # This test is the first to involve the children of nodes.
#         st = self.app.register_new_suffix_tree()
#         string1_id = uuid.uuid4().hex
#         string2_id = uuid.uuid4().hex
#         string3_id = uuid.uuid4().hex
#         # string4_id = uuid.uuid4().hex
#         self.add_string_to_suffix_tree("blue", string1_id, st)
#         self.add_string_to_suffix_tree("red", string2_id, st)
#         self.add_string_to_suffix_tree("blues", string3_id, st)
#
#         strings = self.app.find_string_ids('$', st.id)
#         assert not strings, strings
#         strings = self.app.find_string_ids('0', st.id)
#         assert not strings, strings
#         strings = self.app.find_string_ids('1', st.id)
#         assert not strings, strings
#         strings = self.app.find_string_ids('2', st.id)
#         assert not strings, strings
#         strings = self.app.find_string_ids('3', st.id)
#         assert not strings, strings
#         strings = self.app.find_string_ids('4', st.id)
#         assert not strings, strings
#         strings = self.app.find_string_ids('5', st.id)
#         assert not strings, strings
#         strings = self.app.find_string_ids('6', st.id)
#         assert not strings, strings
#         strings = self.app.find_string_ids('7', st.id)
#         assert not strings, strings
#
#         # Find 'b'.
#         strings = self.app.find_string_ids('b', st.id)
#         self.assertIn(string1_id, strings)
#         self.assertNotIn(string2_id, strings)
#
#         # Find 'e'.
#         strings = self.app.find_string_ids('e', st.id)
#         self.assertEqual(len(strings), 3)
#         self.assertIn(string1_id, strings, (string1_id, string2_id, string3_id, strings))
#         self.assertIn(string2_id, strings, (string1_id, string2_id, string3_id, strings))
#         self.assertIn(string3_id, strings, (string1_id, string2_id, string3_id, strings))
#
#         # Find 'e' - limit 1.
#         strings = self.app.find_string_ids('e', st.id, limit=1)
#         self.assertEqual(len(strings), 1)
#
#         # Find 'e' - limit 2.
#         strings = self.app.find_string_ids('e', st.id, limit=2)
#         self.assertEqual(len(strings), 2)
#
#         # Find 'r'.
#         strings = self.app.find_string_ids('r', st.id)
#         self.assertNotIn(string1_id, strings)
#         self.assertIn(string2_id, strings)
#
#         # Find 'd'.
#         strings = self.app.find_string_ids('d', st.id)
#         self.assertNotIn(string1_id, strings)
#         self.assertIn(string2_id, strings)
#
#         # Find 's'.
#         strings = self.app.find_string_ids('s', st.id)
#         self.assertNotIn(string1_id, strings)
#         self.assertNotIn(string2_id, strings)
#         self.assertIn(string3_id, strings)
#
#     def test_add_string_to_suffixtree_from_repo(self):
#         # Check adding strings after getting the tree from the repo.
#         st = self.app.register_new_suffix_tree()
#
#         st = self.app.get_suffix_tree(st.id)
#         self.add_string_to_suffix_tree('blue', '1', st)
#
#         st = self.app.get_suffix_tree(st.id)
#         self.add_string_to_suffix_tree('green', '2', st)
#
#         st = self.app.get_suffix_tree(st.id)
#         self.add_string_to_suffix_tree('yellow', '3', st)
#
#         st = self.app.get_suffix_tree(st.id)
#         strings_ids = self.app.find_string_ids('e', st.id)
#         self.assertEqual(3, len(strings_ids), strings_ids)
#         self.assertEqual(['1', '2', '3'], sorted(strings_ids))
#
#     def test_remove_string_from_suffixtree(self):
#         st = self.app.register_new_suffix_tree()
#
#         # Add 'blue' and 'green'.
#         self.add_string_to_suffix_tree('blue', '1', st)
#         self.add_string_to_suffix_tree('green', '2', st)
#
#         strings_ids = self.app.find_string_ids('b', st.id)
#         self.assertEqual(1, len(strings_ids))
#
#         strings_ids = self.app.find_string_ids('l', st.id)
#         self.assertEqual(1, len(strings_ids))
#
#         strings_ids = self.app.find_string_ids('u', st.id)
#         self.assertEqual(1, len(strings_ids))
#
#         strings_ids = self.app.find_string_ids('r', st.id)
#         self.assertEqual(1, len(strings_ids))
#
#         strings_ids = self.app.find_string_ids('g', st.id)
#         self.assertEqual(1, len(strings_ids))
#
#         strings_ids = self.app.find_string_ids('e', st.id)
#         self.assertEqual(2, len(strings_ids))
#
#         # Remove 'blue'.
#         st.remove_string('blue', '1')
#
#         strings_ids = self.app.find_string_ids('b', st.id)
#         self.assertEqual(0, len(strings_ids))
#
#         strings_ids = self.app.find_string_ids('l', st.id)
#         self.assertEqual(0, len(strings_ids))
#
#         strings_ids = self.app.find_string_ids('u', st.id)
#         self.assertEqual(0, len(strings_ids))
#
#         strings_ids = self.app.find_string_ids('r', st.id)
#         self.assertEqual(1, len(strings_ids))
#
#         strings_ids = self.app.find_string_ids('g', st.id)
#         self.assertEqual(1, len(strings_ids))
#
#         strings_ids = self.app.find_string_ids('e', st.id)
#         self.assertEqual(1, len(strings_ids), strings_ids)
#
#         # Add 'blue' again.
#         self.add_string_to_suffix_tree('blue', '1', st)
#
#         strings_ids = self.app.find_string_ids('b', st.id)
#         self.assertEqual(1, len(strings_ids))
#
#         strings_ids = self.app.find_string_ids('l', st.id)
#         self.assertEqual(1, len(strings_ids))
#
#         strings_ids = self.app.find_string_ids('u', st.id)
#         self.assertEqual(1, len(strings_ids))
#
#         strings_ids = self.app.find_string_ids('r', st.id)
#         self.assertEqual(1, len(strings_ids))
#
#         strings_ids = self.app.find_string_ids('g', st.id)
#         self.assertEqual(1, len(strings_ids))
#
#         strings_ids = self.app.find_string_ids('e', st.id)
#         self.assertEqual(2, len(strings_ids))
#
#
# @skip
# @notquick
# class TestGeneralizedSuffixTreeSlow(GeneralizedSuffixTreeTestCase):
#     def test_long_string(self):
#         st = self.app.register_new_suffix_tree()
#         self.add_string_to_suffix_tree(LONG_TEXT[:12000], '1', st)
#         self.assertEqual(self.app.find_string_ids('Ukkonen', st.id), {'1'})
#         self.assertEqual(self.app.find_string_ids('Optimal', st.id), {'1'})
#         self.assertFalse(self.app.find_string_ids('ukkonen', st.id))
#         self.add_string_to_suffix_tree(LONG_TEXT_CONT[:1000], '2', st)
#         self.assertEqual(self.app.find_string_ids('Burrows-Wheeler', st.id), {'2'})
#         self.assertEqual(self.app.find_string_ids('suffix', st.id), {'1', '2'})
#
#     def test_split_long_string(self):
#         # Split the long string into separate strings, and make some IDs.
#         list_of_strings = [w for w in LONG_TEXT[:1000].split(' ') if w]
#
#         print("Long string split into words: {}".format(list_of_strings))
#
#         string_ids = {}
#         for string in list_of_strings:
#             string_id = uuid.uuid4().hex
#             string_ids[string_id] = string
#
#         # Build the suffix tree.
#         st = self.app.register_new_suffix_tree()
#         for string_id, string in string_ids.items():
#             self.add_string_to_suffix_tree(string, string_id, st)
#
#         # Check the suffix tree.
#         for string_id, string in string_ids.items():
#             self.assertIn(string_id, self.app.find_string_ids(string, st.id), (string, string_id))
#
#         # Build the suffix tree.
#         #  - this time, get the suffix tree afresh from the repo each time
#         st = self.app.register_new_suffix_tree()
#         for string_id, string in string_ids.items():
#             st = self.app.get_suffix_tree(st.id)
#             self.add_string_to_suffix_tree(string, string_id, st)
#
#         # Check the suffix tree.
#         for string_id, string in string_ids.items():
#             self.assertIn(string_id, self.app.find_string_ids(string, st.id))
#
#     def test_case_insensitivity(self):
#         st = self.app.register_new_suffix_tree(case_insensitive=True)
#         self.add_string_to_suffix_tree(LONG_TEXT[:12000], '1', st)
#         self.assertEqual(self.app.find_string_ids('ukkonen', st.id), {'1'})
#         self.assertEqual(self.app.find_string_ids('Optimal', st.id), {'1'})
#         self.assertEqual(self.app.find_string_ids('burrows-wheeler', st.id), set())
#         self.add_string_to_suffix_tree(LONG_TEXT_CONT[:1000], '2', st)
#         self.assertEqual(self.app.find_string_ids('ukkonen', st.id), {'1'})
#         self.assertEqual(self.app.find_string_ids('Optimal', st.id), {'1'})
#         self.assertEqual(self.app.find_string_ids('burrows-wheeler', st.id), {'2'})
#
#
# @skip
# @notquick
# class TestMultiprocessingWithGeneralizedSuffixTree(CassandraDatastoreTestCase):
#     def setUp(self):
#         super(TestMultiprocessingWithGeneralizedSuffixTree, self).setUp()
#         self.app = None
#
#     def tearDown(self):
#         super(TestMultiprocessingWithGeneralizedSuffixTree, self).tearDown()
#         if self.app is not None:
#             self.app.close()
#
#     @notquick
#     def test_words_in_sorted_order(self):
#         self.check_words(is_sorted=True)
#
#     # Todo: Fix this - adding strings in a random order sometimes breaks (perhaps a dict is causing indeterminate
#     # order).
#     # def test_words_in_unsorted_order(self):
#     #     self.check_words()
#
#     # Todo: Fix this - adding strings in a reversed sorted order always fails. Not sure why all substrings of 'ree'
#     # fail. The suffix is obviously not moving along in the same way as it does when the nodes are added. Perhaps it
#     #  needs to add the IDs when explicit match is made, and then move the first char along by one? Not sure so
#     # trace it out?
#     # def test_words_in_reverse_sorted_order(self):
#     #     self.check_words(is_reversed=True)
#     #
#     # The error reported is:-
#     #
#     # >       self.assertFalse(errors, "\n".join(errors))
#     # E       Not found: substring ''e'' from string ''tree''
#     # E       Not found: substring ''ee'' from string ''tree''
#     # E       Not found: substring ''r'' from string ''tree''
#     # E       Not found: substring ''re'' from string ''tree''
#     # E       Not found: substring ''ree'' from string ''tree''
#
#     def check_words(self, is_sorted=False, is_reversed=False):
#         # Split the long string into separate strings, and make some IDs.
#         words = list([w for w in LONG_TEXT[:100].split(' ') if w])
#
#         print("Adding words: {}".format(words))
#
#         # Avoid adding the same string twice (or a prefix of a previous string).
#         #  - because it's a current problem unless we append string IDs, which makes things too slow
#         # words = set(words)
#         # words = [w for w in words if 0 != sum([x.startswith(w) for x in words if x != w])]
#
#         assert words
#
#         # Make a string ID for each string.
#         strings = {}
#         for string in words:
#             string_id = uuid.uuid4().hex
#             strings[string_id] = string
#
#         # Create a new suffix tree.
#         self.app = SuffixTreeApplicationWithCassandra()
#         st = self.app.register_new_suffix_tree()
#         assert st.id in self.app.suffix_tree_repo
#
#         # Close the app, so the pool doesn't inherit it.
#         self.app.close()
#
#         # Start the pool.
#         pool = Pool(initializer=pool_initializer, processes=1)
#
#         words = [[s, sid, st.id] for sid, s in strings.items() if s]
#
#         if is_sorted:
#             words = sorted(words)
#         if is_reversed:
#             words = reversed(words)
#
#         results = pool.map(add_string_to_suffix_tree, words)
#         for result in results:
#             if isinstance(result, Exception):
#                 print(result.args[0][1])
#                 raise result
#
#         # Creat the app again.
#         self.app = SuffixTreeApplicationWithCassandra()
#
#         errors = []
#
#         # Check the suffix tree returns string ID for all substrings of string.
#         for string_id, string in strings.items():
#             # Check all prefixes and suffixes.
#             substrings = sorted(list(get_all_substrings(string)))
#             print("")
#             print("Checking for all substrings of string '{}': {}".format(repr(string),
#                                                                           " ".join([repr(s) for s in substrings])))
#             for substring in substrings:
#                 results = self.app.find_string_ids(substring, st.id)
#                 if string_id not in results:
#                     msg = "Not found: substring '{}' from string '{}'".format(repr(substring), repr(string))
#                     print(msg)
#                     errors.append(msg)
#
#         # Check for errors.
#         self.assertFalse(errors, "\n".join(errors))
#
#
# def get_all_substrings(s):
#     length = len(s)
#     return (s[i:j] for i in range(length) for j in range(i + 1, length + 1))
#
#
# worker_app = None
#
#
# def pool_initializer():
#     global worker_app
#     worker_app = SuffixTreeApplicationWithCassandra()
#
#
# def add_string_to_suffix_tree(args):
#     # random.seed()
#     string, string_id, suffix_tree_id = args
#     print("")
#     print("Adding string to suffix tree: {}: {}".format(string_id, repr(string[:100])))
#     try:
#         assert isinstance(worker_app, AbstractSuffixTreeApplication)
#         suffix_tree = worker_app.get_suffix_tree(suffix_tree_id)
#         assert isinstance(suffix_tree, GeneralizedSuffixTree)
#         started = datetime.datetime.now()
#         suffix_tree.add_string(string, string_id)
#         print(" - added string in: {}".format(datetime.datetime.now() - started))
#     except Exception as e:
#         msg = traceback.format_exc()
#         print(" - failed to add string: {}".format(msg))
#         return Exception((e, msg, string, string_id))
#     return string_id
