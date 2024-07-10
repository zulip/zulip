# Testing philosophy

Zulip's automated tests are a huge part of what makes the project able
to make progress. This page records some of the key principles behind
how we have designed our automated test suites.

## Effective testing allows us to move quickly

Zulip's engineering strategy can be summarized as "move quickly
without breaking things". Despite reviewing many code submissions
from new contributors without deep expertise in the code they are
changing, Zulip's maintainers spend most of the time they spend
integrating changes on product decisions and code
structure/readability questions, not on correctness, style, or
lower-level issues.

This is possible because we have spent years systematically investing
in testing, tooling, code structure, documentation, and development
practices to help ensure that our contributors write code that needs
relatively few changes before it can be merged. The testing element
of this is to have reliable, extensive, easily extended test suites
that cover most classes of bugs. Our testing systems have been
designed to minimize the time spent manually testing or otherwise
investigating whether changes are correct.

For example, our [infrastructure for testing
authentication](../development/authentication.md) allows using a mock
LDAP database in both automated tests and the development environment,
making it much easier now to refactor and improve this important part of
the product than it was when you needed to set up an LDAP server and
populate it with some test data in order to test LDAP authentication.

While not every part of Zulip has a great test suite, many components
do, and for those components, the tests mean that new contributors can
often make substantive changes and have them be
more or less correct by the time they share the
changes for code review. More importantly, it means that maintainers
save most of the time that would otherwise be spent verifying that the
changes are simply correct, and instead focus on making sure that the
codebase remains readable, well-structured, and well-tested.

## Test suite performance and reliability are critical

When automated test suites are slow or unreliable, developers will
avoid running them, and furthermore, avoid working on improving them
(both the system and individual tests). Because changes that make
tests slow or unreliable are often unintentional side effects of other
development, problems in this area tend to accumulate as a codebase
grows. As a result, barring focused effort to prevent this outcome,
any large software project will eventually have its test suite rot
into one that is slow, unreliable, untrustworthy, and hated. We aim
for Zulip to avoid that fate.

