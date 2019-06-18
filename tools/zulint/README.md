# zulint

zulint is a lightweight linting framework designed for complex
applications using a mix of third-party linters and custom rules.

## Why zulint

Modern full-stack web applications generally involve code written in
several programming languages, each of which have their own standard
linter tools.  For example, [Zulip](https://zulipchat.com) uses Python
(mypy/pyflake/pycodestyle), JavaScript (eslint), CSS (stylelint),
puppet (puppet-lint), shell (shellcheck), and several more.  For many
codebases, this results in linting being an unpleasantly slow
experience, resulting in even more unpleasant secondary problems like
developers merging code that doesn't pass lint, not enforcing linter
rules, and debates about whether a useful linter is "worth the time".

Zulint is the linter framework we built for Zulip to create a
reliable, lightning-fast linter experience to solve these problems.
It has the following features:

- Integrates with `git` to only checks files in source control (not
  automatically generated, untracked, or .gitignore files).
- Runs the linters in parallel, so you only have to wait for the
  slowest linter.  For Zulip, this is a ~4x performance improvement
  over running our third-party linters in series.
- Produduces easy-to-read, clear terminal output, with each
  independent linter given its own color.
- Can check just modified files, or even as a `pre-commit` hook, only
  checking files that have changed (and only starting linters which
  check files that have changed).
- Handles all the annoying details of flushing stdout and managing
  color codes.
- Highly configurable.
  - Integrate a third-party linter with just a couple lines of code.
  - Every feature supports convenient include/exclude rules.
  - Add custom lint rules with a powerful regular expression
    framework.  E.g. in Zulip, we want all access to `Message` objects
    in views code to be done via our `access_message_by_id` functions
    (which do security checks to ensure the user the request is being
    done on behalf of has access to the message), and that is enforced
    in part by custom regular expression lint rules.  This system is
    optimized Python: Zulip has a few hundred custom linter rules of
    this type.
  - Easily add custom options to check subsets of your codebase,
    subsets of rules, etc.
- Has a nice automated testing framework for custom lint rules, so you
  can make sure your rules actually work.

This codebase has been in production use in Zulip for several years,
but only in 2019 was generalized for use by other projects.  Its API
to be beta and may change (with notice in the release notes) if we
discover a better API, and patches to further extend it for more use
cases are encouraged.

## Using zulint

Once a project is setup with zulint, you'll have a top-level linter
script with at least the following options:

```
(zulip-py3-venv) tabbott@coset:~/zulip$ ./tools/lint --help
usage: lint [-h] [--force] [--full] [--frontend | --backend] [--modified]
            [--verbose-timing] [--skip SKIP] [--only ONLY] [--list]
            [targets [targets ...]]

positional arguments:
  targets               Specify directories to check

optional arguments:
  -h, --help            show this help message and exit
  --force               Run tests despite possible problems.
  --modified, -m        Only check modified files
  --verbose-timing, -vt
                        Print verbose timing output
  --skip SKIP           Specify linters to skip, eg: --skip=mypy,gitlint
  --only ONLY           Specify linters to run, eg: --only=mypy,gitlint
  --list, -l            List all the registered linters
```

### pre-commit hook mode

See https://github.com/zulip/zulip/blob/master/tools/pre-commit for an
example pre-commit hook (Zulip's has some extra complexity because we
use Vagrant from our development environment, and want to be able to
run the hook from outside Vagrant).

## Adding zulint to a codebase

TODO.  Will roughly include `pip install zulint`, copying an example
`lint` script, and adding your rules.


## Adding third-party linters

TODO: Document the linter_config API.

## Writing custom rules

TODO: Document all the features of the `RuleList` and `custom_check` system.

