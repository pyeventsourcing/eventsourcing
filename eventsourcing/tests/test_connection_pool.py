from abc import ABC, abstractmethod
from collections import deque
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from itertools import count
from threading import Condition, Event, Lock, Semaphore, Thread, Timer
from time import sleep, time
from typing import Deque, List, Optional
from unittest import TestCase

from eventsourcing.persistence import PersistenceError


class Cursor(ABC):
    @abstractmethod
    def execute(self, statement):
        pass

    @abstractmethod
    def fetchall(self):
        pass


class Connection(ABC):
    def __init__(self, max_age: Optional[float] = None):
        self._closed = False
        self._closing = Event()
        self.in_use = Lock()
        self.in_use.acquire()
        if max_age is not None:
            self._max_age_timer: Optional[Timer] = Timer(
                interval=max_age,
                function=self._close_on_timer,
            )
            self._max_age_timer.start()

    @property
    def closed(self):
        return self._closed

    @property
    def closing(self):
        return self._closing.is_set()

    @abstractmethod
    def commit(self):
        pass

    @abstractmethod
    def rollback(self):
        pass

    @abstractmethod
    def cursor(self) -> Cursor:
        pass

    @abstractmethod
    def close(self):
        self._closed = True
        if self._max_age_timer:
            self._max_age_timer.cancel()
        if self.in_use.locked():
            self.in_use.release()

    def _close_on_timer(self):
        self._closing.set()
        with self.in_use:
            if not self._closed:
                self.close()


class DummyCursor(Cursor):
    def __init__(self):
        self._closed = False
        self._results = None

    def execute(self, statement: str):
        if self._closed:
            raise PersistenceError
        assert statement == "SELECT 1"
        self._results = [[1]]

    def fetchall(self):
        if self._closed:
            raise PersistenceError
        results = self._results
        self._results = None
        return results

    def close(self):
        self._closed = True


class DummyConnection(Connection):
    def __init__(self, max_age: Optional[int] = None):
        super().__init__(max_age=max_age)
        self._cursors: List[DummyCursor] = []
        self._closed_on_server = False

    def commit(self):
        if self.closed:
            raise Exception("Closed")

    def rollback(self):
        if self.closed:
            raise Exception("Closed")

    def cursor(self):
        curs = DummyCursor()
        self._cursors.append(curs)
        if self._closed or self._closed_on_server:
            curs.close()
        return curs

    def close(self):
        for curs in self._cursors:
            curs.close()
        self._closed = True

    def close_on_server(self):
        self._closed_on_server = True


class ConnectionPoolClosed(Exception):
    pass


class ConnectionNotFromPool(Exception):
    pass


