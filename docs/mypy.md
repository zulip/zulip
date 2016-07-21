# Python static type checker (mypy)

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

* [The mypy cheat
  sheet](https://github.com/python/mypy/blob/master/docs/source/cheat_sheet.rst)
  is the best resource for quickly understanding how to write the PEP
  484 type annotations used by mypy correctly.

* The [Python 2 type annotation syntax spec in PEP
  484](https://www.python.org/dev/peps/pep-0484/#suggested-syntax-for-python-2-7-and-straddling-code)

* [Using mypy with Python 2 code](http://mypy.readthedocs.io/en/latest/python2.html)

The mypy type checker is run automatically as part of Zulip's Travis
CI testing process in the 'static-analysis' build.

## `type_debug.py`

`zerver/lib/type_debug.py` has a useful decorator `print_types`.  It
prints the types of the parameters of the decorated function and the
return type whenever that function is called.  This can help find out
what parameter types a function is supposed to accept, or if
parameters with the wrong types are being passed to a function.

Here is an example using the interactive console:

```
>>> from zerver.lib.type_debug import print_types
>>>
>>> @print_types
... def func(x, y):
...     return x + y
...
>>> func(1.0, 2)
func(float, int) -> float
3.0
>>> func('a', 'b')
func(str, str) -> str
'ab'
>>> func((1, 2), (3,))
func((int, int), (int,)) -> (int, int, int)
(1, 2, 3)
>>> func([1, 2, 3], [4, 5, 6, 7])
func([int, ...], [int, ...]) -> [int, ...]
[1, 2, 3, 4, 5, 6, 7]
```

`print_all` prints the type of the first item of lists.  So `[int, ...]` represents
a list whose first element's type is `int`.  Types of all items are not printed
because a list can have many elements, which would make the output too large.

Similarly in dicts, one key's type and the corresponding value's type are printed.
So `{1: 'a', 2: 'b', 3: 'c'}` will be printed as `{int: str, ...}`.

## Zulip goals

Zulip is hoping to reach 100% of the codebase annotated with mypy
static types, and then enforce that it stays that way.  Our current
coverage is shown in
[Coveralls](https://coveralls.io/github/zulip/zulip).

## Installing mypy

If you installed Zulip's development environment correctly, mypy
should already be installed inside the Python 3 virtualenv at
`zulip-py3-venv` (mypy only supports Python 3).  If it isn't installed
(e.g. because you haven't reprovisioned recently), you can run
`tools/install-mypy` to install it.

## Running mypy on Zulip's code locally

To run mypy on Zulip's python code, run the command:

    tools/run-mypy

It will output errors in the same style as a compiler would.  For
example, if your code has a type error like this:

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
tracking the (older) latest mypy release on PyPI.

## Excluded files

Since several Python files in Zulip's code don't pass mypy's checks
(even for unannotated code) right now, a list of files to be excluded
from the check for CI is present in `tools/run-mypy`.

To run mypy on all Python files, ignoring the exclude list, you can
pass the `--all` option to `tools/run-mypy`.

    tools/run-mypy --all

If you type annotate some of those files so that they pass without
errors, please remove them from the exclude list.

## Mypy is there to find bugs in Zulip before they impact users

For the purposes of Zulip development, you can treat `mypy` like a
much more powerful linter that can catch a wide range of bugs.  If,
after running `tools/run-mypy` on your Zulip branch, you get mypy
errors, it's important to get to the bottom of the issue, not just do
something quick to silence the warnings.  Possible explanations include:

* A bug in any new type annotations you added.
* A bug in the existing type annotations.
* A bug in Zulip!
* Some Zulip code is correct but confusingly reuses variables with
  different types.
* A bug in mypy (though this is increasingly rare as mypy is now
  fairly mature as a project).

Each explanation has its own solution, but in every case the result
should be solving the mypy warning in a way that makes the Zulip
codebase better.  If you need help understanding an issue, please feel
free to mention @sharmaeklavya2 or @timabbott on the relevant pull
request or issue on GitHub.

If you think you have found a bug in Zulip or mypy, inform the zulip
developers by opening an issue on [Zulip's GitHub
repository](https://github.com/zulip/zulip/issues) or posting on
[zulip-devel](https://groups.google.com/d/forum/zulip-devel).  If it's
indeed a mypy bug, we can help with reporting it upstream.

## Annotating strings

In Python 3, strings can have non-ASCII characters without any problems.
Such characters are required to support languages which use non-latin
scripts like Japanese and Hindi.  They are also needed to support special
characters like mathematical symbols, musical symbols, etc.
In Python 2, however, `str` generally doesn't work well with non-ASCII
characters.  That's why `unicode` was introduced in Python 2.

But there are problems with the `unicode` and `str` system.  Implicit
conversions between `str` and `unicode` use the `ascii` codec, which
fails on strings containing non-ASCII characters.  Such errors are hard
to detect by people who always write in English.  To minimize such
implicit conversions, we should have a strict separation between `str`
and `unicode` in Python 2.  It might seem that using `unicode` everywhere
will solve all problems, but unfortunately it doesn't.  This is because
some parts of the standard library and the Python language (like keyword
argument unpacking) insist that parameters passed to them are `str`.

To make our code work correctly in Python 2, we have to identify strings
which contain data which could come from non-ASCII sources like stream
names, people's names, domain names, content of messages, emails, etc.
These strings should be `unicode`.  We also have to identify strings
which should be `str` like Exception names, attribute names, parameter
names, etc.

Mypy can help with this.  We just have to annotate each string as either
`str` or `unicode` and mypy's static type checking will tell us if we
are incorrectly mixing the two.  However, `unicode` is not defined in
Python 3.  We want our code to be Python 3 compatible in the future.
This can be achieved using 'six', a Python 2 and 3 compatibility library.

`six.text_type` is defined as `str` in Python 3 and as `unicode` in
Python 2.  We'll be using `text_type` (instead of `unicode`) and `str`
to annotate strings in Zulip's code.  We follow the style of doing
`from six import text_type` and using `text_type` for annotation instead
of doing `import six` and using `six.text_type` for annotation, because
`text_type` is used so extensively for type annotations that we don't
need to be that verbose.

Sometimes you'll find that you have to convert strings from one type to
another.  `zerver/lib/str_utils.py` has utility functions to help with that.
It also has documentation (in docstrings) which explains the right way
to use them.
