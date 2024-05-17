# Documentation systems

Zulip has three major documentation systems:

- **Developer and sysadmin documentation**: Documentation for people
  actually interacting with the Zulip codebase (either by developing
  it or installing it), and written in Markdown.

- **Core website documentation**: Complete webpages for complex topics,
  written in HTML, JavaScript, and CSS (using the Django templating
  system). These roughly correspond to the documentation someone
  might look at when deciding whether to use Zulip. We don't expect
  to ever have more than about 10 pages written using this system.

- **User-facing documentation**: Our scalable system for documenting
  Zulip's huge collection of specific features without a lot of
  overhead or duplicated code/syntax, written in Markdown. We have
  several hundred pages written using this system. There are 3
  branches of this documentation:
  - [Help center documentation](#help-center-documentation)
    (with a target audience of individual Zulip users)
  - [Integrations documentation](#integrations-documentation)
    (with a target audience of IT folks setting up integrations)
  - [API documentation](#api-documentation) (with a target audience
    of developers writing code to extend Zulip)

These three systems are documented in detail.

## Developer and sysadmin documentation

What you are reading right now is part of the collection of
documentation targeted at developers and people running their own
Zulip servers. These docs are written in
[CommonMark Markdown](https://commonmark.org/).
We've chosen Markdown because it is
[easy to write](https://commonmark.org/help/). The source for Zulip's
developer documentation is at `docs/` in the Zulip Git repository, and
they are served in production at
[zulip.readthedocs.io](https://zulip.readthedocs.io/en/latest/).

This documentation is hosted by the excellent [ReadTheDocs
service](https://readthedocs.org/). ReadTheDocs automatically [builds
a preview](https://docs.readthedocs.io/en/stable/pull-requests.html)
for every pull request, accessible from a "Details" link in the
"Checks" section of the pull request page. It's nonetheless valuable
to submit a screenshot with any pull request modifying documentation
to help make reviews efficient.

If you want to build the developer documentation locally (e.g. to test
your changes), the dependencies are automatically installed as part of
Zulip development environment provisioning, and you can build the
documentation using:

```bash
./tools/build-docs
```

and then opening `http://127.0.0.1:9991/docs/index.html` in your
browser. The raw files are available at
`file:///path/to/zulip/docs/_build/html/index.html` in your browser
(so you can also use e.g. `firefox docs/_build/html/index.html` from
the root of your Zulip checkout).

If you are adding a new page to the table of contents, you will want
to modify `docs/index.md` and run `make clean` before `make html`, so
that other docs besides your new one also get the new entry in the
table of contents.

You can also usually test your changes by pushing a branch to GitHub
and looking at the content on the GitHub web UI, since GitHub renders
Markdown, though that won't be as faithful as the `make html`
approach or the preview build.

When editing dependencies for the Zulip documentation, you should edit
`requirements/docs.in` and then run `tools/update-locked-requirements`
which updates docs.txt file (which is used by ReadTheDocs to build the
Zulip developer documentation, without installing all of Zulip's
dependencies).

## Core website documentation

Zulip has around 10 HTML documentation pages under `templates/zerver`
for specific major topics, like the features list, client apps,
integrations, hotkeys, API bindings, etc. These documents often have
somewhat complex HTML and JavaScript, without a great deal of common
patterns between them other than inheriting from the `portico.html`
template. We generally avoid adding new pages to this collection
unless there's a good reason, but we don't intend to migrate them,
either, since this system gives us the flexibility to express these
important elements of the product clearly.

## User-facing documentation

All of these systems use a common Markdown-based framework with
various extensions for macros and variable interpolation,
(`render_markdown_path` in the code), designed to make it convenient
to do the things one does a lot in each type of documentation.

### Help center documentation

Zulip's [help center](https://zulip.com/help/) documentation is
designed to explain how the product works to end users. We aim for
this to be clear, concise, correct, and readable to nontechnical
audiences where possible.

See our guide on [writing help center articles](helpcenter.md).

### Integrations documentation

Zulip's [integrations documentation](https://zulip.com/integrations/)
is user-facing documentation explaining to end users how to set up each
of Zulip's more than 100 integrations. There is a detailed [guide on
documenting integrations](integrations.md), including style guidelines
to ensure that the documentation is high quality and consistent.

See also our broader [integrations developer
guide](https://zulip.com/api/integrations-overview).

### API documentation

Zulip's [API documentation](https://zulip.com/api/) is intended to make
it easy for a technical user to write automation tools that interact
with Zulip. This documentation also serves as our main mechanism for
Zulip server developers to communicate with client developers about
how the Zulip API works.

See the [API documentation tutorial](api.md) for
details on how to contribute to this documentation.

## Automated testing

Zulip has several automated test suites that we run in CI and
recommend running locally when making significant edits:

- `tools/lint` catches a number of common mistakes, and we highly
  recommend
  [using our linter pre-commit hook](../git/zulip-tools.md#set-up-git-repo-script).
  See the [main linter doc](../testing/linters.md) for more details.

- The ReadTheDocs docs are built and the links tested by
  `tools/test-documentation`, which runs `build-docs` and then checks
  all the links.

There's an exclude list for the link testing at this horrible path:
`tools/documentation_crawler/documentation_crawler/spiders/common/spiders.py`,
which is relevant for flaky links.

- The API docs are tested by `tools/test-api`, which does some basic
  payload verification. Note that this test does not check for broken
  links (those are checked by `test-help-documentation`).

- `tools/test-help-documentation` checks `/help/`, `/api/`,
  `/integrations/`, and the core website ("portico") documentation for
  broken links. Note that the "portico" documentation check has a
  manually maintained whitelist of pages, so if you add a new page to
  this site, you will need to edit `PorticoDocumentationSpider` to add it.

- `tools/test-backend test_docs.py` tests various internal details of
  the variable substitution logic, as well as rendering. It's
  essential when editing the documentation framework, but not
  something you'll usually need to interact with when editing
  documentation.
