from django.test.simple import DjangoTestSuiteRunner

from zerver.lib.cache import bounce_key_prefix_for_testing

import os
import time


def slow(expected_run_time, slowness_reason):
    '''
    This is a decorate that annotates a test as being "known
    to be slow."  The decorator will set expected_run_time and slowness_reason
    as atributes of the function.  Other code can use this annotation
    as needed, e.g. to exclude these tests in "fast" mode.
    '''
    def decorator(f):
        f.expected_run_time = expected_run_time
        f.slowness_reason = slowness_reason
        return f

    return decorator

def is_known_slow_test(test_method):
    return hasattr(test_method, 'slowness_reason')

def full_test_name(test):
    test_class = test.__class__.__name__
    test_method = test._testMethodName
    return '%s/%s' % (test_class, test_method)

def get_test_method(test):
    return getattr(test, test._testMethodName)

def enforce_timely_test_completion(test_method, test_name, delay):
    if hasattr(test_method, 'expected_run_time'):
        # Allow for tests to run 50% slower than normal due
        # to random variations.
        max_delay = 1.5 * test_method.expected_run_time
    else:
        max_delay = 0.180 # seconds

    # Further adjustments for slow laptops:
    max_delay = max_delay * 3

    if delay > max_delay:
        print 'Test is TOO slow: %s (%.3f s)' % (test_name, delay)

def fast_tests_only():
    return os.environ.get('FAST_TESTS_ONLY', False)

def run_test(test):
    test_method = get_test_method(test)

    if fast_tests_only() and is_known_slow_test(test_method):
        return

    test_name = full_test_name(test)

    bounce_key_prefix_for_testing(test_name)

    print 'Running zerver.%s' % (test_name.replace("/", "."),)
    test._pre_setup()

    start_time = time.time()

    test.setUp()
    test_method()
    test.tearDown()

    delay = time.time() - start_time
    enforce_timely_test_completion(test_method, test_name, delay)

    test._post_teardown()

class Runner(DjangoTestSuiteRunner):
    option_list = ()

    def __init__(self, *args, **kwargs):
        DjangoTestSuiteRunner.__init__(self, *args, **kwargs)

    def run_suite(self, suite):
        for test in suite:
            run_test(test)

    def run_tests(self, test_labels, extra_tests=None, **kwargs):
        self.setup_test_environment()
        suite = self.build_suite(test_labels, extra_tests)
        self.run_suite(suite)
        self.teardown_test_environment()
        print 'DONE!'
        print
