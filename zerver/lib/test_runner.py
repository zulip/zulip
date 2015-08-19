from django.test.runner import DiscoverRunner

from zerver.lib.cache import bounce_key_prefix_for_testing
from zerver.views.messages import get_sqlalchemy_connection

import os
import time
import unittest


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
    test_module = test.__module__
    test_class = test.__class__.__name__
    test_method = test._testMethodName
    return '%s.%s.%s' % (test_module, test_class, test_method)

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

    print 'Running', test_name
    if not hasattr(test, "_pre_setup"):
        print "somehow the test doesn't have _pre_setup; it may be an import fail."
        print "Here's a debugger. Good luck!"
        import pdb; pdb.set_trace()
    test._pre_setup()

    start_time = time.time()

    test.setUp()
    try:
        test_method()
    except unittest.SkipTest:
        pass
    test.tearDown()

    delay = time.time() - start_time
    enforce_timely_test_completion(test_method, test_name, delay)

    test._post_teardown()

class Runner(DiscoverRunner):
    def __init__(self, *args, **kwargs):
        DiscoverRunner.__init__(self, *args, **kwargs)

    def run_suite(self, suite):
        for test in suite:
            run_test(test)

    def run_tests(self, test_labels, extra_tests=None, **kwargs):
        self.setup_test_environment()
        suite = self.build_suite(test_labels, extra_tests)
        # We have to do the next line to avoid flaky scenarios where we
        # run a single test and getting an SA connection causes data from
        # a Django connection to be rolled back mid-test.
        get_sqlalchemy_connection()
        self.run_suite(suite)
        self.teardown_test_environment()
        print 'DONE!'
        print
