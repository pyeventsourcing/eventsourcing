import sys
from threading import Event, Lock, Thread
from time import sleep, time
from typing import Any, List, Optional, Union
from unittest import TestCase

from eventsourcing.persistence import (
    Connection,
    ConnectionNotFromPool,
    ConnectionPool,
    ConnectionPoolClosed,
    ConnectionUnavailable,
    Cursor,
    PersistenceError,
    ProgrammingError,
)


class DummyCursor(Cursor):
    def __init__(self):
        self._closed = False
        self._results = None

    def execute(self, statement: Union[str, bytes], params: Any = None):
        if self._closed:
            raise PersistenceError
        assert statement == "SELECT 1"
        self._results = [[1]]

    def fetchall(self):
        if self._closed:
            raise PersistenceError
        if self._results is None:
            raise ProgrammingError
        return self._results

    def fetchone(self):
        if self._closed:
            raise PersistenceError
        if self._results is None:
            raise ProgrammingError
        return self._results[0]

    def close(self):
        self._closed = True


class DummyConnection(Connection):
    def __init__(self, max_age: Optional[float] = None):
        super().__init__(max_age=max_age)
        self._cursors: List[DummyCursor] = []
        self._closed_on_server = False

    def commit(self):
        if self.closed:
            raise PersistenceError("Closed")

    def rollback(self):
        if self.closed:
            raise PersistenceError("Closed")

    def cursor(self):
        curs = DummyCursor()
        self._cursors.append(curs)
        if self._closed or self._closed_on_server:
            curs.close()
        return curs

    def _close(self):
        for curs in self._cursors:
            curs.close()
        super()._close()

    def close_on_server(self):
        self._closed_on_server = True


class DummyConnectionPool(ConnectionPool):
    def _create_connection(self) -> Connection:
        return DummyConnection(max_age=self.max_age)


class TestConnection(TestCase):
    def tearDown(self) -> None:
        sys.stdout.flush()

    def test_commit_rollback_close(self):
        conn = DummyConnection()
        self.assertFalse(conn.closed)
        self.assertFalse(conn.closing)
        self.assertTrue(conn.in_use.locked())
        conn.commit()
        conn.rollback()
        conn.close()
        self.assertTrue(conn.closed)
        self.assertFalse(conn.closing)

        with self.assertRaises(PersistenceError):
            conn.commit()

        with self.assertRaises(PersistenceError):
            conn.rollback()

    def test_max_age(self):
        conn = DummyConnection(max_age=0)
        sleep(0.01)
        self.assertTrue(conn.closing)
        self.assertFalse(conn.closed)
        conn.in_use.release()
        sleep(0.01)
        self.assertTrue(conn.closed)

    def test_close_on_server(self):
        conn = DummyConnection()
        conn.close_on_server()
        self.assertFalse(conn.closing)
        self.assertFalse(conn.closed)
        with self.assertRaises(PersistenceError):
            conn.cursor().execute("SELECT 1")


