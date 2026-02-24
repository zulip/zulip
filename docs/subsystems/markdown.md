# Markdown implementation

Zulip uses a special flavor of Markdown/CommonMark for its message
formatting. Our Markdown flavor is unique primarily to add important
extensions, such as quote blocks and math blocks, and also to do
previews and correct issues specific to the chat context. Beyond
that, it has a number of minor historical variations resulting from
its history predating CommonMark (and thus Zulip choosing different
solutions to some problems) and based in part on Python-Markdown,
which is proudly a classic Markdown implementation. We reduce these
variations with every major Zulip release.

Zulip has two implementations of Markdown. The backend implementation
at `zerver/lib/markdown/` is based on
[Python-Markdown](https://pypi.python.org/pypi/Markdown) and is used to
authoritatively render messages to HTML (and implements
slow/expensive/complex features like querying the Twitter API to
render tweets nicely). The frontend implementation is in JavaScript
(`web/src/echo.ts`), and is used to preview and locally echo
messages the moment the sender hits Enter, without waiting for round
trip from the server. Those frontend renderings are only shown to the
sender of a message, and they are (ideally) identical to the backend
rendering.

The frontend Markdown processor is based on the
[micromark/mdast](https://github.com/micromark/micromark) ecosystem
(`web/src/markdown_unified.ts` and related modules); see
[unified processor](#unified-processor) for its architecture. The
legacy frontend processor, based on a heavily forked
[marked.js](https://github.com/chjj/marked)
(`web/third/marked/lib/marked.cjs`), is being replaced; it may still
be present in the codebase during the transition.

The JavaScript Markdown implementation has a function,
`markdown.contains_backend_only_syntax`, that is used to check whether a message
contains any syntax that needs to be rendered to HTML on the backend.
If `markdown.contains_backend_only_syntax` returns true, the frontend simply won't
echo the message for the sender until it receives the rendered HTML
from the backend. If there is a bug where `markdown.contains_backend_only_syntax`
returns false incorrectly, the frontend will discover this when the
backend returns the newly sent message, and will update the HTML based
on the authoritative backend rendering (which would cause a change in
the rendering that is visible only to the sender shortly after a
message is sent). As a result, we try to make sure that
`markdown.contains_backend_only_syntax` is always correct.

## Testing

The Python-Markdown implementation is tested by
`zerver/tests/test_markdown.py`, and the frontend implementations and
`markdown.contains_backend_only_syntax` are tested by
`web/tests/markdown.test.cjs`.

A shared set of fixed test data ("test fixtures") is present in
`zerver/tests/fixtures/markdown_test_cases.json`, and is automatically used
by both test suites; as a result, it is the preferred place to add new
tests for Zulip's Markdown system. Some important notes on reading
this file:

- `expected_output` is the expected output for the backend Markdown
  processor.
- When the frontend processor doesn't support a feature and it should
  just be rendered on the backend, we set `backend_only_rendering` to
  `true` in the fixtures; this will automatically verify that
  `markdown.contains_backend_only_syntax` rejects the syntax, ensuring
  it will be rendered only by the backend processor.
- When the frontend processor disagrees with the backend, we set
  `marked_expected_output` or `unified_expected_output` in the
  fixtures; this records the frontend processor's actual output for
  that case. To regenerate `unified_expected_output` after processor
  changes, run
  `./tools/test-js-with-node generate_unified_expected_output`.
- For mobile push notifications, we need a text version of the
  rendered content, since the APNS and GCM push notification systems
  don't support richer markup. Mostly, this involves stripping HTML,
  but there's some syntax we take special care with. Tests for what
  this plain-text version of content should be stored in the
  `text_content` field.

If you're going to manually test some changes in the frontend Markdown
implementation, the easiest way to do this is as follows:

1. Log in to your development server.
2. Stop your Zulip server with Ctrl-C, leaving the browser open.
3. Compose and send the messages you'd like to test. They will be
   locally echoed using the frontend rendering.

This procedure prevents any server-side rendering. If you don't do
this, backend will likely render the Markdown you're testing and swap
it in before you can see the frontend's rendering.

If you are working on a feature that breaks multiple testcases, and want
to debug the testcases one by one, you can add `"ignore": true` to any
testcases in `markdown_test_cases.json` that you want to ignore. This
is a workaround due to lack of comments support in JSON. Revert your
"ignore" changes before committing. After this, you can run the frontend
tests with `tools/test-js-with-node markdown` and backend tests with
`tools/test-backend zerver.tests.test_markdown.MarkdownFixtureTest.test_markdown_fixtures`.

## Changing Zulip's Markdown processor

First, you will likely find these third-party resources helpful:

- **[Python-Markdown](https://pypi.python.org/pypi/Markdown)** is the Markdown
  library used by Zulip as a base to build our custom Markdown syntax upon.
- **[Python's XML ElementTree](https://docs.python.org/3/library/xml.etree.elementtree.html)**
  is the part of the Python standard library used by Python Markdown
  and any custom extensions to generate and modify the output HTML.

When changing Zulip's Markdown syntax, you need to update several
places:

- The backend Markdown processor (`zerver/lib/markdown/__init__.py`).
- The frontend Markdown processor (`web/src/markdown_unified.ts` and
  related modules; see [unified processor](#unified-processor)), or
  `markdown.contains_backend_only_syntax` if your changes won't be
  supported in the frontend processor.
- If desired, the typeahead logic in `web/src/composebox_typeahead.ts`.
- The test suite, probably via adding entries to
  `zerver/tests/fixtures/markdown_test_cases.json`. After adding
  tests, regenerate unified expected output with
  `./tools/test-js-with-node generate_unified_expected_output`.
- The in-app Markdown documentation (`markdown_help_rows` in `web/src/info_overlay.ts`).
- The list of changes to Markdown at the end of this document.

Important considerations for any changes are:

- Security: A bug in the Markdown processor can lead to XSS issues.
  For example, we should not insert unsanitized HTML from a
  third-party web application into a Zulip message.
- Uniqueness: We want to avoid users having a bad experience due to
  accidentally triggering Markdown syntax or typeahead that isn't
  related to what they are trying to express.
- Performance: Zulip can render a lot of messages very quickly, and
  we'd like to keep it that way. New regular expressions similar to
  the ones already present are unlikely to be a problem, but we need
  to be thoughtful about expensive computations or third-party API
  requests.
- Database: The backend Markdown processor runs inside a Python thread
  (as part of how we implement timeouts for third-party API queries),
  and for that reason we currently should avoid making database
  queries inside the Markdown processor. This is a technical
  implementation detail that could be changed with a few days of work,
  but is an important detail to know about until we do that work.
- Testing: Every new feature should have both positive and negative
  tests; they're easy to write and give us the flexibility to refactor
  frequently.

## Per-realm features

Zulip's Markdown processor's rendering supports a number of features
that depend on realm-specific or user-specific data. For example, the
realm could have
[linkifiers](https://zulip.com/help/add-a-custom-linkifier)
or [custom emoji](https://zulip.com/help/custom-emoji)
configured, and Zulip supports mentions for channels, users, and user
groups (which depend on data like users' names, IDs, etc.).

At a backend code level, these are controlled by the `message_realm`
object and other arguments passed into `do_convert` (`sent_by_bot`,
`translate_emoticons`, `mention_data`, etc.). Because
Python-Markdown doesn't support directly passing arguments into the
Markdown processor, our logic attaches the data to the Markdown
processor object via, for example, `_md_engine.zulip_db_data`, and
then individual Markdown rules can access the data from there.

For non-message contexts (e.g., an organization's profile (aka the
thing on the right-hand side of the login page), channel descriptions,
or rendering custom profile fields), one needs to just pass in a
`message_realm` (see, for example, `zulip_default_context` for the
organization profile code for this). But for messages, we need to
pass in attributes like `sent_by_bot` and `translate_emoticons` that
indicate details about how the user sending the message is configured.

## Unified processor

The frontend Markdown processor (`web/src/markdown_unified.ts`) uses
the [micromark](https://github.com/micromark/micromark) /
[mdast](https://github.com/syntax-tree/mdast) ecosystem for
CommonMark + GFM parsing. Zulip-specific extensions (mentions,
channel links, emoji, math, timestamps, spoilers, linkifiers) are
implemented as AST transforms that run between parsing and HTML
serialization, rather than by modifying the parser itself.

### Key files

- `web/src/markdown_unified.ts` -- Pipeline orchestration and the
  `parse_to_mdast()` function (used recursively for spoiler bodies).
- `web/src/markdown_zulip_transforms.ts` -- AST transforms that
  detect Zulip-specific patterns in the mdast tree and replace them
  with custom node types (e.g., `zulipUserMention`,
  `zulipStreamLink`, `zulipEmoji`).
- `web/src/markdown_hast_handlers.ts` -- Converts custom mdast node
  types to HTML. Reuses HTML-generating functions from
  `web/src/markdown.ts` (e.g., `handleTimestamp`, `handleTex`,
  `wrap_code`).
- `web/src/markdown_fenced_blocks.ts` -- Preprocessor that converts
  `~~~quote` blocks to `>` blockquote syntax before micromark
  parsing; other fenced blocks pass through for micromark.

### Security model

The unified processor's XSS defense has three layers:

1. **HTML parsing is disabled at the micromark level.** User-authored
   HTML tags (`<script>`, `<b>`, etc.) become text nodes and are
   auto-escaped by `toHtml`.
2. **All user-controlled values in hast handlers are escaped with
   `_.escape()`.** The custom hast handlers emit `raw()` nodes
   containing pre-built HTML strings; every piece of user data in
   those strings is escaped.
3. **`allowDangerousHtml` is safe** because the only raw HTML comes
   from our handlers (layer 2), never from user input (layer 1).

When adding or modifying hast handlers, always use `_.escape()` on
any user-controlled value inserted into raw HTML.

### Design notes

**Mentions and channel links** like `@**name**` and `#**channel**`
are not custom micromark syntax. Micromark parses `@**name**` as a
text node `@` followed by a `<strong>` sibling containing `name`.
The `transform_sibling_patterns` helper in
`markdown_zulip_transforms.ts` detects this pattern and merges the
two nodes into a custom Zulip node. This avoids writing custom
micromark tokenizer extensions but depends on micromark's exact AST
output.

**Inline math** (`$$...$$`) is preprocessed before micromark parsing:
math spans are replaced with alphanumeric placeholders so that
content inside math isn't parsed as Markdown. After parsing,
placeholders in text nodes are restored to `zulipInlineMath` nodes.
Placeholders inside `inlineCode` nodes are restored to the original
`$$...$$` text (so code spans show literal content). Any future
preprocessing steps should check for similar placeholder leaks into
code spans or other literal-content contexts.

**Transform ordering matters.** The order of AST transforms in the
pipeline is significant; for example, timestamps and math must run
before emoji (because the unicode emoji regex matches digits and
would split text nodes), and links must run before mentions. See the
comments in `markdown_unified.ts` for details.

## Zulip's Markdown philosophy

Note that this discussion is based on a comparison with the original
Markdown, not newer Markdown variants like CommonMark.

Markdown is great for group chat for the same reason it's been
successful in products ranging from blogs to wikis to bug trackers:
it's close enough to how people try to express themselves when writing
plain text (e.g., emails) that it helps more than getting in the way.

The main issue for using Markdown in instant messaging is that the
Markdown standard syntax used in a lot of wikis/blogs has nontrivial
error rates, where the author needs to go back and edit the post to
fix the formatting after typing it the first time. While that's
basically fine when writing a blog, it gets annoying very fast in a
chat product; even though you can edit messages to fix formatting
mistakes, you don't want to be doing that often. There are basically
2 types of error rates that are important for a product like Zulip:

- What fraction of the time, if you pasted a short technical email
  that you wrote to your team and passed it through your Markdown
  implementation, would you need to change the text of your email for it
  to render in a reasonable way? This is the "accidental Markdown
  syntax" problem, common with Markdown syntax like the italics syntax
  interacting with talking about `char *`s.

- What fraction of the time do users attempting to use a particular
  Markdown syntax actually succeed at doing so correctly? Syntax like
  required a blank line between text and the start of a bulleted list
  raise this figure substantially.

Both of these are minor issues for most products using Markdown, but
they are major problems in the instant messaging context, because one
can't edit a message that has already been sent before others read it
and users are generally writing quickly. Zulip's Markdown strategy is
based on the principles of giving users the power they need to express
complicated ideas in a chat context while minimizing those two error rates.

## Zulip's changes to Markdown

Below, we document the changes that Zulip has against stock
Python-Markdown; some of the features we modify / disable may already
be non-standard.

**Note** This section has not been updated in a few years and is not
accurate.

### Basic syntax

- Enable `nl2br` extension: this means one newline creates a line
  break (not paragraph break).

- Allow only `*` syntax for italics, not `_`. This resolves an issue where
  people were using `_` and hitting it by mistake too often. Asterisks
  surrounded by spaces won't trigger italics, either (e.g., with stock Markdown
  `You should use char * instead of void * there` would produce undesired
  results).

- Allow only `**` syntax for bold, not `__` (easy to hit by mistake if
  discussing Python `__init__` or something).

- Add `~~` syntax for strikethrough.

- Disable special use of `\` to escape other syntax. Rendering `\\` as
  `\` was hugely controversial, but having no escape syntax is also
  controversial. We may revisit this. For now you can always put
  things in code blocks.

### Lists

- Allow tacking a bulleted list or block quote onto the end of a
  paragraph, i.e. without a blank line before it.

- Allow only `*` for bulleted lists, not `+` or `-` (previously
  created confusion with diff-style text sloppily not included in a
  code block).

- Disable ordered list syntax: stock Markdown automatically renumbers, which
  can be really confusing when sending a numbered list across multiple
  messages.

### Links

- Enable auto-linkification, both for `http://...` and guessing at
  things like `t.co/foo`.

- Force links to be absolute. `[foo](google.com)` will go to
  `http://google.com`, and not `https://zulip.com/google.com` which
  is the default behavior.

- Set `title=`(the URL) on every link tag.

- Disable link-by-reference syntax,
  `[foo][bar]` ... `[bar]: https://google.com`.

- Enable linking to other channels using `#**channelName**`.

### Code

- Enable fenced code block extension, with syntax highlighting.

- Disable line-numbering within fenced code blocks -- the `<table>`
  output confused our web client code.

### Headings

- Enable headings with syntax `# foo` (syntax `== foo ==` is unsupported).

### Other

- Disabled images with `![]()` (images from links are shown as an inline
  preview).

- We added the `~~~ quote` block quote syntax.
