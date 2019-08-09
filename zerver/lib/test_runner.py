from functools import partial
import random

from typing import Any, Callable, Dict, List, Optional, Set, Tuple, \
    Type, TypeVar, Union
from unittest import loader, runner
from unittest.result import TestResult

from django.conf import settings
from django.db import connections, ProgrammingError
from django.urls.resolvers import RegexURLPattern
from django.test import TestCase
from django.test import runner as django_runner
from django.test.runner import DiscoverRunner
from django.test.signals import template_rendered

from zerver.lib import test_classes, test_helpers
from zerver.lib.cache import bounce_key_prefix_for_testing
from zerver.lib.rate_limiter import bounce_redis_key_prefix_for_testing
from zerver.lib.test_classes import flush_caches_for_testing
from zerver.lib.sqlalchemy_utils import get_sqlalchemy_connection
from zerver.lib.test_helpers import (
    write_instrumentation_reports,
    append_instrumentation_data
)

import os
import time
import unittest
import shutil

from multiprocessing.sharedctypes import Synchronized

from scripts.lib.zulip_tools import get_dev_uuid_var_path, TEMPLATE_DATABASE_DIR, \
    get_or_create_dev_uuid_var_path

# We need to pick an ID for this test-backend invocation, and store it
# in this global so it can be used in init_worker; this is used to
# ensure the database IDs we select are unique for each `test-backend`
# run.  This probably should use a locking mechanism rather than the
# below hack, which fails 1/10000000 of the time.
random_id_range_start = random.randint(1, 10000000) * 100
# The root directory for this run of the test suite.
TEST_RUN_DIR = get_or_create_dev_uuid_var_path(
    os.path.join('test-backend', 'run_{}'.format(random_id_range_start)))

_worker_id = 0  # Used to identify the worker process.

ReturnT = TypeVar('ReturnT')  # Constrain return type to match

def slow(slowness_reason: str) -> Callable[[Callable[..., ReturnT]], Callable[..., ReturnT]]:
    '''
    This is a decorate that annotates a test as being "known
    to be slow."  The decorator will set expected_run_time and slowness_reason
    as attributes of the function.  Other code can use this annotation
    as needed, e.g. to exclude these tests in "fast" mode.
    '''
    def decorator(f: Callable[..., ReturnT]) -> Callable[..., ReturnT]:
        setattr(f, 'slowness_reason', slowness_reason)
        return f

    return decorator

def is_known_slow_test(test_method: Callable[..., ReturnT]) -> bool:
    return hasattr(test_method, 'slowness_reason')

def full_test_name(test: TestCase) -> str:
    test_module = test.__module__
    test_class = test.__class__.__name__
    test_method = test._testMethodName
    return '%s.%s.%s' % (test_module, test_class, test_method)

def get_test_method(test: TestCase) -> Callable[[], None]:
    return getattr(test, test._testMethodName)

# Each tuple is delay, test_name, slowness_reason
TEST_TIMINGS = []  # type: List[Tuple[float, str, str]]


def report_slow_tests() -> None:
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

def enforce_timely_test_completion(test_method: Callable[..., ReturnT], test_name: str,
                                   delay: float, result: unittest.TestResult) -> None:
    if hasattr(test_method, 'slowness_reason'):
        max_delay = 2.0  # seconds
    else:
        max_delay = 0.4  # seconds

    assert isinstance(result, TextTestResult) or isinstance(result, RemoteTestResult)

    if delay > max_delay:
        msg = '** Test is TOO slow: %s (%.3f s)\n' % (test_name, delay)
        result.addInfo(test_method, msg)

def fast_tests_only() -> bool:
    return "FAST_TESTS_ONLY" in os.environ

