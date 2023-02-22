# Linters

A linter is a program that runs on the source code of software and
reports potentially problematic code to the user. Linters help enforce
coding guidelines, from minor details like whitespace formatting or
capitalization patterns for strings to preventing problematic coding
patterns that can lead to security bugs.

## Overview

Zulip does extensive linting of much of its source code, including
Python/JavaScript/TypeScript files, HTML templates (Django/Handlebars), CSS files,
JSON fixtures, Markdown documents, puppet manifests, and shell scripts.

For some files we simply check for small things like trailing whitespace,
but for other files, we are quite thorough about checking semantic
correctness.

Obviously, a large reason for linting code is to enforce the [Zulip
coding standards](../contributing/code-style.md). But we also use the linters to
prevent common coding errors.

We borrow some open source tools for much of our linting, and the links
below will direct you to the official documentation for these projects.

- [Black](https://github.com/psf/black)
- [ESLint](https://eslint.org)
- [isort](https://pycqa.github.io/isort/)
- [mypy](http://mypy-lang.org/)
- [Prettier](https://prettier.io/)
- [Puppet](https://puppet.com/) (puppet provides its own mechanism for
  validating manifests)
- [ruff](https://github.com/charliermarsh/ruff)
- [stylelint](https://github.com/stylelint/stylelint)

Zulip also uses some home-grown code to perform tasks like validating
indentation in template files, enforcing coding standards that are unique
to Zulip, allowing certain errors from third party linters to pass through,
and exempting legacy files from lint checks.

## Running the linters

If you run `./tools/test-all`, it will automatically run the linters.
You can also run them individually or pass specific files:

```bash
./tools/lint
./tools/lint web/src/compose.js
./tools/lint web/src/
```

`./tools/lint` has many useful options; you can read about them in its
internal documentation using `./tools/lint --help`. Of particular
note are:

- `--fix`: Several of our linters support automatically fixing basic
  issues; this option will ask `tools/lint` to run those.
- `--verbose`: Provides detailed information on how to fix many common
  linter errors not covered by `--fix`.
- `--skip` and `--only`: Only run certain linters.
- `-m`: Only check modified files.

Finally, you can rely on our continuous integration setup to run linters for you,
but it is good practice to run lint checks locally.

:::{important}
We provide a
[Git pre-commit hook](../git/zulip-tools.md#set-up-git-repo-script)
that can automatically run `tools/lint` on just the files that
changed (in a few 100ms) whenever you make a commit. This can save
you a lot of time, by automatically detecting linter errors as you
make them.
:::

**Note:** The linters only check files that Git tracks. Remember to `git add`
new files before running lint checks.

Our linting tools generally support the ability to lint files
individually--with some caveats--and those options will be described
later in this document.

## General considerations

Once you have read the [Zulip coding guidelines](../contributing/code-style.md), you can
be pretty confident that 99% of the code that you write will pass through
the linters fine, as long as you are thorough about keeping your code clean.
And, of course, for minor oversights, `lint` is your friend, not your foe.

Occasionally, our linters will complain about things that are more of
an artifact of the linter limitations than any actual problem with your
code. There is usually a mechanism where you can bypass the linter in
extreme cases, but often it can be a simple matter of writing your code
in a slightly different style to appease the linter. If you have
problems getting something to lint, you can submit an unfinished PR
and ask the reviewer to help you work through the lint problem, or you
can find other people in the [Zulip Community](https://zulip.com/development-community/)
to help you.

Also, bear in mind that 100% of the lint code is open source, so if you
find limitations in either the Zulip home-grown stuff or our third party
tools, feedback will be highly appreciated.

Finally, one way to clean up your code is to thoroughly exercise it
with tests. The [Zulip test documentation](testing.md)
describes our test system in detail.

## Lint checks

Most of our lint checks get performed by `./tools/lint`. These include the
following checks:

- Check Python code with ruff.
- Check Python formatting with Black and isort.
- Check JavaScript and TypeScript code with ESLint.
- Check CSS, JavaScript, TypeScript, and YAML formatting with Prettier.
- Check Python code for custom Zulip rules.
- Check non-Python code for custom Zulip rules.
- Check Puppet manifests with the Puppet validator.
- Check HTML templates for matching tags and indentations.
- Check CSS for parsability and formatting.
- Check JavaScript code for addClass calls.
- Running `mypy` to check static types in Python code. Our
  [documentation on using mypy](mypy.md) covers mypy in
  more detail.
- Running `tsc` to compile TypeScript code. Our [documentation on
  TypeScript](typescript.md) covers TypeScript in more detail.

The rest of this document pertains to the checks that occur in `./tools/lint`.

## lint

Zulip has a script called `lint` that lives in our "tools" directory.
It is the workhorse of our linting system, although in some cases it
dispatches the heavy lifting to other components such as ruff,
eslint, and other home grown tools.

You can find the source code [here](https://github.com/zulip/zulip/blob/main/tools/lint).

In order for our entire lint suite to run in a timely fashion, the `lint`
script performs several lint checks in parallel by forking out subprocesses.

Note that our project does custom regex-based checks on the code. The code for these
types of checks mostly lives [here](https://github.com/zulip/zulip/tree/main/tools/linter_lib).

### Special options

You can use the `-h` option for `lint` to see its usage. One particular
flag to take note of is the `--modified` flag, which enables you to only run
lint checks against files that are modified in your Git repo. Most of the
"sub-linters" respect this flag, but some will continue to process all the files.
Generally, a good workflow is to run with `--modified` when you are iterating on
the code, and then run without that option right before committing new code.

If you need to troubleshoot the linters, there is a `--verbose-timing`
option that can give you clues about which linters may be running
slow, for example.

### Lint checks

The next part of this document describes the lint checks that we apply to
various file types.

#### Generic source code checks

We check almost our entire codebase for trailing whitespace. Also, we
disallow tab (\t) characters in all but two files.

We also have custom regex-based checks that apply to specific file types.
For relatively minor files like Markdown files and JSON fixtures, this
is the extent of our checking.

Finally, we're checking line length in Python code (and hope to extend
this to other parts of the codebase soon). You can use
`#ignorelinelength` for special cases where a very long line makes
sense (e.g. a link in a comment to an extremely long URL).

#### Python code

Our Python code is formatted using Black (using the options in the
`[tool.black]` section of `pyproject.toml`) and isort (using the
options in `.isort.cfg`). The `lint` script enforces this by running
Black and isort in check mode, or in write mode with `--fix`.

The bulk of our Python linting gets outsourced to the "ruff" tool,
which is configured in the `tool.ruff` section of `pyproject.toml`.

Zulip also has custom regex-based rules that it applies to Python code.
Look for `python_rules` in the source code for `lint`. Note that we
provide a mechanism to exclude certain lines of codes from these checks.
Often, it is simply the case that our regex approach is too crude to
correctly exonerate certain valid constructs. In other cases, the code
that we exempt may be deemed not worthwhile to fix.

#### JavaScript code

We check our JavaScript code in a few different ways:

- We run eslint.
- We check code formatting with Prettier.
- We perform custom Zulip regex checks on the code.

#### Puppet manifests

We use Puppet as our tool to manage configuration files, using
Puppet "manifests." To lint Puppet manifests, we use the "parser validate"
option of Puppet.

#### HTML templates

Zulip uses two HTML templating systems:

- [Django templates](https://docs.djangoproject.com/en/3.2/topics/templates/)
- [handlebars](https://handlebarsjs.com/)

Zulip has an internal tool that validates both types of templates for
correct indentation and matching tags. You can find the code here:

- driver: [check-templates](https://github.com/zulip/zulip/blob/main/tools/check-templates)
- engine: [lib/template_parser.py](https://github.com/zulip/zulip/blob/main/tools/lib/template_parser.py)

We exempt some legacy files from indentation checks, but we are hoping to
clean those files up eventually.

#### CSS

Zulip uses [stylelint](https://github.com/stylelint/stylelint) to lint
its CSS; see our
[configuration](https://github.com/zulip/zulip/blob/main/stylelint.config.js)
for the rules we currently enforce.

#### Shell scripts

Zulip uses [shellcheck](https://github.com/koalaman/shellcheck) to
lint our shell scripts. We recommend the
[shellcheck gallery of bad code][shellcheck-bad-code] as a resource on
how to not write bad shell.

[shellcheck-bad-code]: https://github.com/koalaman/shellcheck/blob/master/README.md#user-content-gallery-of-bad-code

#### Markdown, shell scripts, JSON fixtures

We mostly validate miscellaneous source files like `.json`, and `.md`
files for whitespace issues.

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
