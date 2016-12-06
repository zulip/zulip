# Documentation

Zulip has three major documentation systems:

* Developer and sysadmin documentation: Documentation for people
  actually interacting with the Zulip codebase (either by developing
  it or installing it), and written in Markdown.

* Core website documentation: Complete webpages for complex topics,
  written in HTML, JavaScript, and CSS (using the Django templating
  system).  These roughly correspond to the documentation someone
  might look at when deciding whether to use Zulip.  We don't expect
  to ever have more than about 10 pages written using this system.

* General user documentation: Our scalable system for documenting
  Zulip's huge collection of specific features without a lot of
  overhead or duplicated code/syntax, written in Markdown.  We expect
  to eventually have around 100 pages written using this system.  The
  target audience for this system is individual Zulip users.

These three systems are documented in detail below.

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
cd docs/
make html
```

and then opening `file:///path/to/zulip/docs/_build/html/index.html` in
your browser (you can also use e.g. `firefox
docs/_build/html/index.html` from the root of your Zulip checkout).

If you are adding a new page to the table of contents, you will want
to modify `docs/index.rst` and run `make clean` before `make html`, so
that other docs besides your new one also get the new entry in the
table of contents.

You can also usually test your changes by pushing a branch to GitHub
and looking at the content on the GitHub web UI, since GitHub renders
Markdown, though that won't be as faithful as the `make html`
approach.

When editing dependencies for the Zulip documentation, you should edit
`requirements/docs.txt` (which is used by ReadTheDocs to build the
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

## General user documentation

Our goal is for Zulip to have complete, high-quality user-facing
documentation about how to use every feature and how to do common
tasks (like setting up a new Zulip organization well).  This system is
designed to make writing and maintaining such documentation highly
efficient.

The user documentation is available under `/help/` on any Zulip
server;
(e.g. [https://chat.zulip.org/help/](https://chat.zulip.org/help/) or
`http://localhost:9991/help/` in the Zulip development environment).
The user documentation is not hosted on ReadTheDocs, since Zulip
supports running a server completely disconnected from the Internet,
and we'd like the documentation to be available in that environment.

The source for this user documentation is the Markdown files under
`templates/zerver/help/` in the
[main Zulip server repository](https://github.com/zulip/zulip).  The
file `foo.md` is automatically rendered by the `render_markdown_path`
function in `zerver/templatetags/app_filters.py` when the user
accesses a URL of the form `/help/foo`; with special cases for
`/help/` going to `index.md` and `/help/unknown_article` going to
`missing.md` (with a 404 response).  Images are usually linked from
`static/images/help/`.

This means that you can contribute to the Zulip user documentation by
just adding to or editing the collection of markdown files under
`templates/zerver/help`.  If you have the Zulip development
environment setup, you simply need to reload your browser on
`http://localhost:9991/help/foo` to see the latest version of `foo.md`
rendered.

Since raw HTML is supported in Markdown, you can include arbitraty
HTML in your documentation in order to do fancy things like
highlighting an important aspect of your code.  We'll likely add a
library of common components over time, which will be documented
below.

### Supported features

* All the usual features of Markdown with raw HTML enabled so you can
  do custom things as needed.
* Code blocks with syntax highlighting.
* Anchor tags for linking to headers in other documents.
