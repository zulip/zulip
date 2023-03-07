# Testing overview

Zulip takes pride in its extensive, carefully designed test suites.
For example, `test-backend` runs a complete test suite (~98% test
coverage; 100% on core code) for the Zulip server in under a minute on
a fast laptop; very few web apps of similar scope can say something
similar.

This page focused on the mechanics of running automated tests in a
[development environment](../development/overview.md); you may also
want to read about our [testing philosophy](philosophy.md)
and [continuous integration
setup](continuous-integration.md).

Manual testing with a web browser is primarily discussed in the docs
on [using the development environment](../development/using.md).

## Running tests

Zulip tests must be run inside a Zulip development environment; if
you're using Vagrant, you may need to enter it with `vagrant ssh`.

You can run all of the test suites (similar to our continuous integration)
as follows:

```bash
./tools/test-all
```

However, you will rarely want to do this while actively developing,
because it takes a long time. Instead, your edit/refresh cycle will
typically involve running subsets of the tests with commands like these:

```bash
./tools/lint zerver/models.py # Lint the file you just changed
./tools/test-backend zerver.tests.test_markdown.MarkdownTest.test_inline_youtube
./tools/test-backend MarkdownTest # Run `test-backend --help` for more options
./tools/test-js-with-node util
# etc.
```

The commands above will all run in just a few seconds. Many more
useful options are discussed in each tool's documentation (e.g.
`./tools/test-backend --help`).

## Major test suites

Zulip has a handful of major tests suite that every developer will
eventually work with, each with its own page detailing how it works:

- [Linters](linters.md): Our dozen or so linters run in parallel.
- [Django](testing-with-django.md): Server/backend Python tests.
- [Node](testing-with-node.md): JavaScript tests for the
  frontend run via node.js.
- [Puppeteer](testing-with-puppeteer.md): End-to-end
  UI tests run via a Chromium browser.

## Other test suites

Additionally, Zulip also has about a dozen smaller tests suites:

- `tools/test-migrations`: Checks whether the `zerver/migrations`
  migration content the models defined in `zerver/models.py`. See our
  [schema migration documentation](../subsystems/schema-migrations.md)
  for details on how to do database migrations correctly.
- `tools/test-documentation`: Checks for broken links in this
  ReadTheDocs documentation site.
- `tools/test-help-documentation`: Checks for broken links in the
  `/help/` help center documentation, and related pages.
- `tools/test-api`: Tests that the API documentation at `/api`
  actually works; the actual code for this is defined in
  `zerver/openapi/python_examples.py`.
- `test-locked-requirements`: Verifies that developers didn't forget
  to run `tools/update-locked-requirements` after modifying
  `requirements/*.in`. See
  [our dependency documentation](../subsystems/dependencies.md) for
  details on the system this is verifying.
- `tools/check-capitalization`: Checks whether translated strings (aka
  user-facing strings) correctly follow Zulip's capitalization
  conventions. This requires some maintenance of an exclude list
  (`tools.lib.capitalization.IGNORED_PHRASES`) of proper nouns
  mentioned in the Zulip project, but helps a lot in avoiding new
  strings being added that don't match our style.
- `tools/check-frontend-i18n`: Checks for a common bug in Handlebars
  templates, of using the wrong syntax for translating blocks
  containing variables.
- `./tools/test-run-dev`: Checks that `run-dev` starts properly;
  this helps prevent bugs that break the development environment.
- `./tools/test-queue-worker-reload`: Verifies that Zulip's queue
  processors properly reload themselves after code changes.
- `./tools/setup/optimize-svg`: Checks whether all integration logo SVG
  graphics are optimized.
  logos are properly optimized for size (since we're not going to edit
  third-party logos, this helps keep the Zulip codebase from getting huge).
- `./tools/test-tools`: Automated tests for various parts of our
  development tooling (mostly various linters) that are not used in
  production.

Each of these has a reason (usually, performance or a need to do messy
things to the environment) why they are not part of the handful of
major test suites like `test-backend`, but they all contribute
something valuable to helping keep Zulip bug-free.

## Internet access inside test suites

As a policy matter, the Zulip test suites should never make outgoing
HTTP or other network requests. This is important for 2 major
reasons:

- Tests that make outgoing Internet requests will fail when the user
  isn't on the Internet.
- Tests that make outgoing Internet requests often have a hidden
  dependency on the uptime of a third-party service, and will fail
  nondeterministically if that service has a temporary outage.
  Nondeterministically failing tests can be a big waste of
  developer time, and we try to avoid them wherever possible.

As a result, Zulip's major test suites should never access the
Internet directly. Since code in Zulip does need to access the
Internet (e.g. to access various third-party APIs), this means that
the Zulip tests use mocking to basically hardcode (for the purposes of
the test) what responses should be used for any outgoing Internet
requests that Zulip would make in the code path being tested.

This is easy to do using test fixtures (a fancy word for fixed data
used in tests) and the `mock.patch` function to specify what HTTP
response should be used by the tests for every outgoing HTTP (or other
network) request. Consult
[our guide on mocking](testing-with-django.md#zulip-mocking-practices) to
learn how to mock network requests easily; there are also a number of
examples throughout the codebase.

We partially enforce this policy in the main Django/backend test suite
by overriding certain library functions that are used in outgoing HTTP
code paths (`httplib2.Http().request`, `requests.request`, etc.) to
throw an exception in the backend tests. While this is enforcement is
not complete (there a lot of other ways to use the Internet from
Python), it is easy to do and catches most common cases of new code
depending on Internet access.

This enforcement code results in the following exception:

```pytb
File "tools/test-backend", line 120, in internet_guard
  raise Exception("Outgoing network requests are not allowed in the Zulip tests."
Exception: Outgoing network requests are not allowed in the Zulip tests.
...
```

#### Documentation tests

The one exception to this policy is our documentation tests, which
will attempt to verify that the links included in our documentation
aren't broken. Those tests end up failing nondeterministically fairly
often, which is unfortunate, but there's simply no other correct way
to verify links other than attempting to access them. The compromise
we've implemented is that in CI, these tests only verify links to
websites controlled by the Zulip project (zulip.com, our GitHub,
our ReadTheDocs), and not links to third-party websites.
