# Testing and writing tests

## Overview

Zulip has a full test suite that includes many components.  The most
important components are documented in depth in their own sections:

- [Django](testing-with-django.html): backend Python tests
- [Casper](testing-with-casper.html): end-to-end UI tests
- [Node](testing-with-node.html): unit tests for JS front end code
- [Linters](linters.html)

This document covers more general testing issues, such as how to run the
entire test suite, how to troubleshoot database issues, how to manually
test the front end, and how to plan for the future upgrade to Python3.

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

This runs the linter (`tools/lint-all`) plus all of our test suites;
they can all be run separately (just read `tools/test-all` to see
them).  You can also run individual tests which can save you a lot of
time debugging a test failure, e.g.:

```
./tools/lint-all # Runs all the linters in parallel
./tools/test-backend zerver.tests.test_bugdown.BugdownTest.test_inline_youtube
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

## Manual testing (local app + web browser)

### Clearing the manual testing database

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

## Python 3 Compatibility

Zulip is working on supporting Python 3, and all new code in Zulip
should be Python 2+3 compatible. We have converted most of the codebase
to be compatible with Python 3 using a suite of 2to3 conversion tools
and some manual work. In order to avoid regressions in that
compatibility as we continue to develop new features in Zulip, we have a
special tool, `tools/check-py3`, which checks all code for Python 3
syntactic compatibility by running a subset of the automated migration
tools and checking if they trigger any changes. `tools/check-py3` is run
automatically in Zulip's Travis CI tests (in the 'static-analysis'
build) to avoid any regressions, but is not included in `test-all` since
it is quite slow.

To run `tools/check-py3`, you need to install the `modernize` and
`future` Python packages (which are included in
`requirements/py3k.txt`, which itself is included in
`requirements/dev.txt`, so you probably already have these packages
installed).

To run `check-py3` on just the Python files in a particular directory, you
can change the current working directory (e.g. `cd zerver/`) and run
`check-py3` from there.
