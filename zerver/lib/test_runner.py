from __future__ import print_function

from typing import Any, Callable, Iterable, List, Optional, Set, Tuple

from django.test import TestCase
from django.test.runner import DiscoverRunner
from django.test.signals import template_rendered

from zerver.lib.cache import bounce_key_prefix_for_testing
from zerver.lib.sqlalchemy_utils import get_sqlalchemy_connection
from zerver.lib.test_helpers import (
    get_all_templates, write_instrumentation_reports,
    )

import os
import subprocess
import sys
import time
import traceback
import unittest

def slow(slowness_reason):
    # type: (str) -> Callable[[Callable], Callable]
    '''
    This is a decorate that annotates a test as being "known
    to be slow."  The decorator will set expected_run_time and slowness_reason
    as atributes of the function.  Other code can use this annotation
    as needed, e.g. to exclude these tests in "fast" mode.
    '''
    def decorator(f):
        # type: (Any) -> Any
        f.slowness_reason = slowness_reason
        return f

    return decorator

def is_known_slow_test(test_method):
    # type: (Any) -> bool
    return hasattr(test_method, 'slowness_reason')

def full_test_name(test):
    # type: (TestCase) -> str
    test_module = test.__module__
    test_class = test.__class__.__name__
    test_method = test._testMethodName
    return '%s.%s.%s' % (test_module, test_class, test_method)

def get_test_method(test):
    # type: (TestCase) -> Callable[[], None]
    return getattr(test, test._testMethodName)

# Each tuple is delay, test_name, slowness_reason
TEST_TIMINGS = [] # type: List[Tuple[float, str, str]]


def report_slow_tests():
    # type: () -> None
    timings = sorted(TEST_TIMINGS, reverse=True)
    print('SLOWNESS REPORT')
    print(' delay test')
    print(' ----  ----')
    for delay, test_name, slowness_reason in timings[:15]:
        if not slowness_reason:
            slowness_reason = 'UNKNOWN WHY SLOW, please investigate'
        print(' %0.3f %s\n       %s\n' % (delay, test_name, slowness_reason))

    print('...')
    for delay, test_name, slowness_reason in timings[100:]:
        if slowness_reason:
            print(' %.3f %s is not that slow' % (delay, test_name))
            print('      consider removing @slow decorator')
            print('      This may no longer be true: %s' % (slowness_reason,))

def enforce_timely_test_completion(test_method, test_name, delay):
    # type: (Any, str, float) -> None
    if hasattr(test_method, 'slowness_reason'):
        max_delay = 1.1 # seconds
    else:
        max_delay = 0.4 # seconds

    if delay > max_delay:
        print(' ** Test is TOO slow: %s (%.3f s)' % (test_name, delay))

def fast_tests_only():
    # type: () -> bool
    return "FAST_TESTS_ONLY" in os.environ

def run_test(test):
    # type: (TestCase) -> bool
    failed = False
    test_method = get_test_method(test)

    if fast_tests_only() and is_known_slow_test(test_method):
        return failed

    test_name = full_test_name(test)

    bounce_key_prefix_for_testing(test_name)

    print('Running', test_name)
    if not hasattr(test, "_pre_setup"):
        # test_name is likely of the form unittest.loader.ModuleImportFailure.zerver.tests.test_upload
        import_failure_prefix = 'unittest.loader.ModuleImportFailure.'
        if test_name.startswith(import_failure_prefix):
            actual_test_name = test_name[len(import_failure_prefix):]
            print()
            print("Actual test to be run is %s, but import failed." % (actual_test_name,))
            print("Importing test module directly to generate clearer traceback:")
            try:
                command = ["python", "-c", "import %s" % (actual_test_name,)]
                print("Import test command: `%s`" % (' '.join(command),))
                subprocess.check_call(command)
            except subprocess.CalledProcessError:
                print("If that traceback is confusing, try doing the import inside `./manage.py shell`")
                print()
                return True
            print("Import unexpectedly succeeded!  Something is wrong")
            return True
        else:
            print("Test doesn't have _pre_setup; something is wrong.")
            print("Here's a debugger. Good luck!")
            import pdb; pdb.set_trace()
    test._pre_setup()

    start_time = time.time()

    test.setUp()
    try:
        test_method()
    except unittest.SkipTest as e:
        print('Skipped:', e)
    except Exception:
        failed = True
        traceback.print_exc()

    test.tearDown()

    delay = time.time() - start_time
    enforce_timely_test_completion(test_method, test_name, delay)
    slowness_reason = getattr(test_method, 'slowness_reason', '')
    TEST_TIMINGS.append((delay, test_name, slowness_reason))

    test._post_teardown()
    return failed

class Runner(DiscoverRunner):
    def __init__(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        DiscoverRunner.__init__(self, *args, **kwargs)

        # `templates_rendered` holds templates which were rendered
        # in proper logical tests.
        self.templates_rendered = set()  # type: Set[str]
        # `shallow_tested_templates` holds templates which were rendered
        # in `zerver.tests.test_templates`.
        self.shallow_tested_templates = set()  # type: Set[str]
        template_rendered.connect(self.on_template_rendered)

    def on_template_rendered(self, sender, context, **kwargs):
        # type: (Any, Dict[str, Any], **Any) -> None
        if hasattr(sender, 'template'):
            template_name = sender.template.name
            if template_name not in self.templates_rendered:
                if context.get('shallow_tested'):
                    self.shallow_tested_templates.add(template_name)
                else:
                    self.templates_rendered.add(template_name)
                    self.shallow_tested_templates.discard(template_name)

    def get_shallow_tested_templates(self):
        # type: () -> Set[str]
        return self.shallow_tested_templates

    def run_suite(self, suite, fatal_errors=True):
        # type: (Iterable[TestCase], bool) -> bool
        failed = False
        for test in suite:
            # The attributes __unittest_skip__ and __unittest_skip_why__ are undocumented
            if hasattr(test, '__unittest_skip__') and test.__unittest_skip__:
                print('Skipping', full_test_name(test), "(%s)" % (test.__unittest_skip_why__,))
            elif run_test(test):
                failed = True
                if fatal_errors:
                    return failed
        return failed

    def run_tests(self, test_labels, extra_tests=None, **kwargs):
        # type: (List[str], Optional[List[TestCase]], **Any) -> bool
        self.setup_test_environment()
        try:
            suite = self.build_suite(test_labels, extra_tests)
        except AttributeError:
            traceback.print_exc()
            print()
            print("  This is often caused by a test module/class/function that doesn't exist or ")
            print("  import properly. You can usually debug in a `manage.py shell` via e.g. ")
            print("    import zerver.tests.test_messages")
            print("    from zerver.tests.test_messages import StreamMessagesTest")
            print("    StreamMessagesTest.test_message_to_stream")
            print()
            sys.exit(1)
        # We have to do the next line to avoid flaky scenarios where we
        # run a single test and getting an SA connection causes data from
        # a Django connection to be rolled back mid-test.
        get_sqlalchemy_connection()
        failed = self.run_suite(suite, fatal_errors=kwargs.get('fatal_errors'))
        self.teardown_test_environment()
        if not failed:
            write_instrumentation_reports()
        return failed
