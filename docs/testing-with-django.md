# Backend Django tests

## Overview

Zulip uses the Django framework for its Python back end.  We
use the testing framework from
[django.test](https://docs.djangoproject.com/en/1.10/topics/testing/)
to test our code.  We have over a thousand automated tests that verify that
our backend works as expected.

All changes to the Zulip backend code should be supported by tests.  We
enforce our testing culture during code review, and we also use
coverage tools to measure how well we test our code.  We mostly use
tests to prevent regressions in our code, but the tests can have
ancillary benefits such as documenting interfaces and influencing
the design of our software.

If you have worked on other Django projects that use unit testing, you
will probably find familiar patterns in Zulip's code.  This document
describes how to write tests for the Zulip back end, with a particular
emphasis on areas where we have either wrapped Django's test framework
or just done things that are kind of unique in Zulip.

## Running tests

Our tests live in `zerver/tests/`. You can run them with
`./tools/test-backend`. It generally takes about a minute to run
the entire test suite.  When you are in iterative mode, you
can run individual tests or individual modules, following the
dotted.test.name convention below:

    cd /srv/zulip
    ./tools/test-backend zerver.tests.tests.WorkerTest

There are many command line options for running Zulip tests, such
as a `--verbose` option.  The
best way to learn the options is to use the online help:

    ./tools/test-backend -h

We also have ways to instrument our tests for finding code coverage,
URL coverage, and slow tests.  Use the `-h` option to discover these
features.  We also have a `--profile` option to facilitate profiling
tests.

Another thing to note is that our tests generally "fail fast," i.e. they
stop at the first sign of trouble.  This is generally a good thing for
iterative development, but you can override this behavior with the
`--nonfatal-errors` option.

## How to write tests.

Before you write your first tests of Zulip, it is worthwhile to read
the rest of this document, and you can also read some of the existing tests
in `zerver/tests` to get a feel for the patterns we use.

A good practice is to get a "failing test" before you start to implement
your feature.  First, it is a useful exercise to understand what needs to happen
in your tests before you write the code, as it can help drive out simple
design or help you make incremental progress on a large feature.  Second,
you want to avoid introducing tests that give false positives.  Ensuring
that a test fails before you implement the feature ensures that if somebody
accidentally regresses the feature in the future, the test will catch
the regression.

Another important file to skim is
[zerver/lib/test_helpers.py](https://github.com/zulip/zulip/blob/master/zerver/lib/test_helpers.py),
which contains test helpers and our `ZulipTestCase` class.

### Setting up data for tests

All tests start with the same fixture data.  (The tests themselves
update the database, but they do so inside a transaction that gets
rolled back after each of the tests complete. For more details on how the
fixture data gets set up, refer to `tools/setup/generate-fixtures`.)

The fixture data includes a few users that are named after
Shakesepeare characters, and they are part of the "zulip.com" realm.

Generally, you will also do some explicit data setup of your own. Here
are a couple useful methods in ZulipTestCase:

- common_subscribe_to_streams
- send_message
- subscribe_to_stream

More typically, you will use methods directly from the backend code.
(This ensures more end-to-end testing, and avoids false positives from
tests that might not consider ancillary parts of data setup that could
influence tests results.)

Here are some example action methods that tests may use for data setup:

- check_send_message
- create_stream_if_needed
- do_add_subscription
- do_change_is_admin
- do_create_user
- do_make_stream_private

## Zulip Testing Philosophy

If there is one word to describe Zulip's philosophy for writing tests,
it is probably "flexible."  (Hopefully "thorough" goes without saying.)

When in doubt, unless speed concerns are prohibitive,
you usually want your tests to be somewhat end-to-end, particularly
for testing endpoints.

These are some of the testing strategies that you will see in the Zulip
test suite...

### Endpoint tests

We strive to test all of our URL endpoints.  The vast majority of Zulip
endpoints support a JSON interface.  Regardless of the interface, an
endpoint test generally follows this pattern:

- Set up the data.
- Login with `self.login()` or set up an API key.
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
we strive to have a highly data-driven approach to testing.  To give a
specific example, when we test our GitHub integration, the test code
reads a bunch of sample inputs from a JSON fixture file, feeds them
to our Github integration code, and then verifies the output against
expected values from the same JSON fixture file.

Our fixtures live in `zerver/fixtures`.

### Mocks and stubs

We use mocks and stubs for all the typical reasons:

- to more precisely test the target code
- to stub out calls to third-party services
- to make it so that you can run your tests on the airplane without wifi

For mocking we generally use the "mock" library and use `mock.patch` as
a context manager or decorator.  We also take advantage of some context managers
from Django as well as our own custom helpers.  Here is an example:


        with self.settings(RATE_LIMITING=True):
            with mock.patch('zerver.decorator.rate_limit_user') as rate_limit_mock:
                api_result = my_webhook(request)

        self.assertTrue(rate_limit_mock.called)

Follow [this link](settings.html#testing-non-default-settings) for more
information on the "settings" context manager.

### Template tests

In [zerver/tests/test_templates.py](https://github.com/zulip/zulip/blob/master/zerver/tests/test_templates.py)
we have a test that renders all of our back end templates with
a "dummy" context, to make sure the templates don't have obvious
errors.  (These tests won't catch all types of errors; they are
just a first line of defense.)

### SQL performance tests

A common class of bug with Django systems is to handle bulk data in
an inefficient way, where the back end populates objects for join tables
with a series of individual queries that give O(N) latency.  (The
remedy is often just to call `select_related()`, but sometimes it
requires a more subtle restructuring of the code.)

We try to prevent these bugs in our tests by using a context manager
called `queries_captured()` that captures the SQL queries used by
the back end during a particular operation.  We make assertions about
those queries, often simply asserting that the number of queries is
below some threshold.

### Event-based tests

The Zulip back end has a mechanism where it will fetch initial data
for a client from the database, and then it will subsequently apply
some queued up events to that data to the data structure before notifying
the client.  The `EventsRegisterTest.do_test()` helper helps tests
verify that the application of those events via apply_events() produces
the same data structure as performing an action that generates said event.

This is a bit esoteric, but if you read the tests, you will see some of
the patterns.  You can also learn more about our event system in the
[new feature tutorial](new-feature-tutorial.html#handle-database-interactions).

### Negative tests

It is important to verify error handling paths for endpoints, particularly
situations where we need to ensure that we don't return results to clients
with improper authentication or with limited authorization.  A typical test
will call the endpoint with either a non-logged in client, an invalid API
key, or missing input fields.  Then the test will call `assert_json_error()`
to verify that the endpoint is properly failing.

## Testing considerations

Here are some things to consider when writing new tests:

- **Duplication** We try to avoid excessive duplication in tests.
If you have several tests repeating the same type of test setup,
consider making a setUp() method or a test helper.

- **Network independence** Our tests should still work if you don't
have an internet connection.  For third party clients, you can simulate
their behavior using fixture data.  For third party servers, you can
typically simulate their behavior using mocks.

- **Coverage** We have 100% line coverage on several of our backend
modules.  You can use the `--coverage` option to generate coverage
reports, and new code should have 100% coverage, which generally requires
testing not only the "happy path" but also error handling code and
edge cases.

