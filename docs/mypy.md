# mypy static checker

Zulip now uses mypy. mypy is a compile-time type checker for python.
For information about what mypy is, visit [http://mypy-lang.org/](http://mypy-lang.org/).

mypy is also one of Zulip's Travis CI checks.

## Running mypy on Zulip's code

To run mypy on Zulip's code, you'll need to make sure that mypy is installed.
mypy only runs on python 3.
Since mypy is a new tool under rapid development, Zulip is using a pinned version
of mypy from its [git repository](https://github.com/python/mypy) rather than
tracking the (older) latest mypy release on pypi.

* If you installed Zulip's development environment using vagrant or provision.py,
  mypy is already installed.

* If you haven't installed Zulip using vagrant or provision.py, you will have to
  install a python 3 virtualenv and then install mypy on it.
  On Ubuntu, you can run `tools/install-mypy` to do that.
  For other distros, you can read `tools/install-mypy` and manually run
  corresponding commands for your distro.

To run mypy on Zulip's python code, run the command:

    tools/run-mypy

tools/run-mypy will try to use mypy from `zulip-py3-venv` if you are on Python 2.

## Type annotating Zulip's code

Zulip uses Python 2 style type annotation for mypy. You can learn more about it at:

* [Python 2 type annotation syntax in PEP 484](https://www.python.org/dev/peps/pep-0484/#suggested-syntax-for-python-2-7-and-straddling-code)
* [Using mypy with Python 2 code](http://mypy.readthedocs.org/en/latest/python2.html)

Since a lot of python files in Zulip's code don't pass mypy's type annotation check right now,
a list of files to be excluded is present in tools/run-mypy.
To run mypy on all python files, ignoring the exclude list, you can pass the `--all` option to tools/run-mypy.

    tools/run-mypy --all

If you type annotate some of those files, please remove them from the exclude list.
