# Testing and writing tests

## Overview

Zulip has a full test suite that includes many components.  The most
important components are documented in depth in their own sections:

- [Django](testing-with-django.html): backend Python tests
- [Casper](testing-with-casper.html): end-to-end UI tests
- [Node](testing-with-node.html): unit tests for JS front end code
- [Linters](linters.html): Our parallel linter suite
- [Travis CI details](travis.html): How all of these run in Travis CI

This document covers more general testing issues, such as how to run the
entire test suite, how to troubleshoot database issues, how to manually
test the front end, and how to plan for the future upgrade to Python3.

We also document [how to manually test the app](manual-testing.html).

## Running tests

Zulip tests must be run inside a Zulip development environment; if
you're using Vagrant, you will need to enter the Vagrant environment
before running the tests:

```
vagrant ssh
cd /srv/zulip
```

Then, to run the full Zulip test suite, do this:
```
./tools/test-all
```

This runs the linter (`tools/lint`) plus all of our test suites;
they can all be run separately (just read `tools/test-all` to see
them).  You can also run individual tests which can save you a lot of
time debugging a test failure, e.g.:

```
./tools/lint # Runs all the linters in parallel
./tools/test-backend zerver.tests.test_bugdown.BugdownTest.test_inline_youtube
./tools/test-backend BugdownTest # Run `test-backend --help` for more options
./tools/test-js-with-casper 09-navigation.js
./tools/test-js-with-node utils.js
```
The above setup instructions include the first-time setup of test
databases, but you may need to rebuild the test database occasionally
if you're working on new database migrations.  To do this, run:

```
./tools/do-destroy-rebuild-test-database
```

### Possible testing issues

- When running the test suite, if you get an error like this:

  ```
      sqlalchemy.exc.ProgrammingError: (ProgrammingError) function ts_match_locs_array(unknown, text, tsquery) does not   exist
      LINE 2: ...ECT message_id, flags, subject, rendered_content, ts_match_l...
                                                                   ^
  ```

  … then you need to install tsearch-extras, described
  above. Afterwards, re-run the `init*-db` and the
  `do-destroy-rebuild*-database` scripts.

- When building the development environment using Vagrant and the LXC
  provider, if you encounter permissions errors, you may need to
  `chown -R 1000:$(whoami) /path/to/zulip` on the host before running
  `vagrant up` in order to ensure that the synced directory has the
  correct owner during provision. This issue will arise if you run `id
  username` on the host where `username` is the user running Vagrant
  and the output is anything but 1000.
  This seems to be caused by Vagrant behavior; for more information,
  see [the vagrant-lxc FAQ entry about shared folder permissions][lxc-sf].

[lxc-sf]: https://github.com/fgrehm/vagrant-lxc/wiki/FAQ#help-my-shared-folders-have-the-wrong-owner

### Internet access inside test suites

As a policy matter, the Zulip test suites should never make outgoing
HTTP or other network requests.  This is important for 2 major
reasons:

* Tests that make outgoing Internet requests will fail when the user
  isn't on the Internet.
* Tests that make outgoing Internet requests often have a hidden
  dependency on the uptime of a third-party service, and will fail
  nondeterministically if that service has a temporary outage.
  Nondeterministically failing tests can be a big waste of
  developer time, and we try to avoid them wherever possible.

As a result, Zulip's major test suites should never access the
Internet directly.  Since code in Zulip does need to access the
Internet (e.g. to access various third-party APIs), this means that
the Zulip tests use mocking to basically hardcode (for the purposes of
the test) what responses should be used for any outgoing Internet
requests that Zulip would make in the code path being tested.

This is easy to do using test fixtures (a fancy word for fixed data
used in tests) and the `mock.patch` function to specify what HTTP
response should be used by the tests for every outgoing HTTP (or other
network) request.  Consult
[our guide on mocking](testing-with-django.html#zulip-mocking-practices) to
learn how to mock network requests easily; there are also a number of
examples throughout the codebase.

We partially enforce this policy in the main Django/backend test suite
by overriding certain library functions that are used in outgoing HTTP
code paths (`httplib2.Http().request`, `requests.request`, etc.) to
throw an exception in the backend tests.  While this is enforcement is
not complete (there a lot of other ways to use the Internet from
Python), it is easy to do and catches most common cases of new code
dependning on Internet access.

This enforcement code results in the following exception:

  ```
  File "tools/test-backend", line 120, in internet_guard
    raise Exception("Outgoing network requests are not allowed in the Zulip tests."
  Exception: Outgoing network requests are not allowed in the Zulip tests.
  ...
  ```

#### Documentation tests

The one exception to this policy is our documentation tests, which
will attempt to verify that the links included in our documentation
aren't broken.  Those tests end up failing nondeterministically fairly
often, which is unfortunate, but there's simply no other correct way
to verify links other than attempting to access them.

## Schema and initial data changes

If you change the database schema or change the initial test data, you
have to regenerate the pristine test database by running
`tools/do-destroy-rebuild-test-database`.

## Wiping the test databases

You should first try running: `tools/do-destroy-rebuild-test-database`

If that fails you should try to do:

    sudo -u postgres psql
    > DROP DATABASE zulip_test;
    > DROP DATABASE zulip_test_template;

and then run `tools/do-destroy-rebuild-test-database`

### Recreating the postgres cluster

> **warning**
>
> **This is irreversible, so do it with care, and never do this anywhere
> in production.**

If your postgres cluster (collection of databases) gets totally trashed
permissions-wise, and you can't otherwise repair it, you can recreate
it. On Ubuntu:

    sudo pg_dropcluster --stop 9.1 main
    sudo pg_createcluster --locale=en_US.utf8 --start 9.1 main

## Local browser testing (local app + web browser)

This section is about troubleshooting your local development environment.

There is a [separate manual testing doc](manual-testing.html) that
enumerates things you can test as part of manual QA.

### Clearing the development database

You can use:

    ./tools/do-destroy-rebuild-database

to drop the database on your development environment and repopulate
your it with the Shakespeare characters and some test messages between
them.  This is run automatically as part of the development
environment setup process, but is occasionally useful when you want to
return to a clean state for testing.

### JavaScript manual testing

`debug.js` has some tools for profiling JavaScript code, including:

-   \`print\_elapsed\_time\`: Wrap a function with it to print the time
    that function takes to the JavaScript console.
-   \`IterationProfiler\`: Profile part of looping constructs (like a
    for loop or \$.each). You mark sections of the iteration body and
    the IterationProfiler will sum the costs of those sections over all
    iterations.

Chrome has a very good debugger and inspector in its developer tools.
Firebug for Firefox is also pretty good. They both have profilers, but
Chrome's is a sampling profiler while Firebug's is an instrumenting
profiler. Using them both can be helpful because they provide different
information.
