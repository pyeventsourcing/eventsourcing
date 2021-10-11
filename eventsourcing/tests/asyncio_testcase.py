try:
    from unittest import IsolatedAsyncioTestCase
except ImportError:
    import asyncio
    import inspect
    from unittest import TestCase

    # Adapted from Python 3.8 (doesn't exist in Python 3.7).
    class IsolatedAsyncioTestCase(TestCase):
        def __init__(self, methodName="runTest"):
            super().__init__(methodName)
            self._asyncioTestLoop = None
            self._asyncioCallsQueue = None

        async def asyncSetUp(self):
            pass

        async def asyncTearDown(self):
            pass

        def addAsyncCleanup(self, func, *args, **kwargs):
            self.addCleanup(*(func, *args), **kwargs)

        def _callSetUp(self):
            self.setUp()
            self._callAsync(self.asyncSetUp)

        def _callTestMethod(self, method):
            self._callMaybeAsync(method)

        def _callTearDown(self):
            self._callAsync(self.asyncTearDown)
            self.tearDown()

        def _callCleanup(self, function, *args, **kwargs):
            self._callMaybeAsync(function, *args, **kwargs)

        def _callAsync(self, func, *args, **kwargs):
            assert self._asyncioTestLoop is not None
            ret = func(*args, **kwargs)
            assert inspect.isawaitable(ret)
            fut = self._asyncioTestLoop.create_future()
            self._asyncioCallsQueue.put_nowait((fut, ret))
            return self._asyncioTestLoop.run_until_complete(fut)

        def _callMaybeAsync(self, func, *args, **kwargs):
            assert self._asyncioTestLoop is not None
            ret = func(*args, **kwargs)
            if inspect.isawaitable(ret):
                fut = self._asyncioTestLoop.create_future()
                self._asyncioCallsQueue.put_nowait((fut, ret))
                return self._asyncioTestLoop.run_until_complete(fut)
            else:
                return ret

        async def _asyncioLoopRunner(self, fut):
            self._asyncioCallsQueue = queue = asyncio.Queue()
            fut.set_result(None)
            while True:
                query = await queue.get()
                queue.task_done()
                if query is None:
                    return
                fut, awaitable = query
                try:
                    ret = await awaitable
                    if not fut.cancelled():
                        fut.set_result(ret)
                except asyncio.CancelledError:
                    raise
                except Exception as ex:
                    if not fut.cancelled():
                        fut.set_exception(ex)

        def _setupAsyncioLoop(self):
            assert self._asyncioTestLoop is None
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.set_debug(True)
            self._asyncioTestLoop = loop
            fut = loop.create_future()
            self._asyncioCallsTask = loop.create_task(self._asyncioLoopRunner(fut))
            loop.run_until_complete(fut)

        def _tearDownAsyncioLoop(self):
            assert self._asyncioTestLoop is not None
            loop = self._asyncioTestLoop
            self._asyncioTestLoop = None
            self._asyncioCallsQueue.put_nowait(None)
            loop.run_until_complete(self._asyncioCallsQueue.join())

            try:
                # cancel all tasks
                to_cancel = asyncio.all_tasks(loop)
                if not to_cancel:
                    return

                for task in to_cancel:
                    task.cancel()

                loop.run_until_complete(
                    asyncio.gather(*to_cancel, loop=loop, return_exceptions=True)
                )

                for task in to_cancel:
                    if task.cancelled():
                        continue
                    if task.exception() is not None:
                        loop.call_exception_handler(
                            {
                                "message": "unhandled exception during test shutdown",
                                "exception": task.exception(),
                                "task": task,
                            }
                        )
                # shutdown asyncgens
                loop.run_until_complete(loop.shutdown_asyncgens())
            finally:
                asyncio.set_event_loop(None)
                loop.close()

        def run(self, result=None):
            self._setupAsyncioLoop()
            try:
                return super().run(result)
            finally:
                self._tearDownAsyncioLoop()
