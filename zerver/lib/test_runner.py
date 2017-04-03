from __future__ import print_function

from functools import partial
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple, \
    Text, Type
from unittest import loader, runner  # type: ignore  # Mypy cannot pick these up.
from unittest.result import TestResult

from django.db import connections
from django.test import TestCase
from django.test import runner as django_runner
from django.test.runner import DiscoverRunner
from django.test.signals import template_rendered

from zerver.lib import test_classes, test_helpers
from zerver.lib.cache import bounce_key_prefix_for_testing
from zerver.lib.test_classes import flush_caches_for_testing
from zerver.lib.sqlalchemy_utils import get_sqlalchemy_connection
from zerver.lib.test_helpers import (
    get_all_templates, write_instrumentation_reports,
    append_instrumentation_data
)

import os
import subprocess
import sys
import time
import traceback
import unittest

if False:
    # Only needed by mypy.
    from multiprocessing.sharedctypes import Synchronized

_worker_id = 0  # Used to identify the worker process.

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

def enforce_timely_test_completion(test_method, test_name, delay, result):
    # type: (Any, str, float, TestResult) -> None
    if hasattr(test_method, 'slowness_reason'):
        max_delay = 1.1 # seconds
    else:
        max_delay = 0.4 # seconds

    if delay > max_delay:
        msg = '** Test is TOO slow: %s (%.3f s)\n' % (test_name, delay)
        result.addInfo(test_method, msg)

def fast_tests_only():
    # type: () -> bool
    return "FAST_TESTS_ONLY" in os.environ

def run_test(test, result):
    # type: (TestCase, TestResult) -> bool
    failed = False
    test_method = get_test_method(test)

    if fast_tests_only() and is_known_slow_test(test_method):
        return failed

    test_name = full_test_name(test)

    bounce_key_prefix_for_testing(test_name)
    flush_caches_for_testing()

    if not hasattr(test, "_pre_setup"):
        # test_name is likely of the form unittest.loader.ModuleImportFailure.zerver.tests.test_upload
        import_failure_prefix = 'unittest.loader.ModuleImportFailure.'
        if test_name.startswith(import_failure_prefix):
            actual_test_name = test_name[len(import_failure_prefix):]
            error_msg = ("\nActual test to be run is %s, but import failed.\n"
                         "Importing test module directly to generate clearer "
                         "traceback:\n") % (actual_test_name,)
            result.addInfo(test, error_msg)

            try:
                command = [sys.executable, "-c", "import %s" % (actual_test_name,)]
                msg = "Import test command: `%s`" % (' '.join(command),)
                result.addInfo(test, msg)
                subprocess.check_call(command)
            except subprocess.CalledProcessError:
                msg = ("If that traceback is confusing, try doing the "
                       "import inside `./manage.py shell`")
                result.addInfo(test, msg)
                result.addError(test, sys.exc_info())
                return True

            msg = ("Import unexpectedly succeeded! Something is wrong. Try "
                   "running `import %s` inside `./manage.py shell`.\n"
                   "If that works, you may have introduced an import "
                   "cycle.") % (actual_test_name,)
            import_error = (Exception, Exception(msg), None)  # type: Tuple[Any, Any, Any]
            result.addError(test, import_error)
            return True
        else:
            msg = "Test doesn't have _pre_setup; something is wrong."
            error_pre_setup = (Exception, Exception(msg), None)  # type: Tuple[Any, Any, Any]
            result.addError(test, error_pre_setup)
            return True
    test._pre_setup()

    start_time = time.time()

    test(result)  # unittest will handle skipping, error, failure and success.

    delay = time.time() - start_time
    enforce_timely_test_completion(test_method, test_name, delay, result)
    slowness_reason = getattr(test_method, 'slowness_reason', '')
    TEST_TIMINGS.append((delay, test_name, slowness_reason))

    test._post_teardown()
    return failed

