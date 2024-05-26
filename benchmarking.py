import functools
import logging
import time
import timeit


def benchmark(func):
    """Decorator that prints the execution time of the function"""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        execution_time = end_time - start_time
        logging.info(f"{func.__name__} executed in {execution_time:.4f} seconds")
        return result

    return wrapper


def benchmark_with_repeater(repeats=5):
    """Decorator that runs the function multiple times and logs the average execution time"""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Define a nested function to be passed to timeit
            def timed():
                return func(*args, **kwargs)

            # Measure the execution time
            execution_time = timeit.timeit(timed, number=repeats)
            average_time = execution_time / repeats
            # You can switch to print when logging is suppressed.
            # print(
            logging.info(
                f"{func.__name__} executed {repeats} times with an average time of {average_time:.4f} seconds"
            )

        return wrapper

    return decorator
