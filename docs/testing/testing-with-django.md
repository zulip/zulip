# Backend Django tests

## Overview

Zulip uses the Django framework for its Python backend. We
use the testing framework from
[django.test](https://docs.djangoproject.com/en/5.0/topics/testing/)
to test our code. We have thousands of automated tests that verify that
our backend works as expected.

All changes to the Zulip backend code should be supported by tests. We
enforce our testing culture during code review, and we also use
coverage tools to measure how well we test our code. We mostly use
tests to prevent regressions in our code, but the tests can have
ancillary benefits such as documenting interfaces and influencing
the design of our software.

If you have worked on other Django projects that use unit testing, you
will probably find familiar patterns in Zulip's code. This document
describes how to write tests for the Zulip backend, with a particular
emphasis on areas where we have either wrapped Django's test framework
or just done things that are kind of unique in Zulip.

## Running tests

Our tests live in `zerver/tests/`. You can run them with
`./tools/test-backend`. The tests run in parallel using multiple
threads in your development environment, and can finish in under 30s
on a fast machine. When you are in iterative mode, you can run
individual tests or individual modules, following the dotted.test.name
convention below:

```bash
cd /srv/zulip
./tools/test-backend zerver.tests.test_queue_worker.WorkerTest
```

There are many command line options for running Zulip tests, such
as a `--verbose` option. The
best way to learn the options is to use the online help:

```bash
./tools/test-backend --help
```

We also have ways to instrument our tests for finding code coverage,
URL coverage, and slow tests. Use the `-h` option to discover these
features. We also have a `--profile` option to facilitate profiling
tests.

By default, `test-backend` will run all requested tests, and report
all failures at the end. You can configure it to stop after the first
error with the `--stop` option (or `-x`).

Another useful option is `--rerun`, which will rerun just the tests
that failed in the last test run.

**Webhook integrations**. For performance, `test-backend` with no
arguments will not run webhook integration tests (`zerver/webhooks/`),
which would otherwise account for about 25% of the total runtime.
When working on webhooks, we recommend instead running
`test-backend zerver/webhooks` manually (or better, the direction for
the specific webhooks you're working on). And of course our CI is
configured to always use `test-backend --include-webhooks` and run all
of the tests.

## Writing tests

Before you write your first tests of Zulip, it is worthwhile to read
the rest of this document.

To get a hang of commonly used testing techniques, read
[zerver/tests/test_example.py](https://github.com/zulip/zulip/blob/main/zerver/tests/test_example.py).
You can also read some of the existing tests in `zerver/tests`
to get a feel for other patterns we use.

A good practice is to get a "failing test" before you start to implement
your feature. First, it is a useful exercise to understand what needs to happen
in your tests before you write the code, as it can help drive out simple
design or help you make incremental progress on a large feature. Second,
you want to avoid introducing tests that give false positives. Ensuring
that a test fails before you implement the feature ensures that if somebody
accidentally regresses the feature in the future, the test will catch
the regression.

Another important files to skim are
[zerver/lib/test_helpers.py](https://github.com/zulip/zulip/blob/main/zerver/lib/test_helpers.py),
which contains test helpers.
[zerver/lib/test_classes.py](https://github.com/zulip/zulip/blob/main/zerver/lib/test_classes.py),
which contains our `ZulipTestCase` and `WebhookTestCase` classes.

### Setting up data for tests

All tests start with the same fixture data. (The tests themselves
update the database, but they do so inside a transaction that gets
rolled back after each of the tests complete. For more details on how the
fixture data gets set up, refer to `tools/setup/generate-fixtures`.)

The fixture data includes a few users that are named after
Shakesepeare characters, and they are part of the "zulip.com" realm.

Generally, you will also do some explicit data setup of your own. Here
are a couple useful methods in ZulipTestCase:

- make_stream
- subscribe
- unsubscribe
- send_stream_message
- send_personal_message

More typically, you will use methods directly from the backend code.
(This ensures more end-to-end testing, and avoids false positives from
tests that might not consider ancillary parts of data setup that could
influence tests results.)

Here are some example action methods that tests may use for data setup:

- check_send_message
- do_change_user_role
- do_create_user
- do_make_stream_private

### Testing code that accesses the filesystem

Some tests need to access the filesystem (e.g., `test_upload.py` tests
for `LocalUploadBackend` and the data import tests). Doing
this correctly requires care to avoid problems like:

- Leaking files after every test (which are clutter and can eventually
  run the development environment out of disk) or
- Interacting with other parallel processes of this `test-backend` run
  (or another `test-backend` run), or with later tests run by this
  process.

To avoid these problems, you can do the following:

- Use a subdirectory of `settings.TEST_WORKER_DIR`; this is a
  subdirectory of `/var/<uuid>/test-backend` that is unique to the
  test worker thread and will be automatically deleted when the
  relevant `test-backend` process finishes.
- Delete any files created by the test in the test class's `tearDown`
  method (which runs even if the test fails); this is valuable to
  avoid conflicts with other tests run later by the same test process.

Our common testing infrastructure handles some of this for you,
e.g., it replaces `settings.LOCAL_UPLOADS_DIR` for each test process
with a unique path under `/var/<uuid>/test-backend`. And
`UploadSerializeMixin` manages some of the cleanup work for
`test_upload.py`.

### Testing with mocks

This section is a beginner's guide to mocking with Python's
`unittest.mock` library. It will give you answers to the most common
questions around mocking, and a selection of commonly used mocking
techniques.

#### What is mocking?

When writing tests, _mocks allow you to replace methods or objects with fake entities
suiting your testing requirements_. Once an object is mocked, **its original code does not
get executed anymore**.

Rather, you can think of a mocked object as an initially empty shell:
Calling it won't do anything, but you can fill your shell with custom code, return values, etc.
Additionally, you can observe any calls made to your mocked object.

#### Why is mocking useful?

When writing tests, it often occurs that you make calls to functions
taking complex arguments. Creating a real instance of such an argument
would require the use of various different libraries, a lot of
boilerplate code, etc. Another scenario is that the tested code
accesses files or objects that don't exist at testing time. Finally,
it is good practice to keep tests independent from others. Mocks help
you to isolate test cases by simulating objects and methods irrelevant
to a test's goal.

In all of these cases, you can "mock out" the function calls / objects
and replace them with fake instances that only implement a limited
interface. On top of that, these fake instances can be easily
analyzed.

Say you have a module `greetings` defining the following functions:

```python
def fetch_database(key: str) -> str:
    # ...
    # Do some look-ups in a database
    return data

def greet(name_key: str) -> str:
    name = fetch_database(name_key)
    return "Hello" + name
```

- You want to test `greet()`.

- In your test, you want to call `greet("Mario")` and verify that it returns the correct greeting:

  ```python
  from greetings import greet

  def test_greet() -> str:
      greeting = greet("Mario")
      assert greeting == "Hello Mr. Mario Mario"
  ```

-> **You have a problem**: `greet()` calls `fetch_database()`. `fetch_database()` does some look-ups in
a database. _You haven't created that database for your tests, so your test would fail, even though
the code is correct._

- Luckily, you know that `fetch_database("Mario")` should return "Mr. Mario Mario".

  - _Hint_: Sometimes, you might not know the exact return value, but one that is equally valid and works
    with the rest of the code. In that case, just use this one.

-> **Solution**: You mock `fetch_database()`. This is also referred to as "mocking out" `fetch_database()`.

```python
from unittest.mock import patch

def test_greet() -> None:
    # Mock `fetch_database()` with an object that acts like a shell: It still accepts calls like `fetch_database()`,
    # but doesn't do any database lookup. We "fill" the shell with a return value; This value will be returned on every
    # call to `fetch_database()`.
    with patch("greetings.fetch_database", return_value="Mr. Mario Mario"):
        greeting = greetings.greet("Mario")
        assert greeting == "Hello Mr. Mario Mario"
```

That's all. Note that **this mock is suitable for testing `greet()`, but not for testing `fetch_database()`**.
More generally, you should only mock those functions you explicitly don't want to test.

#### How does mocking work under the hood?

Since Python 3.3, the standard mocking library is `unittest.mock`. `unittest.mock` implements the basic mocking class `Mock`.
It also implements `MagicMock`, which is the same as `Mock`, but contains many default magic methods (in Python,
those are the ones starting with with a dunder `__`). From the docs:

> In most of these examples the Mock and MagicMock classes are interchangeable. As the MagicMock is the more capable class
> it makes a sensible one to use by default.

`Mock` itself is a class that principally accepts and records any and all calls. A piece of code like

```python
from unittest import mock

foo = mock.Mock()
foo.bar('quux')
foo.baz
foo.qux = 42
```

is _not_ going to throw any errors. Our mock silently accepts all these calls and records them.
`Mock` also implements methods for us to access and assert its records, e.g.,

```python
foo.bar.assert_called_with('quux')
```

Finally, `unittest.mock` also provides a method to mock objects only within a scope: `patch()`. We can use `patch()` either
as a decorator or as a context manager. In both cases, the mock created by `patch()` will apply for the scope of the decorator /
context manager. `patch()` takes only one required argument `target`. `target` is a string in dot notation that _refers to
the name of the object you want to mock_. It will then assign a `MagicMock()` to that object.
As an example, look at the following code:

```python
from unittest import mock
from os import urandom

with mock.patch('__main__.urandom', return_value=42):
    print(urandom(1))
    print(urandom(1)) # No matter what value we plug in for urandom, it will always return 42.
print(urandom(1)) # We exited the context manager, so the mock doesn't apply anymore. Will return a random byte.
```

_Note that calling `mock.patch('os.urandom', return_value=42)` wouldn't work here_: `os.urandom` would be the name of our patched
object. However, we imported `urandom` with `from os import urandom`; hence, we bound the `urandom` name to our current module
`__main__`.

On the other hand, if we had used `import os.urandom`, we would need to call `mock.patch('os.urandom', return_value=42)` instead.

#### Boilerplate code

- Including the Python mocking library:

  ```python
  from unittest import mock
  ```

- Mocking a class with a context manager:

  ```python
  with mock.patch('module.ClassName', foo=42, return_value='I am a mock') as my_mock:
    # In here, 'module.ClassName' is mocked with a MagicMock() object my_mock.
    # my_mock has an attribute named foo with the value 42.
    # var = module.ClassName() will assign 'I am a mock' to var.
  ```

- Mocking a class with a decorator:

  ```python
  @mock.patch('module.ClassName', foo=42, return_value='I am a mock')
  def my_function(my_mock):
      # ...
      # In here, 'module.ClassName' will behave as in the previous example.
  ```

- Mocking a class attribute:

  ```python
  with mock.patch.object(module.ClassName, 'class_method', return_value=42)
    # In here, 'module.ClassName' has the same properties as before, except for 'class_method'
    # Calling module.ClassName.class_method() will now return 42.
  ```

  Note the missing quotes around module.ClassName in the patch.object() call.

#### Zulip mocking practices

For mocking we generally use the "mock" library and use `mock.patch` as
a context manager or decorator. We also take advantage of some context managers
from Django as well as our own custom helpers. Here is an example:

```python
with self.settings(RATE_LIMITING=True):
    with mock.patch('zerver.decorator.rate_limit_user') as rate_limit_mock:
        api_result = my_webhook(request)

self.assertTrue(rate_limit_mock.called)
```

Follow [this link](../subsystems/settings.md#testing-non-default-settings) for more
information on the "settings" context manager.

Zulip has several features, like outgoing webhooks or social
authentication, that made outgoing HTTP requests to external
servers. We test those features using the excellent
[responses](https://pypi.org/project/responses/) library, which has a
nice interface for mocking `requests` calls to return whatever HTTP
response from the external server we need for the test. you can find
examples with `git grep responses.add`. Zulip's own `HostRequestMock`
class should be used only for low-level tests for code that expects to
receive Django HttpRequest object.

## Zulip testing philosophy

If there is one word to describe Zulip's philosophy for writing tests,
it is probably "flexible." (Hopefully "thorough" goes without saying.)

When in doubt, unless speed concerns are prohibitive,
you usually want your tests to be somewhat end-to-end, particularly
for testing endpoints.

These are some of the testing strategies that you will see in the Zulip
test suite...

### Endpoint tests

We strive to test all of our URL endpoints. The vast majority of Zulip
endpoints support a JSON interface. Regardless of the interface, an
endpoint test generally follows this pattern:

- Set up the data.
- Log in with `self.login()` or set up an API key.
- Use a Zulip test helper to hit the endpoint.
- Assert that the result was either a success or failure.
- Check the data that comes back from the endpoint.

Generally, if you are doing endpoint tests, you will want to create a
test class that is a subclass of `ZulipTestCase`, which will provide
you helper methods like the following:

- api_auth
- assert_json_error
- assert_json_success
- client_get
- client_post
- get_api_key
- get_streams
- login
- send_message

### Library tests

For certain Zulip library functions, especially the ones that are
not intrinsically tied to Django, we use a classic unit testing
approach of calling the function and inspecting the results.

For these types of tests, you will often use methods like
`self.assertEqual()`, `self.assertTrue()`, etc., which come with
[unittest](https://docs.python.org/3/library/unittest.html#unittest.TestCase)
via Django.

### Fixture-driven tests

Particularly for testing Zulip's integrations with third party systems,
we strive to have a highly data-driven approach to testing. To give a
specific example, when we test our GitHub integration, the test code
reads a bunch of sample inputs from a JSON fixture file, feeds them
to our GitHub integration code, and then verifies the output against
expected values from the same JSON fixture file.

Our fixtures live in `zerver/tests/fixtures`.

### Mocks and stubs

We use mocks and stubs for all the typical reasons:

- to more precisely test the target code
- to stub out calls to third-party services
- to make it so that you can [run the Zulip tests on the airplane without wifi][no-internet]

[no-internet]: testing.md#internet-access-inside-test-suites

A detailed description of mocks, along with useful coded snippets, can be found in the section
[Testing with mocks](#testing-with-mocks).

### Template tests

In [zerver/tests/test_templates.py](https://github.com/zulip/zulip/blob/main/zerver/tests/test_templates.py)
we have a test that renders all of our backend templates with
a "dummy" context, to make sure the templates don't have obvious
errors. (These tests won't catch all types of errors; they are
just a first line of defense.)

### SQL performance tests

A common class of bug with Django systems is to handle bulk data in
an inefficient way, where the backend populates objects for join tables
with a series of individual queries that give O(N) latency. (The
remedy is often just to call `select_related()`, but sometimes it
requires a more subtle restructuring of the code.)

We try to prevent these bugs in our tests by using a context manager
called `queries_captured()` that captures the SQL queries used by
the backend during a particular operation. We make assertions about
those queries, often simply by using the `assert_database_query_count`
that checks the number of queries.

### Event-based tests

The Zulip backend has a mechanism where it will fetch initial data
for a client from the database, and then it will subsequently apply
some queued up events to that data to the data structure before notifying
the client. The `BaseAction.do_test()` helper helps tests
verify that the application of those events via apply_events() produces
the same data structure as performing an action that generates said event.

This is a bit esoteric, but if you read the tests, you will see some of
the patterns. You can also learn more about our event system in the
[new feature tutorial](../tutorials/new-feature-tutorial.md#handle-database-interactions).

### Negative tests

It is important to verify error handling paths for endpoints, particularly
situations where we need to ensure that we don't return results to clients
with improper authentication or with limited authorization. A typical test
will call the endpoint with either a non-logged in client, an invalid API
key, or missing input fields. Then the test will call `assert_json_error()`
to verify that the endpoint is properly failing.

## Testing considerations

Here are some things to consider when writing new tests:

- **Duplication** We try to avoid excessive duplication in tests.
  If you have several tests repeating the same type of test setup,
  consider making a setUp() method or a test helper.

- **Network independence** Our tests should still work if you don't
  have an internet connection. For third party clients, you can simulate
  their behavior using fixture data. For third party servers, you can
  typically simulate their behavior using mocks.

- **Coverage** We have 100% line coverage on several of our backend
  modules. You can use the `--coverage` option to generate coverage
  reports, and new code should have 100% coverage, which generally
  requires testing not only the "happy path" but also error handling
  code and edge cases. It will generate a nice HTML report that you can
  view right from your browser (the tool prints the URL where the report
  is exposed in your development environment).

  The HTML report also displays which tests executed each line, which
  can be handy for finding existing tests for a code path you're
  working on.

- **Console output** A properly written test should print nothing to
  the console; use `with self.assertLogs` to capture and verify any
  logging output. Note that we reconfigure various loggers in
  `zproject/test_extra_settings.py` where the output is unlikely to be
  interesting when running our test suite.
  `test-backend --ban-console-output` checks for stray print statements.

Note that `test-backend --coverage` will assert that
various specific files in the project have 100% test coverage and
throw an error if their coverage has fallen. One of our project goals
is to expand that checking to ever-larger parts of the codebase.