class ConnectionPool(ABC):
    def __init__(
        self,
        pool_size: int = 1,
        max_overhead: int = 0,
        max_age: Optional[float] = None,
        pre_ping=False,
    ):
        self._pool_size = pool_size
        self._max_overhead = max_overhead
        self._max_age = max_age
        self._pre_ping = pre_ping
        self._pool: Deque[Connection] = deque()
        self._in_use = dict()
        self._semaphore = Semaphore()
        self._condition = Condition()
        self._closed = False

    @property
    def num_in_use(self) -> int:
        with self._condition:
            return self._num_in_use

    @property
    def _num_in_use(self) -> int:
        return len(self._in_use)

    @property
    def num_in_pool(self) -> int:
        with self._condition:
            return self._num_in_pool

    @property
    def _num_in_pool(self) -> int:
        return len(self._pool)

    @property
    def _is_pool_full(self):
        return self._num_in_pool >= self._pool_size

    @property
    def _is_use_full(self):
        return self._num_in_use < self._pool_size + self._max_overhead

    def get_connection(self, timeout: float = 0.0) -> Connection:
        if self._closed:
            raise ConnectionPoolClosed
        started = time()
        with self._semaphore:
            return self._get_connection(
                timeout=self._remaining_timeout(timeout, started)
            )

    def _get_connection(self, timeout: float = 0.0) -> Connection:
        started = time()
        with self._condition:
            try:
                conn = self._pool.popleft()
            except IndexError:
                if self._is_use_full:
                    conn = self._create_connection()
                    self._in_use[id(conn)] = conn
                    return conn
                else:
                    if self._condition.wait(
                        timeout=self._remaining_timeout(timeout, started)
                    ):
                        return self._get_connection(
                            timeout=self._remaining_timeout(timeout, started)
                        )
                    else:
                        raise ConnectionPoolExhausted("Pool is exhausted") from None

            else:
                if conn.closing or not conn.in_use.acquire(blocking=False):
                    return self._get_connection(
                        timeout=self._remaining_timeout(timeout, started)
                    )
                elif conn.closed:
                    return self._get_connection(
                        timeout=self._remaining_timeout(timeout, started)
                    )
                elif self._pre_ping:
                    try:
                        conn.cursor().execute("SELECT 1")
                    except PersistenceError:
                        return self._get_connection(
                            timeout=self._remaining_timeout(timeout, started)
                        )
                self._in_use[id(conn)] = conn
                return conn

    @staticmethod
    def _remaining_timeout(timeout, started):
        return max(0.0, timeout + started - time())

    def put_connection(self, conn):
        with self._condition:
            if self._closed:
                try:
                    if not conn.closed:
                        conn.close()
                finally:
                    raise ConnectionPoolClosed("Pool is closed")

            try:
                del self._in_use[id(conn)]
            except KeyError:
                raise ConnectionNotFromPool(
                    "Connection not in use in this pool"
                ) from None
            try:
                if not conn.closed:
                    if conn.closing or self._is_pool_full:
                        conn.close()
                    else:
                        self._pool.append(conn)
            finally:
                conn.in_use.release()
                self._condition.notify_all()

    @abstractmethod
    def _create_connection(self) -> Connection:
        pass

    def close(self):
        with self._condition:
            if self._closed:
                raise ConnectionPoolClosed
            for conn in self._in_use.values():
                conn.close()
            while True:
                try:
                    conn = self._pool.popleft()
                except IndexError:
                    break
                else:
                    conn.close()
            self._closed = True


class DummyConnectionPool(ConnectionPool):
    def _create_connection(self) -> Connection:
        return DummyConnection(max_age=self._max_age)


class ConnectionPoolExhausted(Exception):
    pass


