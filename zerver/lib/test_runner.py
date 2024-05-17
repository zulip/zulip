import multiprocessing
import os
import random
import shutil
import unittest
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple, Type, Union
from unittest import TestSuite, runner
from unittest.result import TestResult

import orjson
from django.conf import settings
from django.db import ProgrammingError, connections
from django.test import runner as django_runner
from django.test.runner import DiscoverRunner
from django.test.signals import template_rendered
from typing_extensions import TypeAlias, override

from scripts.lib.zulip_tools import (
    TEMPLATE_DATABASE_DIR,
    get_dev_uuid_var_path,
    get_or_create_dev_uuid_var_path,
)
from zerver.lib import test_helpers
from zerver.lib.partial import partial
from zerver.lib.sqlalchemy_utils import get_sqlalchemy_connection
from zerver.lib.test_fixtures import BACKEND_DATABASE_TEMPLATE
from zerver.lib.test_helpers import append_instrumentation_data, write_instrumentation_reports

# We need to pick an ID for this test-backend invocation, and store it
# in this global so it can be used in init_worker; this is used to
# ensure the database IDs we select are unique for each `test-backend`
# run.  This probably should use a locking mechanism rather than the
# below hack, which fails 1/10000000 of the time.
random_id_range_start = str(random.randint(1, 10000000))


def get_database_id(worker_id: Optional[int] = None) -> str:
    if worker_id:
        return f"{random_id_range_start}_{worker_id}"
    return random_id_range_start


# The root directory for this run of the test suite.
TEST_RUN_DIR = get_or_create_dev_uuid_var_path(
    os.path.join("test-backend", f"run_{get_database_id()}")
)

_worker_id = 0  # Used to identify the worker process.