class TextTestResult(runner.TextTestResult):
    """
    This class has unpythonic function names because base class follows
    this style.
    """
    def addInfo(self, test, msg):
        # type: (TestCase, Text) -> None
        self.stream.write(msg)
        self.stream.flush()

    def addInstrumentation(self, test, data):
        # type: (TestCase, Dict[str, Any]) -> None
        append_instrumentation_data(data)

    def startTest(self, test):
        # type: (TestCase) -> None
        TestResult.startTest(self, test)
        self.stream.writeln("Running {}".format(full_test_name(test)))
        self.stream.flush()

    def addSuccess(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        TestResult.addSuccess(self, *args, **kwargs)

    def addError(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        TestResult.addError(self, *args, **kwargs)

    def addFailure(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        TestResult.addFailure(self, *args, **kwargs)

    def addSkip(self, test, reason):
        # type: (TestCase, Text) -> None
        TestResult.addSkip(self, test, reason)
        self.stream.writeln("** Skipping {}: {}".format(full_test_name(test),
                                                        reason))
        self.stream.flush()

class RemoteTestResult(django_runner.RemoteTestResult):
    """
    The class follows the unpythonic style of function names of the
    base class.
    """
    def addInfo(self, test, msg):
        # type: (TestCase, Text) -> None
        self.events.append(('addInfo', self.test_index, msg))

    def addInstrumentation(self, test, data):
        # type: (TestCase, Dict[str, Any]) -> None
        # Some elements of data['info'] cannot be serialized.
        if 'info' in data:
            del data['info']

        self.events.append(('addInstrumentation', self.test_index, data))

def process_instrumented_calls(func):
    # type: (Callable) -> None
    for call in test_helpers.INSTRUMENTED_CALLS:
        func(call)

def run_subsuite(args):
    # type: (Tuple[int, Tuple[Type[Iterable[TestCase]], List[str]], bool]) -> Tuple[int, Any]
    subsuite_index, subsuite, failfast = args
    runner = RemoteTestRunner(failfast=failfast)
    result = runner.run(deserialize_suite(subsuite))
    # Now we send instrumentation related events. This data will be
    # appended to the data structure in the main thread. For Mypy,
    # type of Partial is different from Callable. All the methods of
    # TestResult are passed TestCase as the first argument but
    # addInstrumentation does not need it.
    process_instrumented_calls(partial(result.addInstrumentation, None))  # type: ignore
    return subsuite_index, result.events

def init_worker(counter):
    # type: (Synchronized) -> None
    global _worker_id
    test_classes.API_KEYS = {}

    # Clear the cache
    from zerver.lib.cache import get_cache_backend
    cache = get_cache_backend(None)
    cache.clear()

    # Close all connections
    connections.close_all()

    with counter.get_lock():
        counter.value += 1
        _worker_id = counter.value

    for alias in connections:
        connection = connections[alias]

        try:
            connection.creation.destroy_test_db(number=_worker_id)
        except Exception:
            # DB doesn't exist. No need to do anything.
            pass

        connection.creation.clone_test_db(
            number=_worker_id,
            keepdb=True,
        )

        settings_dict = connection.creation.get_test_db_clone_settings(_worker_id)
        # connection.settings_dict must be updated in place for changes to be
        # reflected in django.db.connections. If the following line assigned
        # connection.settings_dict = settings_dict, new threads would connect
        # to the default database instead of the appropriate clone.
        connection.settings_dict.update(settings_dict)
        connection.close()

class TestSuite(unittest.TestSuite):
    def run(self, result, debug=False):
        # type: (TestResult, Optional[bool]) -> TestResult
        """
        This function mostly contains the code from
        unittest.TestSuite.run. The need to override this function
        occurred because we use run_test to run the testcase.
        """
        topLevel = False
        if getattr(result, '_testRunEntered', False) is False:
            result._testRunEntered = topLevel = True

        for test in self:  # type: ignore  # Mypy cannot recognize this
            # but this is correct. Taken from unittest.
            if result.shouldStop:
                break

            if isinstance(test, TestSuite):
                test.run(result, debug=debug)
            else:
                self._tearDownPreviousClass(test, result)  # type: ignore
                self._handleModuleFixture(test, result)  # type: ignore
                self._handleClassSetUp(test, result)  # type: ignore
                result._previousTestClass = test.__class__
                if (getattr(test.__class__, '_classSetupFailed', False) or
                        getattr(result, '_moduleSetUpFailed', False)):
                    continue

                failed = run_test(test, result)
                if failed or result.shouldStop:
                    result.shouldStop = True
                    break

        if topLevel:
            self._tearDownPreviousClass(None, result)  # type: ignore
            self._handleModuleTearDown(result)  # type: ignore
            result._testRunEntered = False
        return result

class TestLoader(loader.TestLoader):
    suiteClass = TestSuite

class ParallelTestSuite(django_runner.ParallelTestSuite):
    run_subsuite = run_subsuite
    init_worker = init_worker

    def __init__(self, suite, processes, failfast):
        # type: (TestSuite, int, bool) -> None
        super(ParallelTestSuite, self).__init__(suite, processes, failfast)
        self.subsuites = SubSuiteList(self.subsuites)  # type: SubSuiteList

class Runner(DiscoverRunner):
    test_suite = TestSuite
    test_loader = TestLoader()
    parallel_test_suite = ParallelTestSuite

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

    def get_resultclass(self):
        # type: () -> Type[TestResult]
        return TextTestResult

    def on_template_rendered(self, sender, context, **kwargs):
        # type: (Any, Dict[str, Any], **Any) -> None
        if hasattr(sender, 'template'):
            template_name = sender.template.name
            if template_name not in self.templates_rendered:
                if context.get('shallow_tested') and template_name not in self.templates_rendered:
                    self.shallow_tested_templates.add(template_name)
                else:
                    self.templates_rendered.add(template_name)
                    self.shallow_tested_templates.discard(template_name)

    def get_shallow_tested_templates(self):
        # type: () -> Set[str]
        return self.shallow_tested_templates

    def run_tests(self, test_labels, extra_tests=None,
                  full_suite=False, **kwargs):
        # type: (List[str], Optional[List[TestCase]], bool, **Any) -> bool
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
        result = self.run_suite(suite)
        self.teardown_test_environment()
        failed = self.suite_result(suite, result)
        if not failed:
            write_instrumentation_reports(full_suite=full_suite)
        return failed

def get_test_names(suite):
    # type: (TestSuite) -> List[str]
    return [full_test_name(t) for t in get_tests_from_suite(suite)]

def get_tests_from_suite(suite):
    # type: (TestSuite) -> TestCase
    for test in suite:  # type: ignore
        if isinstance(test, TestSuite):
            for child in get_tests_from_suite(test):
                yield child
        else:
            yield test

def serialize_suite(suite):
    # type: (TestSuite) -> Tuple[Type[TestSuite], List[str]]
    return type(suite), get_test_names(suite)

def deserialize_suite(args):
    # type: (Tuple[Type[Iterable[TestCase]], List[str]]) -> Iterable[TestCase]
    suite_class, test_names = args
    suite = suite_class()  # type: ignore  # Gives abstract type error.
    tests = TestLoader().loadTestsFromNames(test_names)
    for test in get_tests_from_suite(tests):
        suite.addTest(test)
    return suite

class RemoteTestRunner(django_runner.RemoteTestRunner):
    resultclass = RemoteTestResult

class SubSuiteList(list):
    """
    This class allows us to avoid changing the main logic of
    ParallelTestSuite and still make it serializable.
    """
    def __init__(self, suites):
        # type: (List[TestSuite]) -> None
        serialized_suites = [serialize_suite(s) for s in suites]
        super(SubSuiteList, self).__init__(serialized_suites)

    def __getitem__(self, index):
        # type: (Any) -> Any
        suite = super(SubSuiteList, self).__getitem__(index)
        return deserialize_suite(suite)