class TestConnectionPool(TestCase):
    def test_get_and_put(self):
        pool = DummyConnectionPool(pool_size=2, max_overhead=2)
        self.assertEqual(pool.num_in_use, 0)
        self.assertEqual(pool.num_in_pool, 0)

        conn1 = pool.get_connection()
        self.assertIsInstance(conn1, DummyConnection)
        self.assertEqual(pool.num_in_use, 1)
        self.assertEqual(pool.num_in_pool, 0)

        conn2 = pool.get_connection()
        self.assertEqual(pool.num_in_use, 2)
        self.assertEqual(pool.num_in_pool, 0)

        conn3 = pool.get_connection()
        self.assertEqual(pool.num_in_use, 3)
        self.assertEqual(pool.num_in_pool, 0)

        conn4 = pool.get_connection()
        self.assertEqual(pool.num_in_use, 4)
        self.assertEqual(pool.num_in_pool, 0)

        with self.assertRaises(ConnectionPoolExhausted):
            pool.get_connection(timeout=0)
        self.assertEqual(pool.num_in_use, 4)
        self.assertEqual(pool.num_in_pool, 0)

        pool.put_connection(conn1)
        self.assertEqual(pool.num_in_use, 3)
        self.assertEqual(pool.num_in_pool, 1)
        self.assertFalse(conn1.closed)

        conn5 = pool.get_connection()
        self.assertEqual(pool.num_in_use, 4)
        self.assertEqual(pool.num_in_pool, 0)

        with self.assertRaises(ConnectionPoolExhausted):
            pool.get_connection(timeout=0)

        pool.put_connection(conn2)
        self.assertEqual(pool.num_in_use, 3)
        self.assertEqual(pool.num_in_pool, 1)
        self.assertFalse(conn2.closed)

        pool.put_connection(conn3)
        self.assertEqual(pool.num_in_use, 2)
        self.assertEqual(pool.num_in_pool, 2)
        self.assertFalse(conn3.closed)

        pool.put_connection(conn4)
        self.assertEqual(pool.num_in_use, 1)
        self.assertEqual(pool.num_in_pool, 2)
        self.assertTrue(conn4.closed)

        pool.put_connection(conn5)
        self.assertEqual(pool.num_in_use, 0)
        self.assertEqual(pool.num_in_pool, 2)
        self.assertTrue(conn5.closed)

        # Do it all again.
        conn6 = pool.get_connection()
        self.assertEqual(pool.num_in_use, 1)
        self.assertEqual(pool.num_in_pool, 1)

        conn7 = pool.get_connection()
        self.assertEqual(pool.num_in_use, 2)
        self.assertEqual(pool.num_in_pool, 0)

        conn8 = pool.get_connection()
        self.assertIsInstance(conn3, DummyConnection)
        self.assertEqual(pool.num_in_use, 3)
        self.assertEqual(pool.num_in_pool, 0)

        conn9 = pool.get_connection()
        self.assertIsInstance(conn4, DummyConnection)
        self.assertEqual(pool.num_in_use, 4)
        self.assertEqual(pool.num_in_pool, 0)

        with self.assertRaises(ConnectionPoolExhausted):
            pool.get_connection(timeout=0)
        self.assertEqual(pool.num_in_use, 4)
        self.assertEqual(pool.num_in_pool, 0)

        pool.put_connection(conn6)
        self.assertEqual(pool.num_in_use, 3)
        self.assertEqual(pool.num_in_pool, 1)
        self.assertFalse(conn6.closed)

        conn10 = pool.get_connection()
        self.assertEqual(pool.num_in_use, 4)
        self.assertEqual(pool.num_in_pool, 0)

        with self.assertRaises(ConnectionPoolExhausted):
            pool.get_connection(timeout=0)

        pool.put_connection(conn7)
        self.assertEqual(pool.num_in_use, 3)
        self.assertEqual(pool.num_in_pool, 1)
        self.assertFalse(conn7.closed)

        pool.put_connection(conn8)
        self.assertEqual(pool.num_in_use, 2)
        self.assertEqual(pool.num_in_pool, 2)
        self.assertFalse(conn8.closed)

        pool.put_connection(conn9)
        self.assertEqual(pool.num_in_use, 1)
        self.assertEqual(pool.num_in_pool, 2)
        self.assertTrue(conn9.closed)

        pool.put_connection(conn10)
        self.assertEqual(pool.num_in_use, 0)
        self.assertEqual(pool.num_in_pool, 2)
        self.assertTrue(conn10.closed)

    def test_connection_not_from_pool(self):
        pool = DummyConnectionPool(pool_size=2, max_overhead=2)
        with self.assertRaises(ConnectionNotFromPool):
            pool.put_connection(DummyConnection())

    def test_close_before_returning(self):
        pool = DummyConnectionPool(pool_size=2, max_overhead=2)
        self.assertEqual(pool.num_in_use, 0)
        self.assertEqual(pool.num_in_pool, 0)

        conn1 = pool.get_connection()
        self.assertEqual(pool.num_in_use, 1)
        self.assertEqual(pool.num_in_pool, 0)

        conn1.close()
        pool.put_connection(conn1)
        self.assertEqual(pool.num_in_use, 0)
        self.assertEqual(pool.num_in_pool, 0)

    def test_close_after_returning_without_pre_ping(self):
        pool = DummyConnectionPool(pool_size=1, max_overhead=0)

        conn1 = pool.get_connection()
        curs = conn1.cursor()
        self.assertEqual(curs.fetchall(), None)
        curs.execute("SELECT 1")
        self.assertEqual(curs.fetchall(), [[1]])

        pool.put_connection(conn1)
        conn1.close()
        self.assertEqual(pool.num_in_use, 0)
        self.assertEqual(pool.num_in_pool, 1)

        conn1 = pool.get_connection()
        self.assertFalse(conn1.closed)

        conn1.cursor().execute("SELECT 1")

    def test_close_on_server_after_returning_without_pre_ping(self):
        pool = DummyConnectionPool(pool_size=1, max_overhead=0)

        conn1 = pool.get_connection()
        curs = conn1.cursor()
        self.assertEqual(curs.fetchall(), None)
        curs.execute("SELECT 1")
        self.assertEqual(curs.fetchall(), [[1]])

        pool.put_connection(conn1)
        assert isinstance(conn1, DummyConnection)
        conn1.close_on_server()
        self.assertEqual(pool.num_in_use, 0)
        self.assertEqual(pool.num_in_pool, 1)

        conn1 = pool.get_connection()
        self.assertFalse(conn1.closed)

        with self.assertRaises(PersistenceError):
            conn1.cursor().execute("SELECT 1")

    def test_close_on_server_after_returning_with_pre_ping(self):
        pool = DummyConnectionPool(pool_size=1, max_overhead=0, pre_ping=True)

        conn1 = pool.get_connection()
        pool.put_connection(conn1)
        assert isinstance(conn1, DummyConnection)
        conn1.close_on_server()
        self.assertEqual(pool.num_in_use, 0)
        self.assertEqual(pool.num_in_pool, 1)

        conn2 = pool.get_connection()
        self.assertFalse(conn2.closed)

        curs = conn2.cursor()
        curs.execute("SELECT 1")
        self.assertEqual(curs.fetchall(), [[1]])

    def test_max_age(self):
        pool = DummyConnectionPool(max_age=0.05)

        # Timer fires after conn returned to pool.
        conn1 = pool.get_connection()
        self.assertFalse(conn1.closed)
        self.assertFalse(conn1.closing)
        pool.put_connection(conn1)
        self.assertEqual(pool.num_in_pool, 1)
        sleep(0.1)
        self.assertTrue(conn1.closed)

        # Pool returns a new connection.
        conn2 = pool.get_connection()
        self.assertEqual(pool.num_in_pool, 0)
        self.assertFalse(conn2.closed)
        self.assertFalse(conn2.closing)
        self.assertNotEqual(id(conn1), id(conn2))
        self.assertEqual(pool.num_in_pool, 0)

        # Timer fires before conn returned to pool.
        sleep(0.1)
        self.assertFalse(conn2.closed)
        self.assertTrue(conn2.closing)
        self.assertEqual(pool.num_in_pool, 0)
        pool.put_connection(conn2)
        self.assertEqual(pool.num_in_pool, 0)
        sleep(0.05)
        self.assertTrue(conn1.closed)

        # Pool returns another new connection.
        conn3 = pool.get_connection()
        self.assertFalse(conn3.closed)
        self.assertFalse(conn3.closing)
        self.assertNotEqual(id(conn2), id(conn3))
        pool.put_connection(conn3)

    def test_get_with_timeout(self):
        pool = DummyConnectionPool(pool_size=1, max_overhead=0)
        conn1 = pool.get_connection(timeout=1)

        started = time()
        with self.assertRaises(ConnectionPoolExhausted):
            pool.get_connection(timeout=0)
        ended = time()
        self.assertLess(ended - started, 0.1)

        started = time()
        with self.assertRaises(ConnectionPoolExhausted):
            pool.get_connection(timeout=0.1)
        ended = time()
        self.assertGreater(ended - started, 0.1)

        getting_conn2 = Event()
        got_conn2 = Event()

        def put_conn1():
            getting_conn2.wait()
            sleep(0.05)
            pool.put_connection(conn1)

        def get_conn2():
            getting_conn2.set()
            pool.get_connection(timeout=0.1)
            got_conn2.set()

        thread1 = Thread(target=put_conn1, daemon=True)
        thread1.start()

        thread2 = Thread(target=get_conn2, daemon=True)
        thread2.start()

        self.assertTrue(got_conn2.wait(timeout=0.3))

    def test_close_pool(self):
        pool = DummyConnectionPool(pool_size=2, max_overhead=1)
        conn1 = pool.get_connection(timeout=1)
        conn2 = pool.get_connection(timeout=1)
        conn3 = pool.get_connection(timeout=1)
        pool.put_connection(conn2)
        pool.close()
        self.assertTrue(conn1.closed)
        self.assertTrue(conn2.closed)
        self.assertTrue(conn3.closed)

    def test_fairness_1_0_pre_ping_false(self):
        self._test_fairness(pool_size=1, max_overhead=0, pre_ping=False)

    def test_fairness_1_0_pre_ping_true(self):
        self._test_fairness(pool_size=1, max_overhead=0, pre_ping=True)

    def test_fairness_1_1_pre_ping_false(self):
        self._test_fairness(pool_size=1, max_overhead=1, pre_ping=False)

    def test_fairness_1_2_pre_ping_true(self):
        self._test_fairness(pool_size=1, max_overhead=1, pre_ping=True)

    def test_fairness_2_0_pre_ping_false(self):
        self._test_fairness(pool_size=2, max_overhead=0, pre_ping=False)

    def test_fairness_3_0_pre_ping_false(self):
        self._test_fairness(pool_size=3, max_overhead=0, pre_ping=False)

    def test_fairness_2_2_pre_ping_false(self):
        self._test_fairness(pool_size=2, max_overhead=2, pre_ping=False)

    def test_fairness_2_2_pre_ping_true(self):
        self._test_fairness(pool_size=2, max_overhead=2, pre_ping=True)

    def test_fairness_3_2_pre_ping_false(self):
        self._test_fairness(pool_size=3, max_overhead=2, pre_ping=False)

    def test_fairness_3_2_pre_ping_true(self):
        self._test_fairness(pool_size=3, max_overhead=2, pre_ping=True)

    def test_fairness_20_0_pre_ping_false(self):
        self._test_fairness(pool_size=20, max_overhead=0, pre_ping=False)

    def _test_fairness(self, pool_size=1, max_overhead=1, pre_ping=True):
        connection_pool = DummyConnectionPool(
            pool_size=pool_size, max_overhead=max_overhead, pre_ping=pre_ping
        )

        num_threads = 5
        num_gets = 5
        hold_connection_for = 0.1
        expected_wait_periods = num_threads - 1
        timeout_get_connection = (
            (expected_wait_periods * hold_connection_for) + 0.1
        ) * 1.1

        self.counter = count()

        thread_pool = ThreadPoolExecutor(max_workers=num_threads)
        futures = []
        wait_for = None
        is_stopped = Event()
        for k in range(num_threads):
            has_started = Event()
            future = thread_pool.submit(
                self.get_conn,
                name=k,
                num_gets=num_gets,
                pool=connection_pool,
                hold_for=hold_connection_for,
                timeout=timeout_get_connection,
                has_started=has_started,
                wait_for=wait_for,
                pre_ping=pre_ping,
                is_stopped=is_stopped,
                do_close=True,
            )
            wait_for = has_started
            futures.append(future)

        total_timeout = num_gets * (timeout_get_connection + hold_connection_for) * 1.5
        future_wait_started = time()
        for future in futures:
            try:
                future.result(timeout=total_timeout)
            except TimeoutError as e:
                is_stopped.set()
                raise Exception(
                    f"Timed out{time() - future_wait_started}, timeout {total_timeout}"
                ) from e
            except Exception:
                is_stopped.set()
                raise

    def get_conn(
        self,
        name,
        num_gets,
        pool,
        hold_for,
        timeout,
        has_started,
        wait_for,
        pre_ping,
        is_stopped,
        do_close,
    ):
        if wait_for:
            assert wait_for.wait(timeout=1)
        has_started.set()
        print(name, "started")
        for _ in range(num_gets):
            # print(name, "getting connection")
            started = time()
            try:
                conn = pool.get_connection(timeout=timeout)
            except Exception as exp:
                waited_for = time() - started
                msg = f"{name} errored after {waited_for :.3f}, timeout {timeout}"
                print(msg, type(exp))
                raise Exception(msg) from exp
            else:
                waited_for = time() - started
                remaining_until_timeout = timeout - waited_for
                assert conn
                if pre_ping:
                    assert not conn.closed
                j = next(self.counter)
                print(
                    name,
                    "got connection",
                    j,
                    "after",
                    f"{waited_for :.3f}",
                    f"{remaining_until_timeout :.3f}",
                )
                assert pool.num_in_use <= pool._pool_size + pool._max_overhead
                assert pool.num_in_pool <= pool._pool_size
                # print("num used connections:", pool.num_in_use)
                if not ((j + 1) % 4) and do_close:
                    print("closing connection", j, "before returning to pool")
                    conn.close()
                sleep(hold_for)
                if not ((j + 3) % 4) and do_close:
                    print("closing connection", j, "after returning to pool")
                    conn.close()
                pool.put_connection(conn)
                # sleep(0.001)
            if is_stopped.is_set():
                print(name, "stopping early....")
                return

            # print(name, "put connection", j)
        print(name, "finished")

    # def test_lock_acquire


_print = print

print_lock = Lock()


def print(*args):
    with print_lock:
        _print(*args)