class TextTestResult(runner.TextTestResult):
    """
    This class has unpythonic function names because base class follows
    this style.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.failed_tests: List[str] = []

    def addInstrumentation(self, test: unittest.TestCase, data: Dict[str, Any]) -> None:
        append_instrumentation_data(data)

    @override
    def startTest(self, test: unittest.TestCase) -> None:
        TestResult.startTest(self, test)
        self.stream.write(f"Running {test.id()}\n")
        self.stream.flush()

    @override
    def addSuccess(self, *args: Any, **kwargs: Any) -> None:
        TestResult.addSuccess(self, *args, **kwargs)

    @override
    def addError(self, *args: Any, **kwargs: Any) -> None:
        TestResult.addError(self, *args, **kwargs)
        test_name = args[0].id()
        self.failed_tests.append(test_name)

    @override
    def addFailure(self, *args: Any, **kwargs: Any) -> None:
        TestResult.addFailure(self, *args, **kwargs)
        test_name = args[0].id()
        self.failed_tests.append(test_name)

    @override
    def addSkip(self, test: unittest.TestCase, reason: str) -> None:
        TestResult.addSkip(self, test, reason)
        self.stream.write(f"** Skipping {test.id()}: {reason}\n")
        self.stream.flush()


class RemoteTestResult(django_runner.RemoteTestResult):
    """
    The class follows the unpythonic style of function names of the
    base class.
    """

    def addInstrumentation(self, test: unittest.TestCase, data: Dict[str, Any]) -> None:
        # Some elements of data['info'] cannot be serialized.
        if "info" in data:
            del data["info"]

        self.events.append(("addInstrumentation", self.test_index, data))


def process_instrumented_calls(func: Callable[[Dict[str, Any]], None]) -> None:
    for call in test_helpers.INSTRUMENTED_CALLS:
        func(call)


SerializedSubsuite: TypeAlias = Tuple[Type[TestSuite], List[str]]
SubsuiteArgs: TypeAlias = Tuple[Type["RemoteTestRunner"], int, SerializedSubsuite, bool, bool]


def run_subsuite(args: SubsuiteArgs) -> Tuple[int, Any]:
    # Reset the accumulated INSTRUMENTED_CALLS before running this subsuite.
    test_helpers.INSTRUMENTED_CALLS = []
    # The first argument is the test runner class but we don't need it
    # because we run our own version of the runner class.
    _, subsuite_index, subsuite, failfast, buffer = args
    runner = RemoteTestRunner(failfast=failfast, buffer=buffer)
    result = runner.run(subsuite)
    # Now we send instrumentation related events. This data will be
    # appended to the data structure in the main thread. For Mypy,
    # type of Partial is different from Callable. All the methods of
    # TestResult are passed TestCase as the first argument but
    # addInstrumentation does not need it.
    process_instrumented_calls(partial(result.addInstrumentation, None))
    return subsuite_index, result.events


def destroy_test_databases(worker_id: Optional[int] = None) -> None:
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
                """Modified from the Django original to"""
                database_id = get_database_id(worker_id)
                connection.creation.destroy_test_db(suffix=database_id)
            else:
                connection.creation.destroy_test_db()
        except ProgrammingError:
            # DB doesn't exist. No need to do anything.
            pass


def create_test_databases(worker_id: int) -> None:
    database_id = get_database_id(worker_id)
    for alias in connections:
        connection = connections[alias]
        connection.creation.clone_test_db(
            suffix=database_id,
            keepdb=True,
        )

        settings_dict = connection.creation.get_test_db_clone_settings(database_id)
        # connection.settings_dict must be updated in place for changes to be
        # reflected in django.db.connections. If the following line assigned
        # connection.settings_dict = settings_dict, new threads would connect
        # to the default database instead of the appropriate clone.
        connection.settings_dict.update(settings_dict)
        connection.close()


def init_worker(
    counter: "multiprocessing.sharedctypes.Synchronized[int]",
    initial_settings: Optional[Dict[str, Any]] = None,
    serialized_contents: Optional[Dict[str, str]] = None,
    process_setup: Optional[Callable[..., None]] = None,
    process_setup_args: Optional[Tuple[Any, ...]] = None,
    debug_mode: Optional[bool] = None,
    used_aliases: Optional[Set[str]] = None,
) -> None:
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

    # Clear the cache
    from zerver.lib.cache import get_cache_backend

    cache = get_cache_backend(None)
    cache.clear()

    # Close all connections
    connections.close_all()

    destroy_test_databases(_worker_id)
    create_test_databases(_worker_id)
    initialize_worker_path(_worker_id)


class ParallelTestSuite(django_runner.ParallelTestSuite):
    run_subsuite = run_subsuite
    init_worker = init_worker


def check_import_error(test_name: str) -> None:
    try:
        # Directly using __import__ is not recommended, but here it gives
        # clearer traceback as compared to importlib.import_module.
        __import__(test_name)
    except ImportError as exc:
        raise exc from exc  # Disable exception chaining in Python 3.


def initialize_worker_path(worker_id: int) -> None:
    # Allow each test worker process to write to a unique directory
    # within `TEST_RUN_DIR`.
    worker_path = os.path.join(TEST_RUN_DIR, f"worker_{_worker_id}")
    os.makedirs(worker_path, exist_ok=True)
    settings.TEST_WORKER_DIR = worker_path

    # Every process should upload to a separate directory so that
    # race conditions can be avoided.
    settings.LOCAL_UPLOADS_DIR = get_or_create_dev_uuid_var_path(
        os.path.join(
            "test-backend",
            os.path.basename(TEST_RUN_DIR),
            os.path.basename(worker_path),
            "test_uploads",
        )
    )
    settings.LOCAL_AVATARS_DIR = os.path.join(settings.LOCAL_UPLOADS_DIR, "avatars")
    settings.LOCAL_FILES_DIR = os.path.join(settings.LOCAL_UPLOADS_DIR, "files")


class Runner(DiscoverRunner):
    parallel_test_suite = ParallelTestSuite

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        DiscoverRunner.__init__(self, *args, **kwargs)

        # `templates_rendered` holds templates which were rendered
        # in proper logical tests.
        self.templates_rendered: Set[str] = set()
        # `shallow_tested_templates` holds templates which were rendered
        # in `zerver.tests.test_templates`.
        self.shallow_tested_templates: Set[str] = set()
        template_rendered.connect(self.on_template_rendered)

    @override
    def get_resultclass(self) -> Optional[Type[TextTestResult]]:
        return TextTestResult

    def on_template_rendered(self, sender: Any, context: Dict[str, Any], **kwargs: Any) -> None:
        if hasattr(sender, "template"):
            template_name = sender.template.name
            if template_name not in self.templates_rendered:
                if context.get("shallow_tested") and template_name not in self.templates_rendered:
                    self.shallow_tested_templates.add(template_name)
                else:
                    self.templates_rendered.add(template_name)
                    self.shallow_tested_templates.discard(template_name)

    def get_shallow_tested_templates(self) -> Set[str]:
        return self.shallow_tested_templates

    @override
    def setup_test_environment(self, *args: Any, **kwargs: Any) -> Any:
        settings.DATABASES["default"]["NAME"] = BACKEND_DATABASE_TEMPLATE
        # We create/destroy the test databases in run_tests to avoid
        # duplicate work when running in parallel mode.

        # Write the template database ids to a file that we can
        # reference for cleaning them up if they leak.
        filepath = os.path.join(get_dev_uuid_var_path(), TEMPLATE_DATABASE_DIR, get_database_id())
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w") as f:
            if self.parallel > 1:
                for index in range(self.parallel):
                    f.write(get_database_id(index + 1) + "\n")
            else:
                f.write(get_database_id() + "\n")

        # Check if we are in serial mode to avoid unnecessarily making a directory.
        # We add "worker_0" in the path for consistency with parallel mode.
        if self.parallel == 1:
            initialize_worker_path(0)

        return super().setup_test_environment(*args, **kwargs)

    @override
    def teardown_test_environment(self, *args: Any, **kwargs: Any) -> Any:
        # The test environment setup clones the zulip_test_template
        # database, creating databases with names:
        #     'zulip_test_template_N_<worker_id>',
        # where N is `random_id_range_start`, and `worker_id` is a
        # value between <1, self.parallel>.
        #
        # We need to delete those databases to avoid leaking disk
        # (Django is smart and calls this on SIGINT too).
        if self.parallel > 1:
            for index in range(self.parallel):
                destroy_test_databases(index + 1)
        else:
            destroy_test_databases()

        # Clean up our record of which databases this process created.
        filepath = os.path.join(get_dev_uuid_var_path(), TEMPLATE_DATABASE_DIR, get_database_id())
        os.remove(filepath)

        # Clean up our test runs root directory.
        try:
            shutil.rmtree(TEST_RUN_DIR)
        except OSError:
            print("Unable to clean up the test run's directory.")
        return super().teardown_test_environment(*args, **kwargs)

    def test_imports(
        self, test_labels: List[str], suite: Union[TestSuite, ParallelTestSuite]
    ) -> None:
        prefix = "unittest.loader._FailedTest."
        for test_name in get_test_names(suite):
            if test_name.startswith(prefix):
                test_name = test_name[len(prefix) :]
                for label in test_labels:
                    # This code block is for when a test label is
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

    @override
    def run_tests(
        self,
        test_labels: List[str],
        failed_tests_path: Optional[str] = None,
        full_suite: bool = False,
        include_webhooks: bool = False,
        **kwargs: Any,
    ) -> int:
        self.setup_test_environment()
        suite = self.build_suite(test_labels)
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
        with get_sqlalchemy_connection():
            result = self.run_suite(suite)
            assert isinstance(result, TextTestResult)
        self.teardown_test_environment()
        failed = self.suite_result(suite, result)
        if not failed:
            write_instrumentation_reports(full_suite=full_suite, include_webhooks=include_webhooks)
        if failed_tests_path and result.failed_tests:
            with open(failed_tests_path, "wb") as f:
                f.write(orjson.dumps(result.failed_tests))
        return failed


def get_test_names(suite: Union[TestSuite, ParallelTestSuite]) -> List[str]:
    if isinstance(suite, ParallelTestSuite):
        return [name for subsuite in suite.subsuites for name in get_test_names(subsuite)]
    else:
        return [t.id() for t in get_tests_from_suite(suite)]


def get_tests_from_suite(suite: TestSuite) -> Iterable[unittest.TestCase]:
    for test in suite:
        if isinstance(test, TestSuite):
            yield from get_tests_from_suite(test)
        else:
            yield test


class RemoteTestRunner(django_runner.RemoteTestRunner):
    resultclass = RemoteTestResult
