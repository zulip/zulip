# Add a custom playground

{!admin-only.md!}

Code playgrounds allow users to open the contents of a [code
block][code-block] in an external playground of your choice by
clicking a widget that appears when hovering over the code block.

Code playgrounds can be configured for any programming language (the
language of a code block is determined by the logic for syntax
highlighting).  You can also use a custom language name to implement
simple integrations.  For example, a playground for the language
`send_tweet` could be used with a "playground" that sends the content
of the code block as a Tweet.

[code-block]: /help/format-your-message-using-markdown#code

### Add a custom playground

{start_tabs}

{settings_tab|playground-settings}

1. Under **Add a new playground**, enter a **Name**, **Language** and
**URL prefix**.

1. Click **Add playground**.

{end_tabs}

## Walkthrough with an example

Consider the following example.

* Name: `Rust playground`
* Language: `Rust`
* URL prefix: `https://play.rust-lang.org/?edition=2018&code=`

When composing a message `rust` can be mentioned as the syntax highlighting
language in the code blocks.

~~~
``` rust
fn main() {
    // A hello world Rust program for demo purposes
    println!("Hello World!");
}
```
~~~

The user would then get a on-hover option to open the above code in the playground
they had previously configured.

## Technical details

* You can configure multiple playgrounds for a given language; if you do that,
  the user will get to choose which playground to open the code in.
* The `Language` field is the human-readable Pygments language name for that
  programming language. The syntax highlighting language in a code block
  is internally mapped to these human-readable Pygments names.
  E.g: `py3` and `py` are mapped to `Python`. We are working on implementing a
  typeahead for looking up the Pygments name. Until then, one can use
  [this Pygments method](https://pygments-doc.readthedocs.io/en/latest/lexers/lexers.html#pygments.lexers.get_lexer_by_name).
* The links for opening code playgrounds are always constructed by
  concatenating the provided URL prefix with the URL-encoded contents
  of the code block.
* Code playground sites do not always clearly document their URL
  format; often you can just get the prefix from your browser's URL bar.

If you have any trouble setting in setting up a code playground, please [contact
us](/help/contact-support) with details on what you're trying to do, and we'll be
happy to help you out.