def run_test(test: TestCase, result: TestResult) -> bool:
    failed = False
    test_method = get_test_method(test)

    if fast_tests_only() and is_known_slow_test(test_method):
        return failed

    test_name = full_test_name(test)

    bounce_key_prefix_for_testing(test_name)
    bounce_redis_key_prefix_for_testing(test_name)

    flush_caches_for_testing()

    if not hasattr(test, "_pre_setup"):
        msg = "Test doesn't have _pre_setup; something is wrong."
        error_pre_setup = (Exception, Exception(msg), None)
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
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.failed_tests = []  # type: List[str]

    def addInfo(self, test: TestCase, msg: str) -> None:
        self.stream.write(msg)  # type: ignore # https://github.com/python/typeshed/issues/3139
        self.stream.flush()  # type: ignore # https://github.com/python/typeshed/issues/3139

    def addInstrumentation(self, test: TestCase, data: Dict[str, Any]) -> None:
        append_instrumentation_data(data)

    def startTest(self, test: TestCase) -> None:
        TestResult.startTest(self, test)
        self.stream.writeln("Running {}".format(full_test_name(test)))  # type: ignore # https://github.com/python/typeshed/issues/3139
        self.stream.flush()  # type: ignore # https://github.com/python/typeshed/issues/3139

    def addSuccess(self, *args: Any, **kwargs: Any) -> None:
        TestResult.addSuccess(self, *args, **kwargs)

    def addError(self, *args: Any, **kwargs: Any) -> None:
        TestResult.addError(self, *args, **kwargs)
        test_name = full_test_name(args[0])
        self.failed_tests.append(test_name)

    def addFailure(self, *args: Any, **kwargs: Any) -> None:
        TestResult.addFailure(self, *args, **kwargs)
        test_name = full_test_name(args[0])
        self.failed_tests.append(test_name)

    def addSkip(self, test: TestCase, reason: str) -> None:
        TestResult.addSkip(self, test, reason)
        self.stream.writeln("** Skipping {}: {}".format(  # type: ignore # https://github.com/python/typeshed/issues/3139
            full_test_name(test),
            reason))
        self.stream.flush()  # type: ignore # https://github.com/python/typeshed/issues/3139

class RemoteTestResult(django_runner.RemoteTestResult):
    """
    The class follows the unpythonic style of function names of the
    base class.
    """
    def addInfo(self, test: TestCase, msg: str) -> None:
        self.events.append(('addInfo', self.test_index, msg))

    def addInstrumentation(self, test: TestCase, data: Dict[str, Any]) -> None:
        # Some elements of data['info'] cannot be serialized.
        if 'info' in data:
            del data['info']

        self.events.append(('addInstrumentation', self.test_index, data))

def process_instrumented_calls(func: Callable[[Dict[str, Any]], None]) -> None:
    for call in test_helpers.INSTRUMENTED_CALLS:
        func(call)

SerializedSubsuite = Tuple[Type['TestSuite'], List[str]]
SubsuiteArgs = Tuple[Type['RemoteTestRunner'], int, SerializedSubsuite, bool]

def run_subsuite(args: SubsuiteArgs) -> Tuple[int, Any]:
    # Reset the accumulated INSTRUMENTED_CALLS before running this subsuite.
    test_helpers.INSTRUMENTED_CALLS = []
    # The first argument is the test runner class but we don't need it
    # because we run our own version of the runner class.
    _, subsuite_index, subsuite, failfast = args
    runner = RemoteTestRunner(failfast=failfast)
    result = runner.run(deserialize_suite(subsuite))
    # Now we send instrumentation related events. This data will be
    # appended to the data structure in the main thread. For Mypy,
    # type of Partial is different from Callable. All the methods of
    # TestResult are passed TestCase as the first argument but
    # addInstrumentation does not need it.
    process_instrumented_calls(partial(result.addInstrumentation, None))
    return subsuite_index, result.events

# Monkey-patch database creation to fix unnecessary sleep(1)
from django.db.backends.postgresql.creation import DatabaseCreation
def _replacement_destroy_test_db(self: DatabaseCreation,
                                 test_database_name: str,
                                 verbosity: int) -> None:
    """Replacement for Django's _destroy_test_db that removes the
    unnecessary sleep(1)."""
    with self.connection._nodb_connection.cursor() as cursor:
        cursor.execute("DROP DATABASE %s"
                       % (self.connection.ops.quote_name(test_database_name),))
DatabaseCreation._destroy_test_db = _replacement_destroy_test_db

