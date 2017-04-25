# # coding=utf-8
# from __future__ import unicode_literals
#
# LONG_TEXT_CONT = """
# This article's use of external links may not follow Wikipedia's policies or guidelines. Please improve this
# article by removing excessive and inappropriate external links. (August 2010)
# Suffix Trees by Dr. Sartaj Sahni (CISE Department Chair at University of Florida)
# Suffix Trees by Lloyd Allison
# NIST's Dictionary of Algorithms and Data Structures: Suffix Tree
# suffix_tree ANSI C implementation of a Suffix Tree
# libstree, a generic suffix tree library written in C
# Tree::Suffix, a Perl binding to libstree
# Strmat a faster generic suffix tree library written in C (uses arrays instead of linked lists)
# SuffixTree a Python binding to Strmat
# Universal Data Compression Based on the Burrows-Wheeler Transformation: Theory and Practice, application of suffix
#  trees in the BWT
# Theory and Practice of Succinct Data Structures, C++ implementation of a compressed suffix tree]
# Practical Algorithm Template Library, a C++ library with suffix tree
#
# In computer science, a suffix tree (also called PAT tree or, in an earlier form, position tree) is a data
# structure that presents the suffixes of a given string in a way that allows for a particularly fast implementation
#  of many important string operations.
# The suffix tree for a string S is a tree whose edges are labeled with strings, such that each suffix of S
# corresponds to exactly one path from the tree's root to a leaf. It is thus a radix tree (more specifically,
# a Patricia tree) for the suffixes of S.
# Constructing such a tree for the string S takes time and space linear in the length of S. Once constructed,
# several operations can be performed quickly, for instance locating a substring in S, locating a substring if a
# certain number of mistakes are allowed, locating matches for a regular expression pattern etc. Suffix trees also
# provided one of the first linear-time solutions for the longest common substring problem. These speedups come at a
#  cost: storing a string's suffix tree typically requires significantly more space than storing the string itself.
# Contents [hide]
# 1 History
# 2 Definition
# 3 Generalised suffix tree
# 4 Functionality
# 5 Applications
# 6 Implementation
# 7 External construction
# 8 See also
# 9 References
# 10 External links
# [edit]History
#
# The concept was first introduced as a position tree by Weiner in 1973,[1] which Donald Knuth subsequently
# characterized as "Algorithm of the Year 1973". The construction was greatly simplified by McCreight in 1976 [2] ,
# and also by Ukkonen in 1995.[3][4] Ukkonen provided the first linear-time online-construction of suffix trees,
# now known as Ukkonen's algorithm. These algorithms are all linear-time for constant-size alphabet,
# and have worst-case running time of O(nlogn) in general.
# In 1997, Farach[5] gave the first suffix tree construction algorithm that is optimal for all alphabets. In
# particular, this is the first linear-time algorithm for strings drawn from an alphabet of integers in a polynomial
#  range. This latter algorithm has become the basis for new algorithms for constructing both suffix trees and
# suffix arrays, for example, in external memory, compressed, succinct, etc.
# [edit]Definition
#
# The suffix tree for the string S of length n is defined as a tree such that ([6] page 90):
# the paths from the root to the leaves have a one-to-one relationship with the suffixes of S,
# edges spell non-empty strings,
# and all internal nodes (except perhaps the root) have at least two children.
# Since such a tree does not exist for all strings, S is padded with a terminal symbol not seen in the string (
# usually denoted $). This ensures that no suffix is a prefix of another, and that there will be n leaf nodes,
# one for each of the n suffixes of S. Since all internal non-root nodes are branching, there can be at most n −  1
# such nodes, and n + (n − 1) + 1 = 2n nodes in total (n leaves, n − 1 internal nodes, 1 root).
# Suffix links are a key feature for older linear-time construction algorithms, although most newer algorithms,
# which are based on Farach's algorithm, dispense with suffix links. In a complete suffix tree, all internal
# non-root nodes have a suffix link to another internal node. If the path from the root to a node spells the string
# χα, where χ is a single character and α is a string (possibly empty), it has a suffix link to the internal node
# representing α. See for example the suffix link from the node for ANA to the node for NA in the figure above.
# Suffix links are also used in some algorithms running on the tree.
#
# A suffix tree for a string S of length n can be built in Θ(n) time, if the letters come from an alphabet of
# integers in a polynomial range (in particular, this is true for constant-sized alphabets).[5] For larger
# alphabets, the running time is dominated by first sorting the letters to bring them into a range of size O(n); in
# general, this takes O(nlogn) time. The costs below are given under the assumption that the alphabet is constant.
# Assume that a suffix tree has been built for the string S of length n, or that a generalised suffix tree has been
# built for the set of strings  of total length . You can:
# Search for strings:
# Check if a string P of length m is a substring in O(m) time ([6] page 92).
# Find the first occurrence of the patterns  of total length m as substrings in O(m) time.
# Find all z occurrences of the patterns  of total length m as substrings in O(m + z) time ([6] page 123).
# Search for a regular expression P in time expected sublinear in n ([7]).
# Find for each suffix of a pattern P, the length of the longest match between a prefix of  and a substring in D in
# Θ(m) time ([6] page 132). This is termed the matching statistics for P.
# Find properties of the strings:
# Find the longest common substrings of the string Si and Sj in Θ(ni + nj) time ([6] page 125).
# Find all maximal pairs, maximal repeats or supermaximal repeats in Θ(n + z) time ([6] page 144).
# Find the Lempel–Ziv decomposition in Θ(n) time ([6] page 166).
# Find the longest repeated substrings in Θ(n) time.
# Find the most frequently occurring substrings of a minimum length in Θ(n) time.
# Find the shortest strings from Σ that do not occur in D, in O(n + z) time, if there are z such strings.
# Find the shortest substrings occurring only once in Θ(n) time.
# Find, for each i, the shortest substrings of Si not occurring elsewhere in D in Θ(n) time.
# The suffix tree can be prepared for constant time lowest common ancestor retrieval between nodes in Θ(n) time ([6]
#  chapter 8). You can then also:
# Find the longest common prefix between the suffixes Si[p..ni] and Sj[q..nj] in Θ(1) ([6] page 196).
# Search for a pattern P of length m with at most k mismatches in O(kn + z) time, where z is the number of hits ([6]
#  page 200).
# Find all z maximal palindromes in Θ(n)([6] page 198), or Θ(gn) time if gaps of length g are allowed, or Θ(kn) if k
#  mismatches are allowed ([6] page 201).
# Find all z tandem repeats in O(nlogn + z), and k-mismatch tandem repeats in O(knlog(n / k) + z) ([6] page 204).
# Find the longest substrings common to at least k strings in D for  in Θ(n) time ([6] page 205).
# [edit]Applications
#
# Suffix trees can be used to solve a large number of string problems that occur in text-editing, free-text search,
# computational biology and other application areas.[8] Primary applications include:[8]
# String search, in O(m) complexity, where m is the length of the sub-string (but with initial O(n) time required to
#  build the suffix tree for the string)
# Finding the longest repeated substring
# Finding the longest common substring
# Finding the longest palindrome in a string
# Suffix trees are often used in bioinformatics applications, searching for patterns in DNA or protein sequences (
# which can be viewed as long strings of characters). The ability to search efficiently with mismatches might be
# considered their greatest strength. Suffix trees are also used in data compression; they can be used to find
# repeated data, and can be used for the sorting stage of the Burrows–Wheeler transform. Variants of the LZW
# compression schemes use suffix trees (LZSS). A suffix tree is also used in suffix tree clustering,
# a data clustering algorithm used in some search engines (first introduced in [9]).
# [edit]Implementation
#
# If each node and edge can be represented in Θ(1) space, the entire tree can be represented in Θ(n) space. The
# total length of all the strings on all of the edges in the tree is O(n2), but each edge can be stored as the
# position and length of a substring of S, giving a total space usage of Θ(n) computer words. The worst-case space
# usage of a suffix tree is seen with a fibonacci word, giving the full 2n nodes.
# An important choice when making a suffix tree implementation is the parent-child relationships between nodes. The
# most common is using linked lists called sibling lists. Each node has a pointer to its first child, and to the
# next node in the child list it is a part of. Hash maps, sorted/unsorted arrays (with array doubling), and balanced
#  search trees may also be used, giving different running time properties. We are interested in:
# The cost of finding the child on a given character.
# The cost of inserting a child.
# The cost of enlisting all children of a node (divided by the number of children in the table below).
# Let σ be the size of the alphabet. Then you have the following costs:
# Lookup	Insertion	Traversal
# Sibling lists / unsorted arrays	O(σ)	Θ(1)	Θ(1)
# Hash maps	Θ(1)	Θ(1)	O(σ)
# Balanced search tree	O(logσ)	O(logσ)	O(1)
# Sorted arrays	O(logσ)	O(σ)	O(1)
# Hash maps + sibling lists	O(1)	O(1)	O(1)
# Note that the insertion cost is amortised, and that the costs for hashing are given perfect hashing.
# The large amount of information in each edge and node makes the suffix tree very expensive, consuming about ten to
#  twenty times the memory size of the source text in good implementations. The suffix array reduces this
# requirement to a factor of four, and researchers have continued to find smaller indexing structures.
# [edit]External construction
#
# Suffix trees quickly outgrow the main memory on standard machines for sequence collections in the order of
# gigabytes. As such, their construction calls for external memory approaches.
# There are theoretical results for constructing suffix trees in external memory. The algorithm by Farach et al. [
# 10] is theoretically optimal, with an I/O complexity equal to that of sorting. However, as discussed for example
# in ,[11] the overall intricacy of this algorithm has prevented, so far, its practical implementation.
# On the other hand, there have been practical works for constructing disk-based suffix trees which scale to (few)
# GB/hours. The state of the art methods are TDD ,[12] TRELLIS [13] , DiGeST ,[14] and B2ST .[15]
# TDD and TRELLIS scale up to the entire human genome – approximately 3GB – resulting in a disk-based suffix tree of
#  a size in the tens of gigabytes,.[12][13] However, these methods cannot handle efficiently collections of
# sequences exceeding 3GB.[14] DiGeST performs significantly better and is able to handle collections of sequences
# in the order of 6GB in about 6 hours.[14] The source code and documentation for the latter is available from [16]
# . All these methods can efficiently build suffix trees for the case when the tree does not fit in main memory,
# but the input does. The most recent method, B2ST,[15] scales to handle inputs that do not fit in main memory.
# [edit]See also
#
# Suffix array
# Generalised suffix tree
# [edit]References
#
# ^ P. Weiner (1973). "Linear pattern matching algorithm". 14th Annual IEEE Symposium on Switching and Automata
# Theory. pp. 1–11. doi:10.1109/SWAT.1973.13.
# ^ Edward M. McCreight (1976). "A Space-Economical Suffix Tree Construction Algorithm". Journal of the ACM 23 (2):
# 262–272. doi:10.1145/321941.321946.
# ^ E. Ukkonen (1995). "On-line construction of suffix trees". Algorithmica 14 (3): 249–260. doi:10.1007/BF01206331.
# ^ R. Giegerich and S. Kurtz (1997). "From Ukkonen to McCreight and Weiner: A Unifying View of Linear-Time Suffix
# Tree Construction". Algorithmica 19 (3): 331–353. doi:10.1007/PL00009177.
# ^ a b M. Farach (1997). "Optimal Suffix Tree Construction with Large Alphabets". FOCS: 137–143.
# ^ a b c d e f g h i j k l m n Gusfield, Dan (1999) [1997]. Algorithms on Strings, Trees and Sequences: Computer
# Science and Computational Biology. USA: Cambridge University Press. ISBN 0-521-58519-8.
# ^ Ricardo A. Baeza-Yates and Gaston H. Gonnet (1996). "Fast text searching for regular expressions or automaton
# searching on tries". Journal of the ACM (ACM Press) 43 (6): 915–936. doi:10.1145/235809.235810.
# ^ a b Allison, L.. "Suffix Trees". Retrieved 2008-10-14.
# ^ Oren Zamir and Oren Etzioni (1998). "Web document clustering: a feasibility demonstration". SIGIR '98:
# Proceedings of the 21st annual international ACM SIGIR conference on Research and development in information
# retrieval. ACM. pp. 46–54.
# ^ Martin Farach-Colton, Paolo Ferragina, S. Muthukrishnan (2000). "On the sorting-complexity of suffix tree
# construction.". J. Acm 47(6) 47 (6): 987–1011. doi:10.1145/355541.355547.
# ^ Smyth, William (2003). Computing Patterns in Strings. Addison-Wesley.
# ^ a b Sandeep Tata, Richard A. Hankins, and Jignesh M. Patel (2003). "Practical Suffix Tree Construction". VLDB
# '03: Proceedings of the 30th International Conference on Very Large Data Bases. Morgan Kaufmann. pp. 36–47.
# ^ a b Benjarath Phoophakdee and Mohammed J. Zaki (2007). "Genome-scale disk-based suffix tree indexing". SIGMOD
# '07: Proceedings of the ACM SIGMOD International Conference on Management of Data. ACM. pp. 833–844.
# ^ a b c Marina Barsky, Ulrike Stege, Alex Thomo, and Chris Upton (2008). "A new method for indexing genomes using
# on-disk suffix trees". CIKM '08: Proceedings of the 17th ACM Conference on Information and Knowledge Management.
# ACM. pp. 649–658.
# ^ a b Marina Barsky, Ulrike Stege, Alex Thomo, and Chris Upton (2009). "Suffix trees for very large genomic
# sequences". CIKM '09: Proceedings of the 18th ACM Conference on Information and Knowledge Management. ACM.
# ^ "The disk-based suffix tree for pattern search in sequenced genomes". Retrieved 2009-10-15.
# [edit]External links
#
#
# This article's use of external links may not follow Wikipedia's policies or guidelines. Please improve this
# article by removing excessive and inappropriate external links. (August 2010)
# Suffix Trees by Dr. Sartaj Sahni (CISE Department Chair at University of Florida)
# Suffix Trees by Lloyd Allison
# NIST's Dictionary of Algorithms and Data Structures: Suffix Tree
# suffix_tree ANSI C implementation of a Suffix Tree
# libstree, a generic suffix tree library written in C
# Tree::Suffix, a Perl binding to libstree
# Strmat a faster generic suffix tree library written in C (uses arrays instead of linked lists)
# SuffixTree a Python binding to Strmat
# Universal Data Compression Based on the Burrows-Wheeler Transformation: Theory and Practice, application of suffix
#  trees in the BWT
# Theory and Practice of Succinct Data Structures, C++ implementation of a compressed suffix tree]
# Practical Algorithm Template Library, a C++ library with suffix treeIn computer science, a suffix tree (also
# called PAT tree or, in an earlier form, position tree) is a data structure that presents the suffixes of a given
# string in a way that allows for a particularly fast implementation of many important string operations.
# The suffix tree for a string S is a tree whose edges are labeled with strings, such that each suffix of S
# corresponds to exactly one path from the tree's root to a leaf. It is thus a radix tree (more specifically,
# a Patricia tree) for the suffixes of S.
# Constructing such a tree for the string S takes time and space linear in the length of S. Once constructed,
# several operations can be performed quickly, for instance locating a substring in S, locating a substring if a
# certain number of mistakes are allowed, locating matches for a regular expression pattern etc. Suffix trees also
# provided one of the first linear-time solutions for the longest common substring problem. These speedups come at a
#  cost: storing a string's suffix tree typically requires significantly more space than storing the string itself.
# Contents [hide]
# 1 History
# 2 Definition
# 3 Generalised suffix tree
# 4 Functionality
# 5 Applications
# 6 Implementation
# 7 External construction
# 8 See also
# 9 References
# 10 External links
# [edit]History
#
# The concept was first introduced as a position tree by Weiner in 1973,[1] which Donald Knuth subsequently
# characterized as "Algorithm of the Year 1973". The construction was greatly simplified by McCreight in 1976 [2] ,
# and also by Ukkonen in 1995.[3][4] Ukkonen provided the first linear-time online-construction of suffix trees,
# now known as Ukkonen's algorithm. These algorithms are all linear-time for constant-size alphabet,
# and have worst-case running time of O(nlogn) in general.
# In 1997, Farach[5] gave the first suffix tree construction algorithm that is optimal for all alphabets. In
# particular, this is the first linear-time algorithm for strings drawn from an alphabet of integers in a polynomial
#  range. This latter algorithm has become the basis for new algorithms for constructing both suffix trees and
# suffix arrays, for example, in external memory, compressed, succinct, etc.
# [edit]Definition
#
# The suffix tree for the string S of length n is defined as a tree such that ([6] page 90):
# the paths from the root to the leaves have a one-to-one relationship with the suffixes of S,
# edges spell non-empty strings,
# and all internal nodes (except perhaps the root) have at least two children.
# Since such a tree does not exist for all strings, S is padded with a terminal symbol not seen in the string (
# usually denoted $). This ensures that no suffix is a prefix of another, and that there will be n leaf nodes,
# one for each of the n suffixes of S. Since all internal non-root nodes are branching, there can be at most n −  1
# such nodes, and n + (n − 1) + 1 = 2n nodes in total (n leaves, n − 1 internal nodes, 1 root).
# Suffix links are a key feature for older linear-time construction algorithms, although most newer algorithms,
# which are based on Farach's algorithm, dispense with suffix links. In a complete suffix tree, all internal
# non-root nodes have a suffix link to another internal node. If the path from the root to a node spells the string
# χα, where χ is a single character and α is a string (possibly empty), it has a suffix link to the internal node
# representing α. See for example the suffix link from the node for ANA to the node for NA in the figure above.
# Suffix links are also used in some algorithms running on the tree.
#
# A suffix tree for a string S of length n can be built in Θ(n) time, if the letters come from an alphabet of
# integers in a polynomial range (in particular, this is true for constant-sized alphabets).[5] For larger
# alphabets, the running time is dominated by first sorting the letters to bring them into a range of size O(n); in
# general, this takes O(nlogn) time. The costs below are given under the assumption that the alphabet is constant.
# Assume that a suffix tree has been built for the string S of length n, or that a generalised suffix tree has been
# built for the set of strings  of total length . You can:
# Search for strings:
# Check if a string P of length m is a substring in O(m) time ([6] page 92).
# Find the first occurrence of the patterns  of total length m as substrings in O(m) time.
# Find all z occurrences of the patterns  of total length m as substrings in O(m + z) time ([6] page 123).
# Search for a regular expression P in time expected sublinear in n ([7]).
# Find for each suffix of a pattern P, the length of the longest match between a prefix of  and a substring in D in
# Θ(m) time ([6] page 132). This is termed the matching statistics for P.
# Find properties of the strings:
# Find the longest common substrings of the string Si and Sj in Θ(ni + nj) time ([6] page 125).
# Find all maximal pairs, maximal repeats or supermaximal repeats in Θ(n + z) time ([6] page 144).
# Find the Lempel–Ziv decomposition in Θ(n) time ([6] page 166).
# Find the longest repeated substrings in Θ(n) time.
# Find the most frequently occurring substrings of a minimum length in Θ(n) time.
# Find the shortest strings from Σ that do not occur in D, in O(n + z) time, if there are z such strings.
# Find the shortest substrings occurring only once in Θ(n) time.
# Find, for each i, the shortest substrings of Si not occurring elsewhere in D in Θ(n) time.
# The suffix tree can be prepared for constant time lowest common ancestor retrieval between nodes in Θ(n) time ([6]
#  chapter 8). You can then also:
# Find the longest common prefix between the suffixes Si[p..ni] and Sj[q..nj] in Θ(1) ([6] page 196).
# Search for a pattern P of length m with at most k mismatches in O(kn + z) time, where z is the number of hits ([6]
#  page 200).
# Find all z maximal palindromes in Θ(n)([6] page 198), or Θ(gn) time if gaps of length g are allowed, or Θ(kn) if k
#  mismatches are allowed ([6] page 201).
# Find all z tandem repeats in O(nlogn + z), and k-mismatch tandem repeats in O(knlog(n / k) + z) ([6] page 204).
# Find the longest substrings common to at least k strings in D for  in Θ(n) time ([6] page 205).
# [edit]Applications
#
# Suffix trees can be used to solve a large number of string problems that occur in text-editing, free-text search,
# computational biology and other application areas.[8] Primary applications include:[8]
# String search, in O(m) complexity, where m is the length of the sub-string (but with initial O(n) time required to
#  build the suffix tree for the string)
# Finding the longest repeated substring
# Finding the longest common substring
# Finding the longest palindrome in a string
# Suffix trees are often used in bioinformatics applications, searching for patterns in DNA or protein sequences (
# which can be viewed as long strings of characters). The ability to search efficiently with mismatches might be
# considered their greatest strength. Suffix trees are also used in data compression; they can be used to find
# repeated data, and can be used for the sorting stage of the Burrows–Wheeler transform. Variants of the LZW
# compression schemes use suffix trees (LZSS). A suffix tree is also used in suffix tree clustering,
# a data clustering algorithm used in some search engines (first introduced in [9]).
# [edit]Implementation
#
# If each node and edge can be represented in Θ(1) space, the entire tree can be represented in Θ(n) space. The
# total length of all the strings on all of the edges in the tree is O(n2), but each edge can be stored as the
# position and length of a substring of S, giving a total space usage of Θ(n) computer words. The worst-case space
# usage of a suffix tree is seen with a fibonacci word, giving the full 2n nodes.
# An important choice when making a suffix tree implementation is the parent-child relationships between nodes. The
# most common is using linked lists called sibling lists. Each node has a pointer to its first child, and to the
# next node in the child list it is a part of. Hash maps, sorted/unsorted arrays (with array doubling), and balanced
#  search trees may also be used, giving different running time properties. We are interested in:
# The cost of finding the child on a given character.
# The cost of inserting a child.
# The cost of enlisting all children of a node (divided by the number of children in the table below).
# Let σ be the size of the alphabet. Then you have the following costs:
# Lookup	Insertion	Traversal
# Sibling lists / unsorted arrays	O(σ)	Θ(1)	Θ(1)
# Hash maps	Θ(1)	Θ(1)	O(σ)
# Balanced search tree	O(logσ)	O(logσ)	O(1)
# Sorted arrays	O(logσ)	O(σ)	O(1)
# Hash maps + sibling lists	O(1)	O(1)	O(1)
# Note that the insertion cost is amortised, and that the costs for hashing are given perfect hashing.
# The large amount of information in each edge and node makes the suffix tree very expensive, consuming about ten to
#  twenty times the memory size of the source text in good implementations. The suffix array reduces this
# requirement to a factor of four, and researchers have continued to find smaller indexing structures.
# [edit]External construction
#
# Suffix trees quickly outgrow the main memory on standard machines for sequence collections in the order of
# gigabytes. As such, their construction calls for external memory approaches.
# There are theoretical results for constructing suffix trees in external memory. The algorithm by Farach et al. [
# 10] is theoretically optimal, with an I/O complexity equal to that of sorting. However, as discussed for example
# in ,[11] the overall intricacy of this algorithm has prevented, so far, its practical implementation.
# On the other hand, there have been practical works for constructing disk-based suffix trees which scale to (few)
# GB/hours. The state of the art methods are TDD ,[12] TRELLIS [13] , DiGeST ,[14] and B2ST .[15]
# TDD and TRELLIS scale up to the entire human genome – approximately 3GB – resulting in a disk-based suffix tree of
#  a size in the tens of gigabytes,.[12][13] However, these methods cannot handle efficiently collections of
# sequences exceeding 3GB.[14] DiGeST performs significantly better and is able to handle collections of sequences
# in the order of 6GB in about 6 hours.[14] The source code and documentation for the latter is available from [16]
# . All these methods can efficiently build suffix trees for the case when the tree does not fit in main memory,
# but the input does. The most recent method, B2ST,[15] scales to handle inputs that do not fit in main memory.
# [edit]See also
#
# Suffix array
# Generalised suffix tree
# [edit]References
#
# ^ P. Weiner (1973). "Linear pattern matching algorithm". 14th Annual IEEE Symposium on Switching and Automata
# Theory. pp. 1–11. doi:10.1109/SWAT.1973.13.
# ^ Edward M. McCreight (1976). "A Space-Economical Suffix Tree Construction Algorithm". Journal of the ACM 23 (2):
# 262–272. doi:10.1145/321941.321946.
# ^ E. Ukkonen (1995). "On-line construction of suffix trees". Algorithmica 14 (3): 249–260. doi:10.1007/BF01206331.
# ^ R. Giegerich and S. Kurtz (1997). "From Ukkonen to McCreight and Weiner: A Unifying View of Linear-Time Suffix
# Tree Construction". Algorithmica 19 (3): 331–353. doi:10.1007/PL00009177.
# ^ a b M. Farach (1997). "Optimal Suffix Tree Construction with Large Alphabets". FOCS: 137–143.
# ^ a b c d e f g h i j k l m n Gusfield, Dan (1999) [1997]. Algorithms on Strings, Trees and Sequences: Computer
# Science and Computational Biology. USA: Cambridge University Press. ISBN 0-521-58519-8.
# ^ Ricardo A. Baeza-Yates and Gaston H. Gonnet (1996). "Fast text searching for regular expressions or automaton
# searching on tries". Journal of the ACM (ACM Press) 43 (6): 915–936. doi:10.1145/235809.235810.
# ^ a b Allison, L.. "Suffix Trees". Retrieved 2008-10-14.
# ^ Oren Zamir and Oren Etzioni (1998). "Web document clustering: a feasibility demonstration". SIGIR '98:
# Proceedings of the 21st annual international ACM SIGIR conference on Research and development in information
# retrieval. ACM. pp. 46–54.
# ^ Martin Farach-Colton, Paolo Ferragina, S. Muthukrishnan (2000). "On the sorting-complexity of suffix tree
# construction.". J. Acm 47(6) 47 (6): 987–1011. doi:10.1145/355541.355547.
# ^ Smyth, William (2003). Computing Patterns in Strings. Addison-Wesley.
# ^ a b Sandeep Tata, Richard A. Hankins, and Jignesh M. Patel (2003). "Practical Suffix Tree Construction". VLDB
# '03: Proceedings of the 30th International Conference on Very Large Data Bases. Morgan Kaufmann. pp. 36–47.
# ^ a b Benjarath Phoophakdee and Mohammed J. Zaki (2007). "Genome-scale disk-based suffix tree indexing". SIGMOD
# '07: Proceedings of the ACM SIGMOD International Conference on Management of Data. ACM. pp. 833–844.
# ^ a b c Marina Barsky, Ulrike Stege, Alex Thomo, and Chris Upton (2008). "A new method for indexing genomes using
# on-disk suffix trees". CIKM '08: Proceedings of the 17th ACM Conference on Information and Knowledge Management.
# ACM. pp. 649–658.
# ^ a b Marina Barsky, Ulrike Stege, Alex Thomo, and Chris Upton (2009). "Suffix trees for very large genomic
# sequences". CIKM '09: Proceedings of the 18th ACM Conference on Information and Knowledge Management. ACM.
# ^ "The disk-based suffix tree for pattern search in sequenced genomes". Retrieved 2009-10-15.
# [edit]External links
# """
# LONG_TEXT = """In computer science, a suffix tree (also called PAT tree or, in an earlier form, position tree) is
# a data structure that presents the suffixes of a given string in a way that allows for a particularly fast
# implementation of many important string operations.
# The suffix tree for a string S is a tree whose edges are labeled with strings, such that each suffix of S
# corresponds to exactly one path from the tree's root to a leaf. It is thus a radix tree (more specifically,
# a Patricia tree) for the suffixes of S.
# Constructing such a tree for the string S takes time and space linear in the length of S. Once constructed,
# several operations can be performed quickly, for instance locating a substring in S, locating a substring if a
# certain number of mistakes are allowed, locating matches for a regular expression pattern etc. Suffix trees also
# provided one of the first linear-time solutions for the longest common substring problem. These speedups come at a
#  cost: storing a string's suffix tree typically requires significantly more space than storing the string itself.
# Contents [hide]
# 1 History
# 2 Definition
# 3 Generalised suffix tree
# 4 Functionality
# 5 Applications
# 6 Implementation
# 7 External construction
# 8 See also
# 9 References
# 10 External links
# [edit]History
#
# The concept was first introduced as a position tree by Weiner in 1973,[1] which Donald Knuth subsequently
# characterized as "Algorithm of the Year 1973". The construction was greatly simplified by McCreight in 1976 [2] ,
# and also by Ukkonen in 1995.[3][4] Ukkonen provided the first linear-time online-construction of suffix trees,
# now known as Ukkonen's algorithm. These algorithms are all linear-time for constant-size alphabet,
# and have worst-case running time of O(nlogn) in general.
# In 1997, Farach[5] gave the first suffix tree construction algorithm that is optimal for all alphabets. In
# particular, this is the first linear-time algorithm for strings drawn from an alphabet of integers in a polynomial
#  range. This latter algorithm has become the basis for new algorithms for constructing both suffix trees and
# suffix arrays, for example, in external memory, compressed, succinct, etc.
# [edit]Definition
#
# The suffix tree for the string S of length n is defined as a tree such that ([6] page 90):
# the paths from the root to the leaves have a one-to-one relationship with the suffixes of S,
# edges spell non-empty strings,
# and all internal nodes (except perhaps the root) have at least two children.
# Since such a tree does not exist for all strings, S is padded with a terminal symbol not seen in the string (
# usually denoted $). This ensures that no suffix is a prefix of another, and that there will be n leaf nodes,
# one for each of the n suffixes of S. Since all internal non-root nodes are branching, there can be at most n −  1
# such nodes, and n + (n − 1) + 1 = 2n nodes in total (n leaves, n − 1 internal nodes, 1 root).
# Suffix links are a key feature for older linear-time construction algorithms, although most newer algorithms,
# which are based on Farach's algorithm, dispense with suffix links. In a complete suffix tree, all internal
# non-root nodes have a suffix link to another internal node. If the path from the root to a node spells the string
# χα, where χ is a single character and α is a string (possibly empty), it has a suffix link to the internal node
# representing α. See for example the suffix link from the node for ANA to the node for NA in the figure above.
# Suffix links are also used in some algorithms running on the tree.
#
# A suffix tree for a string S of length n can be built in Θ(n) time, if the letters come from an alphabet of
# integers in a polynomial range (in particular, this is true for constant-sized alphabets).[5] For larger
# alphabets, the running time is dominated by first sorting the letters to bring them into a range of size O(n); in
# general, this takes O(nlogn) time. The costs below are given under the assumption that the alphabet is constant.
# Assume that a suffix tree has been built for the string S of length n, or that a generalised suffix tree has been
# built for the set of strings  of total length . You can:
# Search for strings:
# Check if a string P of length m is a substring in O(m) time ([6] page 92).
# Find the first occurrence of the patterns  of total length m as substrings in O(m) time.
# Find all z occurrences of the patterns  of total length m as substrings in O(m + z) time ([6] page 123).
# Search for a regular expression P in time expected sublinear in n ([7]).
# Find for each suffix of a pattern P, the length of the longest match between a prefix of  and a substring in D in
# Θ(m) time ([6] page 132). This is termed the matching statistics for P.
# Find properties of the strings:
# Find the longest common substrings of the string Si and Sj in Θ(ni + nj) time ([6] page 125).
# Find all maximal pairs, maximal repeats or supermaximal repeats in Θ(n + z) time ([6] page 144).
# Find the Lempel–Ziv decomposition in Θ(n) time ([6] page 166).
# Find the longest repeated substrings in Θ(n) time.
# Find the most frequently occurring substrings of a minimum length in Θ(n) time.
# Find the shortest strings from Σ that do not occur in D, in O(n + z) time, if there are z such strings.
# Find the shortest substrings occurring only once in Θ(n) time.
# Find, for each i, the shortest substrings of Si not occurring elsewhere in D in Θ(n) time.
# The suffix tree can be prepared for constant time lowest common ancestor retrieval between nodes in Θ(n) time ([6]
#  chapter 8). You can then also:
# Find the longest common prefix between the suffixes Si[p..ni] and Sj[q..nj] in Θ(1) ([6] page 196).
# Search for a pattern P of length m with at most k mismatches in O(kn + z) time, where z is the number of hits ([6]
#  page 200).
# Find all z maximal palindromes in Θ(n)([6] page 198), or Θ(gn) time if gaps of length g are allowed, or Θ(kn) if k
#  mismatches are allowed ([6] page 201).
# Find all z tandem repeats in O(nlogn + z), and k-mismatch tandem repeats in O(knlog(n / k) + z) ([6] page 204).
# Find the longest substrings common to at least k strings in D for  in Θ(n) time ([6] page 205).
# [edit]Applications
#
# Suffix trees can be used to solve a large number of string problems that occur in text-editing, free-text search,
# computational biology and other application areas.[8] Primary applications include:[8]
# String search, in O(m) complexity, where m is the length of the sub-string (but with initial O(n) time required to
#  build the suffix tree for the string)
# Finding the longest repeated substring
# Finding the longest common substring
# Finding the longest palindrome in a string
# Suffix trees are often used in bioinformatics applications, searching for patterns in DNA or protein sequences (
# which can be viewed as long strings of characters). The ability to search efficiently with mismatches might be
# considered their greatest strength. Suffix trees are also used in data compression; they can be used to find
# repeated data, and can be used for the sorting stage of the Burrows–Wheeler transform. Variants of the LZW
# compression schemes use suffix trees (LZSS). A suffix tree is also used in suffix tree clustering,
# a data clustering algorithm used in some search engines (first introduced in [9]).
# [edit]Implementation
#
# If each node and edge can be represented in Θ(1) space, the entire tree can be represented in Θ(n) space. The
# total length of all the strings on all of the edges in the tree is O(n2), but each edge can be stored as the
# position and length of a substring of S, giving a total space usage of Θ(n) computer words. The worst-case space
# usage of a suffix tree is seen with a fibonacci word, giving the full 2n nodes.
# An important choice when making a suffix tree implementation is the parent-child relationships between nodes. The
# most common is using linked lists called sibling lists. Each node has a pointer to its first child, and to the
# next node in the child list it is a part of. Hash maps, sorted/unsorted arrays (with array doubling), and balanced
#  search trees may also be used, giving different running time properties. We are interested in:
# The cost of finding the child on a given character.
# The cost of inserting a child.
# The cost of enlisting all children of a node (divided by the number of children in the table below).
# Let σ be the size of the alphabet. Then you have the following costs:
# Lookup	Insertion	Traversal
# Sibling lists / unsorted arrays	O(σ)	Θ(1)	Θ(1)
# Hash maps	Θ(1)	Θ(1)	O(σ)
# Balanced search tree	O(logσ)	O(logσ)	O(1)
# Sorted arrays	O(logσ)	O(σ)	O(1)
# Hash maps + sibling lists	O(1)	O(1)	O(1)
# Note that the insertion cost is amortised, and that the costs for hashing are given perfect hashing.
# The large amount of information in each edge and node makes the suffix tree very expensive, consuming about ten to
#  twenty times the memory size of the source text in good implementations. The suffix array reduces this
# requirement to a factor of four, and researchers have continued to find smaller indexing structures.
# [edit]External construction
#
# Suffix trees quickly outgrow the main memory on standard machines for sequence collections in the order of
# gigabytes. As such, their construction calls for external memory approaches.
# There are theoretical results for constructing suffix trees in external memory. The algorithm by Farach et al. [
# 10] is theoretically optimal, with an I/O complexity equal to that of sorting. However, as discussed for example
# in ,[11] the overall intricacy of this algorithm has prevented, so far, its practical implementation.
# On the other hand, there have been practical works for constructing disk-based suffix trees which scale to (few)
# GB/hours. The state of the art methods are TDD ,[12] TRELLIS [13] , DiGeST ,[14] and B2ST .[15]
# TDD and TRELLIS scale up to the entire human genome – approximately 3GB – resulting in a disk-based suffix tree of
#  a size in the tens of gigabytes,.[12][13] However, these methods cannot handle efficiently collections of
# sequences exceeding 3GB.[14] DiGeST performs significantly better and is able to handle collections of sequences
# in the order of 6GB in about 6 hours.[14] The source code and documentation for the latter is available from [16]
# . All these methods can efficiently build suffix trees for the case when the tree does not fit in main memory,
# but the input does. The most recent method, B2ST,[15] scales to handle inputs that do not fit in main memory.
# [edit]See also
#
# Suffix array
# Generalised suffix tree
# [edit]References
#
# ^ P. Weiner (1973). "Linear pattern matching algorithm". 14th Annual IEEE Symposium on Switching and Automata
# Theory. pp. 1–11. doi:10.1109/SWAT.1973.13.
# ^ Edward M. McCreight (1976). "A Space-Economical Suffix Tree Construction Algorithm". Journal of the ACM 23 (2):
# 262–272. doi:10.1145/321941.321946.
# ^ E. Ukkonen (1995). "On-line construction of suffix trees". Algorithmica 14 (3): 249–260. doi:10.1007/BF01206331.
# ^ R. Giegerich and S. Kurtz (1997). "From Ukkonen to McCreight and Weiner: A Unifying View of Linear-Time Suffix
# Tree Construction". Algorithmica 19 (3): 331–353. doi:10.1007/PL00009177.
# ^ a b M. Farach (1997). "Optimal Suffix Tree Construction with Large Alphabets". FOCS: 137–143.
# ^ a b c d e f g h i j k l m n Gusfield, Dan (1999) [1997]. Algorithms on Strings, Trees and Sequences: Computer
# Science and Computational Biology. USA: Cambridge University Press. ISBN 0-521-58519-8.
# ^ Ricardo A. Baeza-Yates and Gaston H. Gonnet (1996). "Fast text searching for regular expressions or automaton
# searching on tries". Journal of the ACM (ACM Press) 43 (6): 915–936. doi:10.1145/235809.235810.
# ^ a b Allison, L.. "Suffix Trees". Retrieved 2008-10-14.
# ^ Oren Zamir and Oren Etzioni (1998). "Web document clustering: a feasibility demonstration". SIGIR '98:
# Proceedings of the 21st annual international ACM SIGIR conference on Research and development in information
# retrieval. ACM. pp. 46–54.
# ^ Martin Farach-Colton, Paolo Ferragina, S. Muthukrishnan (2000). "On the sorting-complexity of suffix tree
# construction.". J. Acm 47(6) 47 (6): 987–1011. doi:10.1145/355541.355547.
# ^ Smyth, William (2003). Computing Patterns in Strings. Addison-Wesley.
# ^ a b Sandeep Tata, Richard A. Hankins, and Jignesh M. Patel (2003). "Practical Suffix Tree Construction". VLDB
# '03: Proceedings of the 30th International Conference on Very Large Data Bases. Morgan Kaufmann. pp. 36–47.
# ^ a b Benjarath Phoophakdee and Mohammed J. Zaki (2007). "Genome-scale disk-based suffix tree indexing". SIGMOD
# '07: Proceedings of the ACM SIGMOD International Conference on Management of Data. ACM. pp. 833–844.
# ^ a b c Marina Barsky, Ulrike Stege, Alex Thomo, and Chris Upton (2008). "A new method for indexing genomes using
# on-disk suffix trees". CIKM '08: Proceedings of the 17th ACM Conference on Information and Knowledge Management.
# ACM. pp. 649–658.
# ^ a b Marina Barsky, Ulrike Stege, Alex Thomo, and Chris Upton (2009). "Suffix trees for very large genomic
# sequences". CIKM '09: Proceedings of the 18th ACM Conference on Information and Knowledge Management. ACM.
# ^ "The disk-based suffix tree for pattern search in sequenced genomes". Retrieved 2009-10-15.
# [edit]External links
# """
