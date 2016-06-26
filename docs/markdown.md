# Markdown implementation

Zulip has a special flavor of Markdown, currently called 'bugdown'
after Zulip's original name of "humbug". End users are using Bugdown
within the client, not original Markdown.

Zulip has two implementations of Bugdown.  The first is based on
Python-Markdown (`zerver/lib/bugdown/`) and is used to authoritatively
render messages on the backend (and implements expensive features like
querying the Twitter API to render tweets nicely).  The other is in
JavaScript, based on marked (`static/js/echo.js`), and is used to
preview and locally echo messages the moment the sender hits enter,
without waiting for round trip from the server.  The two
implementations are tested for compatibility via
`zerver/tests/test_bugdown.py` and the fixtures under
`zerver/fixtures/bugdown-data.json`.

The JavaScript implementation knows which types of messages it can
render correctly, and thus while there is code to rerender messages
based on the authoritative backend rendering (which would clause a
change in the rendering visible only to the sender shortly after a
message is sent), this should never happen, and whenever it does it is
considered a bug.  Instead, if the frontend doesn't know how to
correctly render a message, we simply won't echo the message for the
sender until it's rendered by the backend.  So for example, a message
containing a link to Twitter will not be rendered by the JavaScript
implementation because it doesn't support doing the 3rd party API
queries required to render tweets nicely.

I should note that the below documentation is based on a comparison
with original Markdown, not newer Markdown variants like CommonMark.

## Zulip's Markdown philosophy

Markdown is great for group chat for the same reason it's been
successful in products ranging from blogs to wikis to bug trackers:
it's close enough to how people try to express themselves when writing
plain text (e.g. emails) that is helps more than getting in the way.

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
can't edit a message that has already been sent and users are
generally writing quickly.  Zulip's Markdown strategy is based on the
principles of giving users the power they need to express complicated
ideas in a chat context while minimizing those two error rates.

## Zulip's Changes to Markdown

Below, we document the changes that Zulip has against stock
Python-Markdown; some of the features we modify / disable may already
be non-standard.

### Basic syntax

* Enable `nl2br</tt> extension: this means one newline creates a line
  break (not paragraph break).

* Disable italics entirely.  This resolves an issue where people were
  using `*` and `_` and hitting it by mistake too often.  E.g. with
  stock Markdown `You should use char * instead of void * there` would
  trigger italics.

* Allow only `**` syntax for bold, not `__` (easy to hit by mistake if
  discussing Python `__init__` or something)

* Disable special use of `\` to escape other syntax. Rendering `\\` as
  `\` was hugely controversial, but having no escape syntax is also
  controversial.  We may revisit this.  For now you can always put
  things in code blocks.

### Lists

* Allow tacking a bulleted list or block quote onto the end of a
  paragraph, i.e. without a blank line before it

* Allow only `*` for bulleted lists, not `+` or `-` (previously
  created confusion with diff-style text sloppily not included in a
  code block)

* Disable ordered list syntax: it automatically renumbers, which can
  be really confusing when sending a numbered list across multiple
  messages.

### Links

* Enable auto-linkification, both for `http://...` and guessing at
  things like `t.co/foo`.

* Force links to be absolute. `[foo](google.com)` will go to
  `http://google.com`, and not `http://zulip.com/google.com` which
  is the default behavior.

* Set `target="_blank"` and `title=`(the url) on every link tag so
  clicking always opens a new window

* Disable link-by-reference syntax, `[foo][bar]` ... `[bar]: http://google.com`

### Code

* Enable fenced code block extension, with syntax highlighting

* Disable line-numbering within fenced code blocks -- the `<table>`
  output confused our web client code.

### Other

* Disable headings, both `# foo` and `== foo ==` syntax: they don't
  make much sense for chat messages.

* Disabled images.

* Allow embedding any avatar as a tiny (list bullet size) image.  This
  is used primarily by version control integrations.

* We added the `~~~ quote` block quote syntax.
