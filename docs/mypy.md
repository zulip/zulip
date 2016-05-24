# Testing with the mypy Python static type checker

[mypy](http://mypy-lang.org/) is a compile-time static type checker
for Python, allowing optional, gradual typing of Python code.  Zulip
is using mypy's Python 2 compatible syntax for type annotations, which
means that type annotations are written inside comments that start
with `# type: `.  Here's a brief example of the mypy syntax we're
using in Zulip:

```
user_dict = {} # type: Dict[str, UserProfile]

def get_user_profile_by_email(email):
    # type: (str) -> UserProfile
    ... # Actual code of the function here
```

You can learn more about it at:

* [Python 2 type annotation syntax in PEP 484](https://www.python.org/dev/peps/pep-0484/#suggested-syntax-for-python-2-7-and-straddling-code)
* [Using mypy with Python 2 code](http://mypy.readthedocs.io/en/latest/python2.html)

The mypy type checker is run automatically as part of Zulip's Travis
CI testing process.

## Installing mypy

If you installed Zulip's development environment correctly, mypy
should already be installed inside the Python 3 virtualenv at
`zulip-py3-venv` (mypy only supports Python 3).  If it isn't installed
(e.g. because you haven't reprovisioned recently), you can run
`tools/install-mypy` to install it.

## Running mypy on Zulip's code locally

To run mypy on Zulip's python code, run the command:

    tools/run-mypy

It will output errors in the same style of a compiler.  For example,
if your code has a type error like this:

```
foo = 1
foo = '1'
```

you'll get an error like this:

```
test.py: note: In function "test":
test.py:200: error: Incompatible types in assignment (expression has type "str", variable has type "int")
```

If you need help interpreting or debugging mypy errors, please feel
free to mention @sharmaeklavya2 or @timabbott on your pull request (or
email zulip-devel@googlegroups.com) to get help; we'd love to both
build a great troubleshooting guide in this doc and also help
contribute improvements to error messages upstream.

Since mypy is a new tool under rapid development and occasionally
makes breaking changes, Zulip is using a pinned version of mypy from
its [git repository](https://github.com/python/mypy) rather than
tracking the (older) latest mypy release on pypi.

## Excluded files

Since several python files in Zulip's code don't pass mypy's checks
(even for unannotated code) right now, a list of files to be excluded
from the check for CI is present in tools/run-mypy.

To run mypy on all python files, ignoring the exclude list, you can
pass the `--all` option to tools/run-mypy.

    tools/run-mypy --all

If you type annotate some of those files, please remove them from the
exclude list.
