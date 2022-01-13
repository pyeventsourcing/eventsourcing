from unittest import TestCase

from eventsourcing.application import Cache, LRUCache


class TestCache(TestCase):
    def test_put_get(self):
        cache = Cache()

        with self.assertRaises(KeyError):
            cache.get(1)

        cache.put(1, 1)
        self.assertEqual(cache.get(1), 1)

        cache.put(2, 2)
        self.assertEqual(1, cache.get(1))
        self.assertEqual(2, cache.get(2))

        cache.put(3, 3)
        self.assertEqual(3, cache.get(3))
        self.assertEqual(2, cache.get(2))
        self.assertEqual(1, cache.get(1))

        cache.put(1, 2)
        self.assertEqual(2, cache.get(1))
        cache.put(1, 3)
        self.assertEqual(3, cache.get(1))

        cache.get(1, evict=True)
        with self.assertRaises(KeyError):
            cache.get(1)

        cache.put(1, None)
        with self.assertRaises(KeyError):
            cache.get(1)


class TestLRUCache(TestCase):
    def test_put_get(self):
        cache = LRUCache(maxsize=2)

        with self.assertRaises(KeyError):
            cache.get(1)

        evicted = cache.put(1, 1)
        self.assertEqual(evicted, (None, None))
        self.assertEqual(cache.get(1), 1)

        evicted = cache.put(2, 2)
        self.assertEqual(evicted, (None, None))
        self.assertEqual(1, cache.get(1))
        self.assertEqual(2, cache.get(2))

        evicted = cache.put(3, 3)
        self.assertEqual(evicted, (1, 1))

        self.assertEqual(3, cache.get(3))
        self.assertEqual(2, cache.get(2))

        cache.put(1, 1)
        self.assertEqual(1, cache.get(1))
        cache.put(1, 2)
        self.assertEqual(2, cache.get(1))
        cache.put(1, 3)
        self.assertEqual(3, cache.get(1))

    def test_put_get_evict_recent(self):
        cache = LRUCache(maxsize=3)

        cache.put(1, 1)
        self.assertEqual(1, cache.get(1))
        self.assertEqual(1, cache.get(1))
        self.assertEqual(1, cache.get(1, evict=True))

        with self.assertRaises(KeyError):
            self.assertEqual(1, cache.get(1))

        cache.put(1, 1)
        cache.put(2, 2)
        cache.put(3, 3)
        evicted = cache.put(4, 4)
        self.assertEqual(evicted, (1, 1))

        self.assertEqual(3, cache.get(3, evict=True))

        evicted = cache.put(5, 5)
        self.assertEqual(evicted, (None, None))

        evicted = cache.put(6, 6)
        self.assertEqual(evicted, (2, 2))

        evicted = cache.put(7, 7)
        self.assertEqual(evicted, (4, 4))

    def test_put_get_evict_oldest(self):
        cache = LRUCache(maxsize=3)

        cache.put(1, 1)
        cache.put(2, 2)
        cache.put(3, 3)
        self.assertEqual(1, cache.get(1, evict=True))

        evicted = cache.put(4, 4)
        self.assertEqual(evicted, (None, None))

        evicted = cache.put(5, 5)
        self.assertEqual(evicted, (2, 2))

        evicted = cache.put(6, 6)
        self.assertEqual(evicted, (3, 3))

        evicted = cache.put(7, 7)
        self.assertEqual(evicted, (4, 4))

    def test_put_get_evict_newest(self):
        cache = LRUCache(maxsize=3)

        cache.put(1, 1)
        cache.put(2, 2)
        cache.put(3, 3)
        self.assertEqual(3, cache.get(3, evict=True))

        evicted = cache.put(4, 4)
        self.assertEqual(evicted, (None, None))

        evicted = cache.put(5, 5)
        self.assertEqual(evicted, (1, 1))

        evicted = cache.put(6, 6)
        self.assertEqual(evicted, (2, 2))

        evicted = cache.put(7, 7)
        self.assertEqual(evicted, (4, 4))