def destroy_test_databases(worker_id: Optional[int]=None) -> None:
    for alias in connections:
        connection = connections[alias]
        try:
            # In the parallel mode, the test databases are created
            # through the N=self.parallel child processes, and in the
            # parent process (which calls `destroy_test_databases`),
            # `settings_dict` remains unchanged, with the original
            # template database name (zulip_test_template).  So to
            # delete the database zulip_test_template_<number>, we
            # need to pass `number` to `destroy_test_db`.
            #
            # When we run in serial mode (self.parallel=1), we don't
            # fork and thus both creation and destruction occur in the
            # same process, which means `settings_dict` has been
            # updated to have `zulip_test_template_<number>` as its
            # database name by the creation code.  As a result, to
            # delete that database, we need to not pass a number
            # argument to destroy_test_db.
            if worker_id is not None:
                """Modified from the Django original to """
                database_id = random_id_range_start + worker_id
                connection.creation.destroy_test_db(number=database_id)
            else:
                connection.creation.destroy_test_db()
        except ProgrammingError:
            # DB doesn't exist. No need to do anything.
            pass

def create_test_databases(worker_id: int) -> None:
    database_id = random_id_range_start + worker_id
    for alias in connections:
        connection = connections[alias]
        connection.creation.clone_test_db(
            number=database_id,
            keepdb=True,
        )

        settings_dict = connection.creation.get_test_db_clone_settings(database_id)
        # connection.settings_dict must be updated in place for changes to be
        # reflected in django.db.connections. If the following line assigned
        # connection.settings_dict = settings_dict, new threads would connect
        # to the default database instead of the appropriate clone.
        connection.settings_dict.update(settings_dict)
        connection.close()

def init_worker(counter: Synchronized) -> None:
    """
    This function runs only under parallel mode. It initializes the
    individual processes which are also called workers.
    """
    global _worker_id

    with counter.get_lock():
        counter.value += 1
        _worker_id = counter.value

    """
    You can now use _worker_id.
    """

    test_classes.API_KEYS = {}

    # Clear the cache
    from zerver.lib.cache import get_cache_backend
    cache = get_cache_backend(None)
    cache.clear()

    # Close all connections
    connections.close_all()

    destroy_test_databases(_worker_id)
    create_test_databases(_worker_id)
    initialize_worker_path(_worker_id)

    def is_upload_avatar_url(url: RegexURLPattern) -> bool:
        if url.regex.pattern == r'^user_avatars/(?P<path>.*)$':
            return True
        return False

    # We manually update the upload directory path in the url regex.
    from zproject import dev_urls
    found = False
    for url in dev_urls.urls:
        if is_upload_avatar_url(url):
            found = True
            new_root = os.path.join(settings.LOCAL_UPLOADS_DIR, "avatars")
            url.default_args['document_root'] = new_root

    if not found:
        print("*** Upload directory not found.")

class TestSuite(unittest.TestSuite):
    def run(self, result: TestResult, debug: Optional[bool]=False) -> TestResult:
        """
        This function mostly contains the code from
        unittest.TestSuite.run. The need to override this function
        occurred because we use run_test to run the testcase.
        """
        topLevel = False
        if getattr(result, '_testRunEntered', False) is False:
            result._testRunEntered = topLevel = True  # type: ignore

        for test in self:
            # but this is correct. Taken from unittest.
            if result.shouldStop:
                break

            if isinstance(test, TestSuite):
                test.run(result, debug=debug)
            else:
                self._tearDownPreviousClass(test, result)  # type: ignore
                self._handleModuleFixture(test, result)  # type: ignore
                self._handleClassSetUp(test, result)  # type: ignore
                result._previousTestClass = test.__class__  # type: ignore
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
            result._testRunEntered = False  # type: ignore
        return result

class TestLoader(loader.TestLoader):
    suiteClass = TestSuite

class ParallelTestSuite(django_runner.ParallelTestSuite):
    run_subsuite = run_subsuite
    init_worker = init_worker

    def __init__(self, suite: TestSuite, processes: int, failfast: bool) -> None:
        super().__init__(suite, processes, failfast)
        # We can't specify a consistent type for self.subsuites, since
        # the whole idea here is to monkey-patch that so we can use
        # most of django_runner.ParallelTestSuite with our own suite
        # definitions.
        self.subsuites = SubSuiteList(self.subsuites)  # type: ignore # Type of self.subsuites changes.

def check_import_error(test_name: str) -> None:
    try:
        # Directly using __import__ is not recommeded, but here it gives
        # clearer traceback as compared to importlib.import_module.
        __import__(test_name)
    except ImportError as exc:
        raise exc from exc  # Disable exception chaining in Python 3.