So we consider it essential to maintaining every automated test suite
setup in a way where it is fast and reliable (tests pass both in CI
and locally if there are no problems with the developer's changes).

Concretely, our performance goals are for the full backend suite
(`test-backend`) to complete in about a minute, and our full frontend
suite (`test-js-with-node`) to run in under 10 seconds.

It'd be a long blog post to summarize everything we do to help achieve
these goals, but a few techniques are worth highlighting:

- Our test suites are designed to not access the Internet, since the
  Internet might be down or unreliable in the test environment. Where
  outgoing HTTP requests are required to test something, we mock the
  responses with libraries like `responses`.
- We carefully avoid the potential for contamination of data inside
  services like PostgreSQL, Redis, and memcached from different tests.
  - Every test case prepends a unique random prefix to all keys it
    uses when accessing Redis and memcached.
  - Every test case runs inside a database transaction, which is
    aborted after the test completes. Each test process interacts
    only with a fresh copy of a special template database used for
    server tests that is destroyed after the process completes.
- We rigorously investigate non-deterministically failing tests as though
  they were priority bugs in the product.

## Integration testing or unit testing?

Developers frequently ask whether they should write "integration
tests" or "unit tests". Our view is that tests should be written
against interfaces that you're already counting on keeping stable, or
already promising people you'll keep stable. In other words,
interfaces that you or other people are already counting on mostly not
changing except in compatible ways.

So writing tests for the Zulip server against Zulip's end-to-end API
is a great example of that: the API is something that people have
written lots of code against, which means all that code is counting on
the API generally continuing to work for the ways they're using it.

The same would be true even if the only users of the API were our own
project's clients like the mobile apps -- because there are a bunch of
already-installed copies of our mobile apps out there, and they're
counting on the API not suddenly changing incompatibly.

One big reason for this principle is that when you write tests against
an interface, those tests become a cost you pay any time you change
that interface -- you have to go update a bunch of tests.

So in a big codebase if you have a lot of "unit tests" that are for
tiny internal functions, then any time you refactor something and
change the internal interfaces -- even though you just made them up,
and they're completely internal to that codebase so there's nothing
that will break if you change them at will -- you have to go deal with
editing a bunch of tests to match the new interfaces. That's
especially a lot of work if you try to take the tests seriously,
because you have to think through whether the tests breaking are
telling you something you should actually listen to.

In some big codebases, this can lead to tests feeling a lot like
busywork... and it's because a lot of those tests really are
busywork. And that leads to developers not being committed to
maintaining and expanding the test suite in a thoughtful way.

But if your tests are written against an external API, and you make
some refactoring change and a bunch of tests break... now that's
telling you something very real! You can always edit the tests... but
the tests are stand-ins for real users and real code out there beyond
your reach, which will break the same way.

So you can still make the change... but you have to deal with figuring
out an appropriate migration or backwards-compatibility strategy for
all those real users out there. Updating the tests is one of the easy
parts. And those changes to the tests are a nice reminder to code
reviewers that you've changed an interface, and the reviewer should
think carefully about whether those interface changes will be a
problem for any existing clients and whether they're properly reflected
in any documentation for that interface.

Some examples of this philosophy:

- If you have a web service that's mainly an API, you want to write
  your tests for that API.
- If you have a CLI program, you want to write your tests against the
  CLI.
- If you have a compiler, an interpreter, etc., you want essentially
  all your tests to be example programs, with a bit of metadata for
  things like "should give an error at this line" or "should build and
  run, and produce this output".

In the Zulip context:

- Zulip uses the same API for our web app as for our mobile clients and
  third-party API clients, and most of our server tests are written
  against the Zulip API.
- The tests for Zulip's incoming webhooks work by sending actual
  payloads captured from the real third-party service to the webhook
  endpoints, and verifies that the webhook produces the expected Zulip
  message as output, to test the actual interface.

So, to summarize our approach to integration vs. unit testing:

- While we aim to achieve test coverage of every significant code path
  in the Zulip server, which is commonly associated with unit testing,
  most of our tests are integration tests in the sense of sending a
  complete HTTP API query to the Zulip server and checking that the
  HTTP response and the internal state of the server following the request
  are both correct.
- Following the end-to-end principle in system design, where possible
  we write tests that execute a complete flow (e.g., registering a new
  Zulip account) rather than testing the implementations of individual
  functions.
- We invest in the performance of Zulip in part to give users a great
  experience, but just as much to make our test suite fast enough
  that we can write our tests this way.

## Avoid duplicating code with security impact

Developing secure software with few security bugs is extremely
difficult. An important part of our strategy for avoiding security
logic bugs is to design patterns for how all of our code that
processes untrusted user input can be well tested without either
writing (and reviewing!) endless tests or requiring every developer to
be good at thinking about security corner cases.

Our strategy for this is to write a small number of carefully-designed
functions like `access_stream_by_id` that we test carefully, and then
use linting and other coding conventions to require that all access to
data from code paths that might share that data with users be mediated
through those functions. So rather than having each view function do
it own security checks for whether the user can access a given channel,
and needing to test each of those copies of the logic, we only need to
do that work once for each major type of data structure and level of
access.

These `access_*_by_*` functions are written in a special style, with each
conditional on its own line (so our test coverage tooling helps verify
that every case is tested), detailed comments, and carefully
considered error-handling to avoid leaking information such as whether
the channel ID requested exists or not.

We will typically also write tests for a given view verifying that it
provides the appropriate errors when improper access is attempted, but
these tests are defense in depth; the main way we prevent invalid
access to channels is not offering developers a way to get a `Stream`
object in server code except as mediated through these security check
functions.

## Share test setup code

It's very common to need to write tests for permission checking or
error handling code. When doing this, it's best to share the test
setup code between success and failure tests.

For example, when testing a function that returns a boolean (as
opposed to an exception with a specific error messages), it's often
better to write a single test function, `test_foo`, that calls the
function several times and verifies its output for each value of the
test conditions.

The benefit of this strategy is that you guarantee that the test setup
only differs as intended: Done well, it helps avoid the otherwise
extremely common failure mode where a `test_foo_failure` test passes
for the wrong reason. (e.g., the action fails not because of the
permission check, but because a required HTTP parameter was only added
to an adjacent `test_foo_success`).

## What isn't tested probably doesn't work

Even the very best programmers make mistakes constantly. Further, it's
impossible to do large codebase refactors (which are important to
having a readable, happy, correct codebase) if doing so has a high
risk of creating subtle bugs.

As a result, it's important to test every change. For business logic,
the best option is usually a high-quality automated test, that is
designed to be robust to future refactoring.

But for some things, like documentation and CSS, the only way to test
is to view the element in a browser and try things that might not
work. What to test will vary with what is likely to break. For
example, after a significant change to Zulip's Markdown documentation,
if you haven't verified every special bit of formatting visually and
clicked every new link, there's a good chance that you've introduced a
bug.

Manual testing not only catches bugs, but it also helps developers
learn more about the system and think about the existing semantics of
a feature they're working on.

When submitting a pull request that affects UI, it's extremely helpful
to show a screencast of your feature working, because that allows a
reviewer to save time that would otherwise be spent manually testing
your changes.
