# Documentation systems

Zulip has three major documentation systems:

* Developer and sysadmin documentation: Documentation for people
  actually interacting with the Zulip codebase (either by developing
  it or installing it), and written in Markdown.

* Core website documentation: Complete webpages for complex topics,
  written in HTML, JavaScript, and CSS (using the Django templating
  system).  These roughly correspond to the documentation someone
  might look at when deciding whether to use Zulip.  We don't expect
  to ever have more than about 10 pages written using this system.

* User-facing documentation: Our scalable system for documenting
  Zulip's huge collection of specific features without a lot of
  overhead or duplicated code/syntax, written in Markdown.  We have
  several hundred pages written using this system.  There are 3
  branches of this documentation: user documentation (with a target
  audience of individual Zulip users), integrations documentation
  (with an audience of IT folks setting up integrations), and API
  documentaiton (with an audience of developers writing code to extend
  Zulip).

These three systems are documented in detail.

## Developer and sysadmin documentation

What you are reading right now is part of the collection of
documentation targeted at developers and people running their own
Zulip servers.  These docs are written in
[Commonmark Markdown](http://commonmark.org/) with a small bit of rST.
We've chosen Markdown because it is
[easy to write](http://commonmark.org/help).  The source for Zulip's
developer documentation is at `docs/` in the Zulip git repository, and
they are served in production at
[zulip.readthedocs.io](https://zulip.readthedocs.io/en/latest/).

If you want to build the developer documentation locally (e.g. to test
your changes), the dependencies are automatically installed as part of
Zulip development environment provisioning, and you can build the
documentation using:

```
./tools/build-docs
```

and then opening `http://127.0.0.1:9991/docs/index.html` in your
browser.  The raw files are available at
`file:///path/to/zulip/docs/_build/html/index.html` in your browser
(so you can also use e.g. `firefox docs/_build/html/index.html` from
the root of your Zulip checkout).

If you are adding a new page to the table of contents, you will want
to modify `docs/index.rst` and run `make clean` before `make html`, so
that other docs besides your new one also get the new entry in the
table of contents.

You can also usually test your changes by pushing a branch to GitHub
and looking at the content on the GitHub web UI, since GitHub renders
Markdown, though that won't be as faithful as the `make html`
approach.

When editing dependencies for the Zulip documentation, you should edit
`requirements/docs.in` and then run `tools/update-locked-requirements`
which updates docs.txt file (which is used by ReadTheDocs to build the
Zulip developer documentation, without installing all of Zulip's
dependencies).

## Core website documentation

Zulip has around 10 HTML documentation pages under `templates/zerver`
for specific major topics, like the features list, client apps,
integrations, hotkeys, API bindings, etc.  These documents often have
somewhat complex HTML and JavaScript, without a great deal of common
pattern between them other than inheriting from the `portico.html`
template.  We generally avoid adding new pages to this collection
unless there's a good reason, but we don't intend to migrate them,
either, since this system gives us the flexibility to express these
important elements of the product clearly.

## User facing documentation

All of these systems use a common Markdown-based framework with
various extensions for macros and variable interpolation,
(`render_markdown_path` in the code), designed to make it convenient
to do the things one does a lot in each type of documentation.

### General user documentation

To learn more about Zulip's general user documentation,
[visit it on zulipchat.com](https://zulipchat.com/help/) or
[read our guide on writing user documentation](user-docs.html).

### Integrations documentation

To learn more about Zulip's integrations documentation,
[visit it on zulipchat.com](https://zulipchat.com/integrations/) or
[read our guide on writing user documentation](integration-docs.html).

### API documentation

To learn more about Zulip's API documentation,
[visit it on zulipchat.com](https://zulipchat.com/api/) or
[read our tutorial on writing user documentation](../tutorials/documenting-api-endpoints.html).

## Automated testing

Zulip has several automated test suites that we run in CI and
recommend running locally when making significant edits:

* `tools/lint` catches a number of common mistakes, and we highly
recommend
[using our linter pre-commit hook](../git/zulip-tools.html#set-up-git-repo-script).
See the [main linter doc](../testing/linters.html) for more details.

* The ReadTheDocs docs are built and the links tested by
`tools/test-documentation`, which runs `build-docs` and then checks
all the links.

There's an exclude list for the link testing at this horrible path:
`tools/documentation_crawler/documentation_crawler/spiders/common/spiders.py`,
which is relevant for flaky links.

* The API docs are tested by `tools/test-api`, which does some basic
payload verification.  Note that this test does not check for broken
links (those are checked by `test-help-documentation`).

* `tools/test-help-documentation` checks `/help/`, `/api/`,
  `/integrations/`, and the Core website ("portico") documentation for
  broken links.  Note that the "portico" documentation check has a
  manually maintained whitelist of pages, so if you add a new page to
  this site, you will need to edit `PorticoDocumentationSpider` to add it.

* `tools/test-backend test_docs.py` tests various internal details of
  the variable substitution logic, as well as rendering.  It's
  essential when editing the documentation framework, but not
  something you'll usually need to interact with when editing
  documentation.