def initialize_worker_path(worker_id: int) -> None:
    # Allow each test worker process to write to a unique directory
    # within `TEST_RUN_DIR`.
    worker_path = os.path.join(TEST_RUN_DIR, 'worker_{}'.format(_worker_id))
    os.makedirs(worker_path, exist_ok=True)
    settings.TEST_WORKER_DIR = worker_path

    # Every process should upload to a separate directory so that
    # race conditions can be avoided.
    settings.LOCAL_UPLOADS_DIR = get_or_create_dev_uuid_var_path(
        os.path.join("test-backend",
                     os.path.basename(TEST_RUN_DIR),
                     os.path.basename(worker_path),
                     "test_uploads"))

class Runner(DiscoverRunner):
    test_suite = TestSuite
    test_loader = TestLoader()
    parallel_test_suite = ParallelTestSuite

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        DiscoverRunner.__init__(self, *args, **kwargs)

        # `templates_rendered` holds templates which were rendered
        # in proper logical tests.
        self.templates_rendered = set()  # type: Set[str]
        # `shallow_tested_templates` holds templates which were rendered
        # in `zerver.tests.test_templates`.
        self.shallow_tested_templates = set()  # type: Set[str]
        template_rendered.connect(self.on_template_rendered)

    def get_resultclass(self) -> Type[TestResult]:
        return TextTestResult

    def on_template_rendered(self, sender: Any, context: Dict[str, Any], **kwargs: Any) -> None:
        if hasattr(sender, 'template'):
            template_name = sender.template.name
            if template_name not in self.templates_rendered:
                if context.get('shallow_tested') and template_name not in self.templates_rendered:
                    self.shallow_tested_templates.add(template_name)
                else:
                    self.templates_rendered.add(template_name)
                    self.shallow_tested_templates.discard(template_name)

    def get_shallow_tested_templates(self) -> Set[str]:
        return self.shallow_tested_templates

    def setup_test_environment(self, *args: Any, **kwargs: Any) -> Any:
        settings.DATABASES['default']['NAME'] = settings.BACKEND_DATABASE_TEMPLATE
        # We create/destroy the test databases in run_tests to avoid
        # duplicate work when running in parallel mode.

        # Write the template database ids to a file that we can
        # reference for cleaning them up if they leak.
        filepath = os.path.join(get_dev_uuid_var_path(),
                                TEMPLATE_DATABASE_DIR,
                                str(random_id_range_start))
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w") as f:
            if self.parallel > 1:
                for index in range(self.parallel):
                    f.write(str(random_id_range_start + (index + 1)) + "\n")
            else:
                f.write(str(random_id_range_start) + "\n")

        # Check if we are in serial mode to avoid unnecessarily making a directory.
        # We add "worker_0" in the path for consistency with parallel mode.
        if self.parallel == 1:
            initialize_worker_path(0)

        return super().setup_test_environment(*args, **kwargs)

    def teardown_test_environment(self, *args: Any, **kwargs: Any) -> Any:
        # The test environment setup clones the zulip_test_template
        # database, creating databases with names:
        #     'zulip_test_template_<N, N + self.parallel - 1>',
        # where N is random_id_range_start.
        #
        # We need to delete those databases to avoid leaking disk
        # (Django is smart and calls this on SIGINT too).
        if self.parallel > 1:
            for index in range(self.parallel):
                destroy_test_databases(index + 1)
        else:
            destroy_test_databases()

        # Clean up our record of which databases this process created.
        filepath = os.path.join(get_dev_uuid_var_path(),
                                TEMPLATE_DATABASE_DIR,
                                str(random_id_range_start))
        os.remove(filepath)

        # Clean up our test runs root directory.
        try:
            shutil.rmtree(TEST_RUN_DIR)
        except OSError:
            print("Unable to clean up the test run's directory.")
            pass
        return super().teardown_test_environment(*args, **kwargs)

    def test_imports(self, test_labels: List[str], suite: Union[TestSuite, ParallelTestSuite]) -> None:
        prefix_old = 'unittest.loader.ModuleImportFailure.'  # Python <= 3.4
        prefix_new = 'unittest.loader._FailedTest.'  # Python > 3.4
        error_prefixes = [prefix_old, prefix_new]
        for test_name in get_test_names(suite):
            for prefix in error_prefixes:
                if test_name.startswith(prefix):
                    test_name = test_name[len(prefix):]
                    for label in test_labels:
                        # This code block is for Python 3.5 when test label is
                        # directly provided, for example:
                        # ./tools/test-backend zerver.tests.test_alert_words.py
                        #
                        # In this case, the test name is of this form:
                        # 'unittest.loader._FailedTest.test_alert_words'
                        #
                        # Whereas check_import_error requires test names of
                        # this form:
                        # 'unittest.loader._FailedTest.zerver.tests.test_alert_words'.
                        if test_name in label:
                            test_name = label
                            break
                    check_import_error(test_name)

    def run_tests(self, test_labels: List[str],
                  extra_tests: Optional[List[TestCase]]=None,
                  full_suite: bool=False,
                  include_webhooks: bool=False,
                  **kwargs: Any) -> Tuple[bool, List[str]]:
        self.setup_test_environment()
        try:
            suite = self.build_suite(test_labels, extra_tests)
        except AttributeError:
            # We are likely to get here only when running tests in serial
            # mode on Python 3.4 or lower.
            # test_labels are always normalized to include the correct prefix.
            # If we run the command with ./tools/test-backend test_alert_words,
            # test_labels will be equal to ['zerver.tests.test_alert_words'].
            for test_label in test_labels:
                check_import_error(test_label)

            # I think we won't reach this line under normal circumstances, but
            # for some unforeseen scenario in which the AttributeError was not
            # caused by an import error, let's re-raise the exception for
            # debugging purposes.
            raise

        self.test_imports(test_labels, suite)
        if self.parallel == 1:
            # We are running in serial mode so create the databases here.
            # For parallel mode, the databases are created in init_worker.
            # We don't want to create and destroy DB in setup_test_environment
            # because it will be called for both serial and parallel modes.
            # However, at this point we know in which mode we would be running
            # since that decision has already been made in build_suite().
            #
            # We pass a _worker_id, which in this code path is always 0
            destroy_test_databases(_worker_id)
            create_test_databases(_worker_id)

        # We have to do the next line to avoid flaky scenarios where we
        # run a single test and getting an SA connection causes data from
        # a Django connection to be rolled back mid-test.
        get_sqlalchemy_connection()
        result = self.run_suite(suite)
        self.teardown_test_environment()
        failed = self.suite_result(suite, result)
        if not failed:
            write_instrumentation_reports(full_suite=full_suite, include_webhooks=include_webhooks)
        return failed, result.failed_tests

