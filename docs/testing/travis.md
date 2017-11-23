# Travis CI

The Zulip server uses [Travis CI](https://travis-ci.org/) for its
continuous integration.  This page documents useful tools and tips to
know about when using Travis CI and debugging issues with it.

## Goals

The overall goal of our Travis CI setup is to avoid regressions and
minimize the total time spent debugging Zulip.  We do that by trying
to catch as many possible future bugs as possible, while minimizing
both latency and false positives, both of which can waste a lot of
developer time.  There are a few implications of this overall goal:

* If a test is failing nondeterministically in Travis CI, we consider
  that to be an urgent problem.
* If the tests become a lot slower, that is also an urgent problem.
* Everything we do in CI should also have a way to run it quickly
(under 1 minute, preferably under 3 seconds), in order to iterate fast
in development. Except when working on the Travis CI configuration
itself, a developer should never have to repeatedly wait 10 minutes
for a full Travis run to iteratively debug something.

## Configuration

The main Travis configuration file is
[.travis.yml](https://github.com/zulip/zulip/blob/master/.travis.yml).
The specific test suites we have are listed in the `matrix` section,
which has a matrix of Python versions and test suites (`$TEST_SUITE`).
We've configured it to use a few helper scripts for each job:

* `tools/travis/setup-$TEST_SUITE`: The script that sets up the test
  environment for that suite (E.g., installing dependencies).
  * For the backend and frontend suites, this is a thin wrapper around
    `tools/provision`, aka the development environment provision script.
  * For the production suite, this is a more complicated process
    because of all the packages Travis installs.  See the comments in
    `tools/travis/setup-production` for details.
* `tools/travis/$TEST_SUITE`: The script that runs the actual test
  suite.

The main purpose of the distinction between the two is that if the
`setup-backend` job fails, Travis CI will report it as the suite
having "Errored" (grey in their emails), whereas if the `backend` job
fails, it'll be reported as "Failed" failure (red in their emails).
Note that Travis CI's web UI seems to make no visual distinction
between these.

An important detail is that Travis CI will by default hide most phases
other than the actual test; you can see this easily by looking at the
line numbers in the Travis CI output.  There are actually a bunch of
phases (e.g. the project's setup job, downloading caches near the
beginning, uploading caches at the end, etc.), and if you're debugging
our configuration, you'll want to look at these closely.

## Useful debugging tips and tools

* Zulip uses the `ts` tool to log the current time on every line of
  the output in our Travis CI scripts.  You can use this output to
  determine which steps are actually consuming a lot of time.

* For performance issues,
  [this statistics tool](https://scribu.github.io/travis-stats/#zulip/zulip/master)
  can give you test runtime history data that can help with
  determining when a performance issue was introduced and whether it
  was fixed.  Note you need to click the "Run" button for it to do
  anything.

* You can [sign up your personal repo for Travis CI][travis-fork] so
  that every remote branch you push will be tested, which can be
  helpful when debugging something complicated.

[travis-fork]: ../git/cloning.html#step-3-configure-travis-ci-continuous-integration

## Performance optimizations

### Caching

An important element of making Travis CI perform effectively is
caching the provisioning of a Zulip development environment.  In
particular, we cache the following across jobs:

* Python virtualenvs
* node_modules directories
* Built/downloaded emoji sprite sheets and data

This has a huge impact on the performance of running tests in Travis
CI; without these caches, the average test time would be several times
longer.

We have designed these caches carefully (they are also used in
production and the Zulip development environment) to ensure that each
is named by a hash of its dependencies, so Zulip should always be
using the same version of dependencies it would have used had the
cache not existed.  In practice, bugs are always possible, so be
mindful of this possibility.

A consequence of this caching is that test jobs for branches which
modify `package.json`, `requirements/`, and other key dependencies
will be significantly slower than normal, because they won't get to
benefit from the cache.

### Uninstalling packages

In the production suite, we run `apt-get upgrade` at some point
(effectively, because the Zulip installer does).  This carries a huge
performance cost in Travis CI, because (1) they don't keep their test
systems up to date and (2) literally everything is installed in their
build workers (e.g. several copies of Postgres, Java, MySQL, etc.).

In order to make Zulip's tests performance reasonably well, we
uninstall (or mark with `apt-mark hold`) many of these dependencies
that are irrelevant to Zulip in
[`tools/travis/setup-production`][setup-production].

[setup-production]: https://github.com/zulip/zulip/blob/master/tools/travis/setup-production
