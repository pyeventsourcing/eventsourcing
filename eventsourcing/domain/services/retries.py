import time

from eventsourcing.exceptions import ConcurrencyError


def retry_after_concurrency_error(operation_to_retry, max_attempts=10, wait=0.02, args=()):
    tries = 0
    assert tries <= max_attempts
    while True:
        try:
            operation_to_retry(*args)
            break
        except ConcurrencyError as error:
            tries += 1
            if tries < max_attempts:
                time.sleep(wait * (1 + tries))
                continue
            else:
                raise error