def get_test_names(suite: Union[TestSuite, ParallelTestSuite]) -> List[str]:
    if isinstance(suite, ParallelTestSuite):
        # suite is ParallelTestSuite. It will have a subsuites parameter of
        # type SubSuiteList. Each element of a SubsuiteList is a tuple whose
        # first element is the type of TestSuite and the second element is a
        # list of test names in that test suite. See serialize_suite() for the
        # implementation details.
        return [name for subsuite in suite.subsuites for name in subsuite[1]]
    else:
        return [full_test_name(t) for t in get_tests_from_suite(suite)]

def get_tests_from_suite(suite: unittest.TestSuite) -> TestCase:
    for test in suite:
        if isinstance(test, TestSuite):
            for child in get_tests_from_suite(test):
                yield child
        else:
            yield test

def serialize_suite(suite: TestSuite) -> Tuple[Type[TestSuite], List[str]]:
    return type(suite), get_test_names(suite)

def deserialize_suite(args: Tuple[Type[TestSuite], List[str]]) -> TestSuite:
    suite_class, test_names = args
    suite = suite_class()
    tests = TestLoader().loadTestsFromNames(test_names)
    for test in get_tests_from_suite(tests):
        suite.addTest(test)
    return suite

class RemoteTestRunner(django_runner.RemoteTestRunner):
    resultclass = RemoteTestResult

class SubSuiteList(List[Tuple[Type[TestSuite], List[str]]]):
    """
    This class allows us to avoid changing the main logic of
    ParallelTestSuite and still make it serializable.
    """
    def __init__(self, suites: List[TestSuite]) -> None:
        serialized_suites = [serialize_suite(s) for s in suites]
        super().__init__(serialized_suites)

    def __getitem__(self, index: Any) -> Any:
        suite = super().__getitem__(index)
        return deserialize_suite(suite)