class TestConnectionPool(TestCase):
    ProgrammingError = ProgrammingError
    PersistenceError = PersistenceError
    allowed_connecting_time = 0

    def create_pool(
        self,
        pool_size=1,
        max_overflow=0,
        max_age=None,
        pre_ping=False,
        mutually_exclusive_read_write=False,
    ):
        return DummyConnectionPool(
            pool_size=pool_size,
            max_overflow=max_overflow,
            max_age=max_age,
            pre_ping=pre_ping,
            mutually_exclusive_read_write=mutually_exclusive_read_write,
        )

    def close_connection_on_server(self, *connections):
        for conn in connections:
            assert isinstance(conn, DummyConnection)
            conn.close_on_server()

    def test_get_and_put(self):
        pool = self.create_pool(pool_size=2, max_overflow=2)

        self.assertEqual(pool.num_in_use, 0)
        self.assertEqual(pool.num_in_pool, 0)

        conn1 = pool.get_connection()
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

        with self.assertRaises(ConnectionUnavailable):
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

        with self.assertRaises(ConnectionUnavailable):
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
        self.assertEqual(pool.num_in_use, 3)
        self.assertEqual(pool.num_in_pool, 0)

        conn9 = pool.get_connection()
        self.assertEqual(pool.num_in_use, 4)
        self.assertEqual(pool.num_in_pool, 0)

        with self.assertRaises(ConnectionUnavailable):
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

        with self.assertRaises(ConnectionUnavailable):
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
        pool = self.create_pool()
        with self.assertRaises(ConnectionNotFromPool):
            pool.put_connection(pool._create_connection())

    def test_close_before_returning(self):
        pool = self.create_pool()
        self.assertEqual(pool.num_in_use, 0)
        self.assertEqual(pool.num_in_pool, 0)

        conn1 = pool.get_connection()
        self.assertEqual(pool.num_in_use, 1)
        self.assertEqual(pool.num_in_pool, 0)

        conn1.close()
        pool.put_connection(conn1)
        self.assertEqual(pool.num_in_use, 0)
        self.assertEqual(pool.num_in_pool, 0)

    def test_close_after_returning(self):
        pool = self.create_pool()
        conn1 = pool.get_connection()
        pool.put_connection(conn1)
        conn1.close()
        self.assertEqual(pool.num_in_use, 0)
        self.assertEqual(pool.num_in_pool, 1)
        conn1 = pool.get_connection()
        self.assertFalse(conn1.closed)

    def test_close_on_server_after_returning_without_pre_ping(self):
        pool = self.create_pool()

        conn1 = pool.get_connection()
        curs = conn1.cursor()
        with self.assertRaises(self.ProgrammingError):
            self.assertEqual(curs.fetchall(), None)
        curs.execute("SELECT 1")
        self.assertEqual(curs.fetchall(), [[1]])

        pool.put_connection(conn1)
        self.close_connection_on_server(conn1)
        self.assertEqual(pool.num_in_use, 0)
        self.assertEqual(pool.num_in_pool, 1)

        conn1 = pool.get_connection()
        self.assertFalse(conn1.closed)

        with self.assertRaises(self.PersistenceError):
            conn1.cursor().execute("SELECT 1")

    def test_close_on_server_after_returning_with_pre_ping(self):
        pool = self.create_pool(pre_ping=True)

        conn1 = pool.get_connection()
        pool.put_connection(conn1)
        self.close_connection_on_server(conn1)
        self.assertEqual(pool.num_in_use, 0)
        self.assertEqual(pool.num_in_pool, 1)

        conn2 = pool.get_connection()
        self.assertFalse(conn2.closed)

        curs = conn2.cursor()
        curs.execute("SELECT 1")
        self.assertEqual(curs.fetchall(), [[1]])

    def test_max_age(self):
        pool = self.create_pool(max_age=0.2)

        # Timer fires after conn returned to pool.
        conn1 = pool.get_connection()
        self.assertFalse(conn1.closed)
        self.assertFalse(conn1.closing)
        pool.put_connection(conn1)
        self.assertEqual(pool.num_in_pool, 1)
        sleep(0.3)
        self.assertTrue(conn1.closed)
        self.assertTrue(conn1.closing)

        # Pool returns a new connection.
        conn2 = pool.get_connection()
        self.assertEqual(pool.num_in_pool, 0)
        self.assertFalse(conn2.closed)
        self.assertFalse(conn2.closing)
        self.assertNotEqual(id(conn1), id(conn2))
        self.assertEqual(pool.num_in_pool, 0)

        # Timer fires before conn returned to pool.
        sleep(0.3)
        self.assertFalse(conn2.closed)
        self.assertTrue(conn2.closing)
        self.assertEqual(pool.num_in_pool, 0)
        pool.put_connection(conn2)
        self.assertEqual(pool.num_in_pool, 0)
        sleep(0.1)
        self.assertTrue(conn1.closed)

        # Pool returns another new connection.
        conn3 = pool.get_connection()
        self.assertFalse(conn3.closed)
        self.assertFalse(conn3.closing)
        self.assertNotEqual(id(conn2), id(conn3))
        pool.put_connection(conn3)

    def test_get_with_timeout(self):
        pool = self.create_pool()

        # Get a connection.
        conn1 = pool.get_connection()

        # Check request for a second connection times out immediately.
        started = time()
        with self.assertRaises(ConnectionUnavailable):
            pool.get_connection(timeout=0)
        ended = time()
        self.assertLess(ended - started, 0.1)

        # Check request for a second connection times out after delay.
        started = time()
        with self.assertRaises(ConnectionUnavailable):
            pool.get_connection(timeout=0.1)
        ended = time()
        self.assertGreater(ended - started, 0.1)

        # Check request for second connection is kept waiting
        # but doesn't timeout if first connection is returned.
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
        thread2 = Thread(target=get_conn2, daemon=True)
        thread1.start()
        thread2.start()
        self.assertTrue(got_conn2.wait(timeout=0.3))

    def test_close_pool(self):
        # Get three connections and return one of them.
        pool = self.create_pool(pool_size=2, max_overflow=1)
        conn1 = pool.get_connection()
        conn2 = pool.get_connection()
        conn3 = pool.get_connection()
        pool.put_connection(conn1)

        # Close pool.
        pool.close()

        # All connections are closed (returned and those in use).
        self.assertTrue(conn1.closed)
        self.assertTrue(conn2.closed)
        self.assertTrue(conn3.closed)

        # Raises error when putting connection after pool closed.
        with self.assertRaises(ConnectionPoolClosed):
            pool.put_connection(conn2)

        with self.assertRaises(ConnectionPoolClosed):
            pool.put_connection(conn3)

        # Raises error when getting connection after pool closed.
        with self.assertRaises(ConnectionPoolClosed):
            pool.get_connection()

        # Can call close() twice.
        pool.close()

    def test_fairness(self):
        pool_size = 1
        num_threads = 5
        num_gets = 5

        # Pre-initialise pool.
        pool = self.create_pool(pool_size=pool_size, max_overflow=0, pre_ping=False)
        connections = []
        for _ in range(pool_size):
            connections.append(pool.get_connection())
        self.assertEqual(pool.num_in_use, pool_size)
        for conn in connections:
            pool.put_connection(conn)

        is_stopped = Event()
        hold_connection = 0.1
        wait_after_connection = 0.01
        conn_sequence = list()

        deadline = num_threads * num_gets * hold_connection * 10

        class WorkerThread(Thread):
            def __init__(self, name):
                super().__init__(daemon=True)
                self.name = name

            def run(self):
                for _ in range(num_gets):
                    if is_stopped.is_set():
                        break
                    try:
                        conn = pool.get_connection(timeout=deadline)
                        conn_sequence.append(self.name)
                        sleep(hold_connection)
                        pool.put_connection(conn)
                        sleep(wait_after_connection)
                    except BaseException:
                        is_stopped.set()
                        raise

        names = [str(i) for i in range(num_threads)]
        threads = []
        for name in names:
            thread = WorkerThread(name)
            threads.append(thread)
            sleep(wait_after_connection)
            thread.start()

        for thread in threads:
            thread.join(timeout=deadline)
            self.assertFalse(is_stopped.is_set())

        expected_sequence = names * num_gets
        self.assertEqual(expected_sequence, conn_sequence)

    # def _test_fairness_based_on_timings(
    #     self, pool_size=1, num_threads=20, num_gets=50, max_overflow=0, pre_ping=False
    # ):
    #
    #     connection_pool = self.create_pool(
    #         pool_size=pool_size, max_overflow=max_overflow, pre_ping=pre_ping
    #     )
    #     print("Testing fairness of", connection_pool.__class__.__name__)
    #
    #     # Pre-initialise pool.
    #     connections = []
    #     for _ in range(pool_size):
    #         connections.append(connection_pool.get_connection())
    #     self.assertEqual(connection_pool.num_in_use, pool_size)
    #     for conn in connections:
    #         connection_pool.put_connection(conn)
    #
    #     print(f"Num client threads: {num_threads}")
    #     num_connections = pool_size + max_overflow
    #     print(f"Num connections available: {num_connections}")
    #     max_num_waiting = max(0, num_threads - num_connections)
    #     print(f"Max num waiting: {max_num_waiting}")
    #     expected_wait_periods = ceil(max_num_waiting / (num_connections))
    #     print(
    #         f"Num expected wait periods: {expected_wait_periods}",
    #     )
    #     hold_connection_for = 0.1
    #     wait_between_connections_for = 0.01
    #     print(f"Hold connection for: {hold_connection_for:.1f}s")
    #     print(f"Allowed connecting time: {self.allowed_connecting_time:.4f}s")
    #     connection_deadline = (
    #         expected_wait_periods * hold_connection_for + self.allowed_connecting_time
    #     )
    #     print(
    #         f"Strict connection deadline: {connection_deadline:.4f}s",
    #     )
    #     allowed_deadline_margin = 75  # percent
    #     print(f"Allowed deadline margin: {allowed_deadline_margin}%")
    #     connection_deadline *= 1 + allowed_deadline_margin / 100
    #     print(
    #         f"Actual connection deadline: {connection_deadline:.4f}s",
    #     )
    #
    #     self.counter = count()
    #
    #     thread_pool = ThreadPoolExecutor(max_workers=num_threads)
    #     futures = []
    #     wait_for = None
    #     is_stopped = Event()
    #
    #     debug = False
    #
    #     waited_fors = list()
    #
    #     def get_conn(
    #         name,
    #         has_started,
    #         wait_for,
    #         do_close,
    #     ):
    #         if wait_for:
    #             assert wait_for.wait(timeout=1)
    #         has_started.set()
    #         if debug:
    #             print(name, "started")
    #         for _ in range(num_gets):
    #             # print(name, "getting connection")
    #             started = time()
    #             try:
    #                 conn = connection_pool.get_connection(timeout=connection_deadline)
    #             except Exception as exp:
    #                 is_stopped.set()
    #                 waited_for = time() - started
    #                 msg = (
    #                     f"Thread {name} errored after {waited_for :.4f}s, "
    #                     f"timeout {connection_deadline:.4f}s: {exp}"
    #                 )
    #                 print(msg)
    #                 raise Exception(msg) from exp
    #             else:
    #                 assert conn
    #                 if pre_ping:
    #                     assert not conn.closed
    #                 j = next(self.counter)
    #                 waited_for = time() - started
    #                 if debug:
    #                     # print(
    #                     #     f"Thread {name} got connection {j} after "
    #                     #     f"{waited_for :.3f}s, remaining time before "
    #                     #     f"timeout: {deadline - waited_for  :.3f}"
    #                     # )
    #                     print(
    #                         f"Thread {name} waited {waited_for:.6f}s to get connection"
    #                     )
    #                 waited_fors.append(waited_for)
    #
    #                 assert (
    #                     connection_pool.num_in_use
    #                     <= connection_pool.pool_size + connection_pool.max_overflow
    #                 )
    #                 assert connection_pool.num_in_pool <= connection_pool.pool_size
    #                 if debug:
    #                     print("num used connections:", connection_pool.num_in_use)
    #                 if not ((j + 1) % 4) and do_close:
    #                     if debug:
    #                         print("closing connection", j, "before returning to pool")
    #                     conn.close()
    #                 sleep(hold_connection_for)
    #                 if not ((j + 3) % 4) and do_close:
    #                     if debug:
    #                         print("closing connection", j, "after returning to pool")
    #                     conn.close()
    #                 connection_pool.put_connection(conn)
    #                 sleep(wait_between_connections_for)
    #             if is_stopped.is_set():
    #                 print(name, "stopping early....")
    #                 return
    #
    #             # print(name, "put connection", j)
    #         if debug:
    #             print(name, "finished")
    #
    #     for k in range(num_threads):
    #         has_started = Event()
    #         future = thread_pool.submit(
    #             get_conn,
    #             name=k,
    #             has_started=has_started,
    #             wait_for=wait_for,
    #             do_close=True,
    #         )
    #         wait_for = has_started
    #         futures.append(future)
    #
    #     total_timeout = (
    #         num_gets
    #         * (connection_deadline + hold_connection_for + wait_between_connections_for)
    #         * 1.5
    #     )
    #     future_wait_started = time()
    #     for future in futures:
    #         try:
    #             future.result(timeout=total_timeout)
    #         except TimeoutError as e:
    #             print("Stopping threads because test timed out...")
    #             is_stopped.set()
    #             thread_pool.shutdown()
    #             raise Exception(
    #                 f"Test timed out after {time() - future_wait_started}s "
    #                 f"(timeout was {total_timeout}s)"
    #             ) from e
    #         except Exception as e:
    #             is_stopped.set()
    #             thread_pool.shutdown()
    #             raise Exception(f"Test stopped after thread pool job error: {e}") from e
    #
    #     max_waited_for = max(waited_fors)
    #     avg_waited_for = sum(waited_fors) / len(waited_fors)
    #     min_waited_for = min(waited_fors)
    #     print(f"Max time to wait for connection: {max_waited_for:.6f}s")
    #     print(f"Avg time to wait for connection: {avg_waited_for:.6f}s")
    #     print(f"Min time to wait for connection: {min_waited_for:.6f}s")
    #     actual_deadline_margin = (
    #         100 * (connection_deadline - max_waited_for) / max_waited_for
    #     )
    #     print(f"Actual deadline margin: {actual_deadline_margin:.0f}%")
    #     print("")
    #     sleep(0.1)

    def test_reader_writer(self):
        self._test_reader_writer_with_mutually_exclusive_read_write()
        self._test_reader_writer_without_mutually_exclusive_read_write()

    def _test_reader_writer_with_mutually_exclusive_read_write(self):
        pool = self.create_pool(pool_size=3, mutually_exclusive_read_write=True)
        self.assertTrue(pool._mutually_exclusive_read_write)

        self.assertEqual(0, pool._num_writers)
        self.assertEqual(0, pool._num_readers)

        # Get writer.
        writer_conn = pool.get_connection(is_writer=True, timeout=0)
        self.assertIs(writer_conn.is_writer, True)

        self.assertEqual(1, pool._num_writers)
        self.assertEqual(0, pool._num_readers)

        # Return writer.
        pool.put_connection(writer_conn)

        self.assertEqual(0, pool._num_writers)
        self.assertEqual(0, pool._num_readers)

        # Get two readers.
        reader_conn1 = pool.get_connection(is_writer=False)
        reader_conn2 = pool.get_connection(is_writer=False)

        self.assertIs(reader_conn1.is_writer, False)
        self.assertIs(reader_conn2.is_writer, False)

        self.assertEqual(0, pool._num_writers)
        self.assertEqual(2, pool._num_readers)

        # Fail to get writer.
        with self.assertRaises(ConnectionUnavailable) as cm:
            pool.get_connection(is_writer=True, timeout=0)
        self.assertEqual(cm.exception.args[0], "Timed out waiting for return of reader")

        self.assertEqual(0, pool._num_writers)
        self.assertEqual(2, pool._num_readers)

        # Return readers to pool.
        pool.put_connection(reader_conn1)
        pool.put_connection(reader_conn2)

        self.assertEqual(0, pool._num_writers)
        self.assertEqual(0, pool._num_readers)

        # Get writer.
        writer_conn = pool.get_connection(is_writer=True, timeout=0)

        self.assertEqual(1, pool._num_writers)
        self.assertEqual(0, pool._num_readers)

        # Fail to get reader.
        with self.assertRaises(ConnectionUnavailable) as cm:
            pool.get_connection(is_writer=False, timeout=0)
        self.assertEqual(cm.exception.args[0], "Timed out waiting for return of writer")

        # Fail to get writer.
        with self.assertRaises(ConnectionUnavailable) as cm:
            pool.get_connection(is_writer=True, timeout=0)
        self.assertEqual(cm.exception.args[0], "Timed out waiting for return of writer")

        self.assertEqual(1, pool._num_writers)
        self.assertEqual(0, pool._num_readers)

        # Return writer.
        pool.put_connection(writer_conn)

        self.assertEqual(0, pool._num_writers)
        self.assertEqual(0, pool._num_readers)

        # Get and put another writer.
        writer_conn = pool.get_connection(is_writer=True)
        pool.put_connection(writer_conn)

        self.assertEqual(0, pool._num_writers)
        self.assertEqual(0, pool._num_readers)

        # Get two readers.
        reader_conn1 = pool.get_connection(is_writer=False)
        reader_conn2 = pool.get_connection(is_writer=False)

        self.assertEqual(0, pool._num_writers)
        self.assertEqual(2, pool._num_readers)

        pool.put_connection(reader_conn1)
        pool.put_connection(reader_conn2)

        self.assertEqual(0, pool._num_writers)
        self.assertEqual(0, pool._num_readers)

    def _test_reader_writer_without_mutually_exclusive_read_write(self):
        pool = self.create_pool(pool_size=3, mutually_exclusive_read_write=False)
        self.assertFalse(pool._mutually_exclusive_read_write)

        self.assertEqual(0, pool._num_writers)
        self.assertEqual(0, pool._num_readers)

        # Get writer.
        writer_conn = pool.get_connection(is_writer=True, timeout=0)
        self.assertIs(writer_conn.is_writer, True)

        self.assertEqual(1, pool._num_writers)
        self.assertEqual(0, pool._num_readers)

        # Get two readers.
        reader_conn1 = pool.get_connection(is_writer=False)
        reader_conn2 = pool.get_connection(is_writer=False)

        self.assertIs(reader_conn1.is_writer, False)
        self.assertIs(reader_conn2.is_writer, False)

        self.assertEqual(1, pool._num_writers)
        self.assertEqual(2, pool._num_readers)

        # Fail to get another writer.
        with self.assertRaises(ConnectionUnavailable) as cm:
            pool.get_connection(is_writer=True, timeout=0)
        self.assertEqual(cm.exception.args[0], "Timed out waiting for return of writer")

        self.assertEqual(1, pool._num_writers)
        self.assertEqual(2, pool._num_readers)

        # Return writer.
        pool.put_connection(writer_conn)

        self.assertEqual(0, pool._num_writers)
        self.assertEqual(2, pool._num_readers)

        # Return readers to pool.
        pool.put_connection(reader_conn1)
        pool.put_connection(reader_conn2)

        self.assertEqual(0, pool._num_writers)
        self.assertEqual(0, pool._num_readers)

        # Get two readers.
        pool.get_connection(is_writer=False)
        pool.get_connection(is_writer=False)

        self.assertEqual(0, pool._num_writers)
        self.assertEqual(2, pool._num_readers)

        # Get another writer.
        writer_conn = pool.get_connection(is_writer=True, timeout=0)

        self.assertEqual(1, pool._num_writers)
        self.assertEqual(2, pool._num_readers)

        # Fail to get another writer.
        with self.assertRaises(ConnectionUnavailable) as cm:
            pool.get_connection(is_writer=True, timeout=0)
        self.assertEqual(cm.exception.args[0], "Timed out waiting for return of writer")

        self.assertEqual(1, pool._num_writers)
        self.assertEqual(2, pool._num_readers)

        # Return writer.
        pool.put_connection(writer_conn)

        self.assertEqual(0, pool._num_writers)
        self.assertEqual(2, pool._num_readers)

        # Get and put another writer.
        writer_conn = pool.get_connection(is_writer=True)
        pool.put_connection(writer_conn)

        self.assertEqual(0, pool._num_writers)
        self.assertEqual(2, pool._num_readers)

    def test_semaphore_timeout_branch(self):
        # This test exercises unusual path where waiting for
        # the semaphore times out. This only happens when
        # the timeouts are very short and there are a lot
        # of threads (regardless of whether the pool is
        # exhausted) because Python just can't process
        # everything in time. It would also happen if
        # 'is_writer' is either True or False for a
        # connection request and this request waits
        # for return of reader/writer whilst holding
        # the semaphore, and a later request uses a
        # timeout that is less than that of the
        # blocked request. But anyway, the semaphore
        # request needs to be acquired with a timeout
        # and so the failure to get the semaphore lock
        # needs a branch in the code, and this branch
        # needs to be covered with a test.

        # Create a pool.
        pool = self.create_pool(pool_size=3)

        # Get a writer connection (blocks subsequent writers).
        pool.get_connection(is_writer=True)

        # Block on waiting for a writer connection (holds the semaphore).
        class WriterThread(Thread):
            def run(self):
                try:
                    pool.get_connection(timeout=0.1, is_writer=True)
                except ConnectionUnavailable:
                    pass

        thread = WriterThread()
        thread.start()

        # Wait for semaphore value to be zero.
        while pool._get_semaphore._value != 0:
            sleep(0.001)

        # With a zero timeout, fail to get semaphore.
        with self.assertRaises(ConnectionUnavailable) as cm:
            pool.get_connection(timeout=0)
        self.assertEqual(
            cm.exception.args[0], "Timed out waiting for connection pool semaphore"
        )


_print = print

print_lock = Lock()


def print(*args):
    with print_lock:
        _print(*args)
