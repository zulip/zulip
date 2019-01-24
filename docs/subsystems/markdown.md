# Markdown implementation

Zulip has a special flavor of Markdown, currently called 'bugdown'
after Zulip's original name of "humbug". End users are using Bugdown
within the client, not original Markdown.

Zulip has two implementations of Bugdown.  The backend implementation
at `zerver/lib/bugdown/` is based on
[Python-Markdown](https://pypi.python.org/pypi/Markdown) and is used to
authoritatively render messages to HTML (and implements
slow/expensive/complex features like querying the Twitter API to
render tweets nicely).  The frontend implementation is in JavaScript,
based on [marked.js](https://github.com/chjj/marked)
(`static/js/echo.js`), and is used to preview and locally echo
messages the moment the sender hits enter, without waiting for round
trip from the server.  Those frontend renderings are only shown to the
sender of a message, and they are (ideally) identical to the backend
rendering.

The JavaScript markdown implementation has a function,
`markdown.contains_backend_only_syntax`, that is used to check whether a message
contains any syntax that needs to be rendered to HTML on the backend.
If `markdown.contains_backend_only_syntax` returns true, the frontend simply won't
echo the message for the sender until it receives the rendered HTML
from the backend.  If there is a bug where `markdown.contains_backend_only_syntax`
returns false incorrectly, the frontend will discover this when the
backend returns the newly sent message, and will update the HTML based
on the authoritative backend rendering (which would cause a change in
the rendering that is visible only to the sender shortly after a
message is sent).  As a result, we try to make sure that
`markdown.contains_backend_only_syntax` is always correct.

## Testing

The Python-Markdown implementation is tested by
`zerver/tests/test_bugdown.py`, and the marked.js implementation and
`markdown.contains_backend_only_syntax` are tested by
`frontend_tests/node_tests/markdown.js`.

A shared set of fixed test data ("test fixtures") is present in
`zerver/tests/fixtures/markdown_test_cases.json`, and is automatically used
by both test suites; as a result, it is the preferred place to add new
tests for Zulip's markdown system.  Some important notes on reading
this file:

* `expected_output` is the expected output for the backend markdown
  processor.
* When the frontend processor doesn't support a feature and it should
  just be rendered on the backend, we set `backend_only_rendering` to
  `true` in the fixtures; this will automatically verify that
  `markdown.contains_backend_only_syntax` rejects the syntax, ensuring
  it will be rendered only by the backend processor.
* When the two processors disagree, we set `marked_expected_output` in
  the fixtures; this will ensure that the syntax stays that way.  If
  the differences are important (i.e. not just whitespace), we should
  also open an issue on GitHub to track the problem.
* For mobile push notifications, we need a text version of the
  rendered content, since the APNS and GCM push notification systems
  don't support richer markup.  Mostly, this involves stripping HTML,
  but there's some syntax we take special care with.  Tests for what
  this plain-text version of content should be are stored in the
  `text_content` field.

If you're going to manually test some changes in the frontend Markdown
implementation, the easiest way to do this is as follows:

1. Login to your development server.
2. Stop your Zulip server with ctrl-C, leaving the browser open.
3. Compose and send the messages you'd like to test.  They will be
   locally echoed using the frontend rendering.

This procedure prevents any server-side rendering.  If you don't do
this, backend will likely render the Markdown you're testing and swap
it in before you can see the frontend's rendering.

If you are working on a feature that breaks multiple testcases, and want
to debug the testcases one by one, you can add `"ignore": true` to any
testcases in `markdown_test_cases.json` that you want to ignore. This
is a workaround due to lack of comments support in JSON. Revert your
"ignore" changes before committing. After this, you can run the frontend
tests with `tools/test-js-with-node markdown` and backend tests with
`tools/test-backend zerver.tests.test_bugdown.BugdownTest.test_bugdown_fixtures`.

## Changing Zulip's markdown processor

First, you will likely find these third-party resources helpful:

* **[Python-Markdown](https://pypi.python.org/pypi/Markdown)** is the markdown
  library used by Zulip as a base to build our custom markdown syntax upon.
* **[Python's XML ElementTree](https://docs.python.org/3/library/xml.etree.elementtree.html)**
  is the part of the Python standard library used by Python Markdown
  and any custom extensions to generate and modify the output HTML.

When changing Zulip's markdown syntax, you need to update several
places:

* The backend markdown processor (`zerver/lib/bugdown/__init__.py`).
* The frontend markdown processor (`static/js/markdown.js` and sometimes
  `static/third/marked/lib/marked.js`), or `markdown.contains_backend_only_syntax` if
  your changes won't be supported in the frontend processor.
* If desired, the typeahead logic in `static/js/composebox_typeahead.js`.
* The test suite, probably via adding entries to `zerver/tests/fixtures/markdown_test_cases.json`.
* The in-app markdown documentation (`templates/zerver/app/markdown_help.html`).
* The list of changes to markdown at the end of this document.

Important considerations for any changes are:

* Security: A bug in the markdown processor can lead to XSS issues.
  For example, we should not insert unsanitized HTML from a
  third-party web application into a Zulip message.
* Uniqueness: We want to avoid users having a bad experience due to
  accidentally triggering markdown syntax or typeahead that isn't
  related to what they are trying to express.
* Performance: Zulip can render a lot of messages very quickly, and
  we'd like to keep it that way.  New regular expressions similar to
  the ones already present are unlikely to be a problem, but we need
  to be thoughtful about expensive computations or third-party API
  requests.
* Database: The backend markdown processor runs inside a Python thread
  (as part of how we implement timeouts for third-party API queries),
  and for that reason we currently should avoid making database
  queries inside the markdown processor.  This is a technical
  implementation detail that could be changed with a few days of work,
  but is an important detail to know about until we do that work.
* Testing: Every new feature should have both positive and negative
  tests; they're easy to write and give us the flexibility to refactor
  frequently.

## Per-realm features

Zulip's markdown processor's rendering supports a number of features
that depend on realm-specific or user-specific data.  For example, the
realm could have
[Linkifiers](https://zulipchat.com/help/add-a-custom-linkification-filter)
or [Custom emoji](https://zulipchat.com/help/add-custom-emoji)
configured, and Zulip supports mentions for streams, users, and user
groups (which depend on data like users' names, IDs, etc.).

At a backend code level, these are controlled by the `message_realm`
object and other arguments passed into `do_convert` (`sent_by_bot`,
`translate_emoticons`, `mention_data`, etc.).  Because
`python-markdown` doesn't support directly passing arguments into the
markdown processor, Bugdown attaches these data to the Markdown
processor object via e.g. `_md_engine.zulip_db_data`, and then
individual markdown rules can access the data from there.

For non-message contexts (e.g. an organization's profile (aka the
thing on the right-hand side of the login page), stream descriptions,
or rendering custom profile fields), one needs to just pass in a
`message_realm` (see, for example, `zulip_default_context` for the
organization profile code for this).  But for messages, we need to
pass in attributes like `sent_by_bot` and `translate_emoticons` that
indicate details about how the user sending the message is configured.

## Zulip's Markdown philosophy

Note that this discussion is based on a comparison with the original
Markdown, not newer Markdown variants like CommonMark.

Markdown is great for group chat for the same reason it's been
successful in products ranging from blogs to wikis to bug trackers:
it's close enough to how people try to express themselves when writing
plain text (e.g. emails) that it helps more than getting in the way.

The main issue for using Markdown in instant messaging is that the
Markdown standard syntax used in a lot of wikis/blogs has nontrivial
error rates, where the author needs to go back and edit the post to
fix the formatting after typing it the first time.  While that's
basically fine when writing a blog, it gets annoying very fast in a
chat product; even though you can edit messages to fix formatting
mistakes, you don't want to be doing that often.  There are basically
2 types of error rates that are important for a product like Zulip:

* What fraction of the time, if you pasted a short technical email
  that you wrote to your team and passed it through your Markdown
  implementation, would you need to change the text of your email for it
  to render in a reasonable way?  This is the "accidental Markdown
  syntax" problem, common with Markdown syntax like the italics syntax
  interacting with talking about `char *`s.

* What fraction of the time do users attempting to use a particular
  Markdown syntax actually succeed at doing so correctly?  Syntax like
  required a blank line between text and the start of a bulleted list
  raise this figure substantially.

Both of these are minor issues for most products using Markdown, but
they are major problems in the instant messaging context, because one
can't edit a message that has already been sent before others read it
and users are generally writing quickly. Zulip's Markdown strategy is
based on the principles of giving users the power they need to express
complicated ideas in a chat context while minimizing those two error rates.

## Zulip's Changes to Markdown

Below, we document the changes that Zulip has against stock
Python-Markdown; some of the features we modify / disable may already
be non-standard.

### Basic syntax

* Enable `nl2br` extension: this means one newline creates a line
  break (not paragraph break).

* Allow only `*` syntax for italics, not `_`. This resolves an issue where
  people were using `_` and hitting it by mistake too often. Asterisks
  surrounded by spaces won't trigger italics, either (e.g. with stock Markdown
  `You should use char * instead of void * there` would produce undesired
  results).

* Allow only `**` syntax for bold, not `__` (easy to hit by mistake if
  discussing Python `__init__` or something).

* Add `~~` syntax for strikethrough.

* Disable special use of `\` to escape other syntax. Rendering `\\` as
  `\` was hugely controversial, but having no escape syntax is also
  controversial.  We may revisit this.  For now you can always put
  things in code blocks.

### Lists

* Allow tacking a bulleted list or block quote onto the end of a
  paragraph, i.e. without a blank line before it.

* Allow only `*` for bulleted lists, not `+` or `-` (previously
  created confusion with diff-style text sloppily not included in a
  code block).

* Disable ordered list syntax: stock Markdown automatically renumbers, which
  can be really confusing when sending a numbered list across multiple
  messages.

### Links

* Enable auto-linkification, both for `http://...` and guessing at
  things like `t.co/foo`.

* Force links to be absolute. `[foo](google.com)` will go to
  `http://google.com`, and not `http://zulip.com/google.com` which
  is the default behavior.

* Set `target="_blank"` and `title=`(the url) on every link tag so
  clicking always opens a new window.

* Disable link-by-reference syntax,
  `[foo][bar]` ... `[bar]: http://google.com`.

* Enable linking to other streams using `#**streamName**`.


### Code

* Enable fenced code block extension, with syntax highlighting.

* Disable line-numbering within fenced code blocks -- the `<table>`
  output confused our web client code.

### Other

* Disable headings, both `# foo` and `== foo ==` syntax: they don't
  make much sense for chat messages.

* Disabled images with `![]()` (images from links are shown as an inline
  preview).

* Allow embedding any avatar as a tiny (list bullet size) image.  This
  is used primarily by version control integrations.

* We added the `~~~ quote` block quote syntax.
