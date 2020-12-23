# from unittest.case import TestCase
#
# from eventsourcing.domain.services.retries import retry_after_concurrency_error
# from eventsourcing.exceptions import ConcurrencyError
#
#
# class TestRetries(TestCase):
#
#     def setUp(self):
#         self.call_count = 0
#
#     def test_retry_after_concurrency_error_success(self):
#         retry_after_concurrency_error(
#             operation_to_retry=self.raise_concurrency_error,
#         )
#
#     def test_retry_after_concurrency_error_fail(self):
#         with self.assertRaises(ConcurrencyError):
#             retry_after_concurrency_error(
#                 operation_to_retry=self.raise_concurrency_error,
#                 max_attempts=1,
#             )
#
#
#     def raise_concurrency_error(self):
#         if self.call_count < 2:
#             self.call_count += 1
#             raise ConcurrencyError("Just a test")
