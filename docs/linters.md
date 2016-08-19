# Linters

## Overview

Zulip does extensive linting of much of its source code, including
Python/JavaScript files, HTML templates (Django/handlebars), CSS files,
JSON fixtures, Markdown documents, puppet manifests, and shell scripts.

For some files we simply check for small things like trailing whitespace,
but for other files, we are quite thorough about checking semantic
correctness.

Obviously, a large reason for linting code is to enforce the [Zulip
coding standards](code-style.html).  But we also use the linters to
prevent common coding errors.

We borrow some open source tools for much of our linting, and the links
below will direct you to the official documentation for these projects.

- [jslint](https://github.com/douglascrockford/JSLint)
- [mypy](http://mypy-lang.org/)
- [puppet](https://puppet.com/) (puppet provides its own mechanism for validating manifests)
- [pyflakes](https://pypi.python.org/pypi/pyflakes)

Zulip also uses some home-grown code to perform tasks like validating
indentation in template files, enforcing coding standards that are unique
to Zulip, allowing certain errors from third party linters to pass through,
and exempting legacy files from lint checks.

## Running the linters

If you run `./tools/test-all`, it will automatically run the linters (with
one small exception: it does not run mypy against scripts).

You can also run them individually:

    ./tools/lint-all
    ./tools/run-mypy
    ./tools/run-mypy --scripts-only

Finally, you can rely on our Travis CI setup to run linters for you, but
it is good practice to run lint checks locally.

Our linting tools generally support the ability to lint files
individually--with some caveats--and those options will be described
later in this document.

We may eventually bundle `run-mypy` into `lint-all`, but mypy is pretty
resource intensive compared to the rest of the linters, because it does
static code analysis.  So we keep mypy separate to allow folks to quickly run
the other lint checks.

## General considerations

Once you have read the [Zulip coding guidelines](code-style.html), you can
be pretty confident that 99% of the code that you write will pass through
the linters fine, as long as you are thorough about keeping your code clean.
And, of course, for minor oversights, `lint-all` is your friend, not your foe.

Occasionally, our linters will complain about things that are more of
an artifact of the linter limitations than any actual problem with your
code.  There is usually a mechanism where you can bypass the linter in
extreme cases, but often it can be a simple matter of writing your code
in a slightly different style to appease the linter.  If you have
problems getting something to lint, you can submit an unfinished PR
and ask the reviewer to help you work through the lint problem, or you
can find other people in the [Zulip Community](readme-symlink.html#community)
to help you.

Also, bear in mind that 100% of the lint code is open source, so if you
find limitations in either the Zulip home-grown stuff or our third party
tools, feedback will be highly appreciated.

Finally, one way to clean up your code is to thoroughly exercise it
with tests.  The [Zulip test documentation](testing.html)
describes our test system in detail.

## Lint checks

Most of our lint checks get performed by `./tools/lint-all`.  These include the
following checks:

- Check Python code with pyflakes.
- Check JavaScript code with jslint.
- Check Python code for custom Zulip rules.
- Check non-Python code for custom Zulip rules.
- Check puppet manifests with the puppet validator.
- Check HTML templates for matching tags and indentations.
- Check CSS for parsability.
- Check JavaScript code for addClass calls.

The remaining lint checks occur in `./tools/run-mypy`.  It is probably somewhat
of an understatement to call "mypy" a "linter," as it performs static
code analysis of Python type annotations throughout our Python codebase.

Our [documentation on using mypy](mypy.html) covers mypy in more detail.

The rest of this document pertains to the checks that occur in `./tools/lint-all`.

## lint-all

Zulip has a script called `lint-all` that lives in our "tools" directory.
It is the workhorse of our linting system, although in some cases it
dispatches the heavy lifting to other components such as pyflakes,
jslint, and other home grown tools.

You can find the source code [here](https://github.com/zulip/zulip/blob/master/tools/lint-all).

In order for our entire lint suite to run in a timely fashion, the `lint-all`
script performs several lint checks in parallel by forking out subprocesses.  This mechanism
is still evolving, but you can look at the method `run_parallel` to get the
gist of how it works.

### Special options

You can use the `-h` option for `lint-all` to see its usage.  One particular
flag to take note of is the `--modified` flag, which enables you to only run
lint checks against files that are modified in your git repo.  Most of the
"sub-linters" respect this flag, but some will continue to process all the files.
Generally, a good workflow is to run with `--modified` when you are iterating on
the code, and then run without that option right before commiting new code.

If you need to troubleshoot the linters, there is a `--verbose` option that
can give you clues about which linters may be running slow, for example.

### Lint checks

The next part of this document describes the lint checks that we apply to
various file types.

#### Generic source code checks

We check almost our entire codebase for trailing whitespace.  Also, we
disallow tab (\t) characters in all but two files.

We also have custom regex-based checks that apply to specific file types.
For relatively minor files like Markdown files and JSON fixtures, this
is the extent of our checking.

Finally, we're checking line length in Python code (and hope to extend
this to other parts of the codebase soon).  You can use
`#ignorelinelength` for special cases where a very long line makes
sense (e.g. a link in a comment to an extremely long URL).

#### Python code

The bulk of our Python linting gets outsourced to the "pyflakes" tool.  We
call "pyflakes" in a fairly vanilla fashion, and then we post-process its
output to exclude certain types of errors that Zulip is comfortable
ignoring.  (One notable class of error that Zulip currently tolerates is
unused imports--because of the way mypy type annotations work in Python 2,
it would be inconvenient to enforce this too strictly.)

Zulip also has custom regex-based rules that it applies to Python code.
Look for `python_rules` in the source code for `lint-all`.  Note that we
provide a mechanism to excude certain lines of codes from these checks.
Often, it is simply the case that our regex approach is too crude to
correctly exonerate certain valid constructs.  In other cases, the code
that we exempt may be deemed not worthwhile to fix.

#### JavaScript code

We check our JavaScript code in a few different ways:
- We run jslint.
- We perform custom Zulip regex checks on the code.
- We verify that all addClass calls, with a few exceptions, explicitly
  contain a CSS class.

The last check happens via a call to `./tools/find-add-class`.  This
particular check is a work in progress, as we are trying to evolve a
more rigorous system for weeding out legacy CSS styles, and the ability
to quickly introspect our JS code for `addClass` calls is part of our
vision.

#### Puppet manifests

We use Puppet as our tool to manage configuration files, using
puppet "manifests."  To lint puppet manifests, we use the "parser validate"
option of puppet.

#### HTML Templates

Zulip uses two HTML templating systems:

- [Django templates](https://docs.djangoproject.com/en/1.10/topics/templates/)
- [handlebars](http://handlebarsjs.com/)

Zulip has a home grown tool that validates both types of templates for
correct indentation and matching tags.  You can find the code here:

- driver: [check-templates](https://github.com/zulip/zulip/blob/master/tools/check-templates)
- engine: [lib/template_parser.py](https://github.com/zulip/zulip/blob/master/tools/lib/template_parser.py)

We exempt some legacy files from indentation checks, but we are hoping to
clean those files up eventually.

#### CSS

Zulip does not currently lint its CSS for any kind of semantic correctness,
but that is definitely a goal moving forward.

We do ensure that our home-grown CSS parser can at least parse the CSS code.
This is a slightly more strict check than checking that the CSS is
compliant to the official spec, as our parser will choke on unusual
constructs that we probably want to avoid in our code, anyway.  (When
the parser chokes, the lint check will fail.)

You can find the code here:

- driver: [check-css](https://github.com/zulip/zulip/blob/master/tools/check-css)
- engine: [lib/css_parser.py](https://github.com/zulip/zulip/blob/master/tools/lib/css_parser.py)

#### Markdown, shell scripts, JSON fixtures

We mostly validate miscellaneous source files like `.sh`, `.json`, and `.md` files for
whitespace issues.

## Philosophy

If you want to help improve Zulip's system for linting, here are some
considerations.

#### Speed

We want our linters to be fast enough that most developers
will feel comfortable running them in a pre-commit hook, so we run
our linters in parallel and support incremental checks.

#### Accuracy

We try to catch as many common mistakes as possible, either via a
linter or an automated test.

#### Completeness

Our goal is to have most common style issues by caught by the linters, so new
contributors to the codebase can efficiently fix produce code with correct
style without needing to go back-and-forth with a reviewer.

