# Copyright 2009 Facebook
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""Automatically restart the server when a source file is modified.

Most applications should not access this module directly.  Instead,
pass the keyword argument ``autoreload=True`` to the
`tornado.web.Application` constructor (or ``debug=True``, which
enables this setting and several others).  This will enable autoreload
mode as well as checking for changes to templates and static
resources.  Note that restarting is a destructive operation and any
requests in progress will be aborted when the process restarts.  (If
you want to disable autoreload while using other debug-mode features,
pass both ``debug=True`` and ``autoreload=False``).

This module can also be used as a command-line wrapper around scripts
such as unit test runners.  See the `main` method for details.

The command-line wrapper and Application debug modes can be used together.
This combination is encouraged as the wrapper catches syntax errors and
other import-time failures, while debug mode catches changes once
the server has started.

This module depends on `.IOLoop`, so it will not work in WSGI applications
and Google App Engine.  It also will not work correctly when `.HTTPServer`'s
multi-process mode is used.

Reloading loses any Python interpreter command-line arguments (e.g. ``-u``)
because it re-executes Python using ``sys.executable`` and ``sys.argv``.
Additionally, modifying these variables will cause reloading to behave
incorrectly.

"""

# Further patched by Zulip check whether the code we're about to
# reload actually imports before reloading into it.  This fixes a
# major development workflow problem, where if one did a `git rebase`,
# Tornado would crash itself by auto-reloading into a version of the
# code that didn't work.

from __future__ import absolute_import, division, print_function

import os
import sys
import functools
import importlib
import traceback
import types
import subprocess
import weakref

from tornado import ioloop
from tornado.log import gen_log
from tornado import process

try:
    import signal
except ImportError:
    signal = None

# os.execv is broken on Windows and can't properly parse command line
# arguments and executable name if they contain whitespaces. subprocess
# fixes that behavior.
_has_execv = sys.platform != 'win32'

_watched_files = set()
_reload_hooks = []
_reload_attempted = False
_io_loops = weakref.WeakKeyDictionary()  # type: ignore # upstream
needs_to_reload = False

def start(io_loop=None, check_time=500):
    """Begins watching source files for changes.

    .. versionchanged:: 4.1
       The ``io_loop`` argument is deprecated.
    """
    io_loop = io_loop or ioloop.IOLoop.current()
    if io_loop in _io_loops:
        return
    _io_loops[io_loop] = True
    if len(_io_loops) > 1:
        gen_log.warning("tornado.autoreload started more than once in the same process")
    modify_times = {}
    callback = functools.partial(_reload_on_update, modify_times)
    scheduler = ioloop.PeriodicCallback(callback, check_time, io_loop=io_loop)
    scheduler.start()


def wait():
    """Wait for a watched file to change, then restart the process.

    Intended to be used at the end of scripts like unit test runners,
    to run the tests again after any source file changes (but see also
    the command-line interface in `main`)
    """
    io_loop = ioloop.IOLoop()
    start(io_loop)
    io_loop.start()


def watch(filename):
    """Add a file to the watch list.

    All imported modules are watched by default.
    """
    _watched_files.add(filename)


def add_reload_hook(fn):
    """Add a function to be called before reloading the process.

    Note that for open file and socket handles it is generally
    preferable to set the ``FD_CLOEXEC`` flag (using `fcntl` or
    ``tornado.platform.auto.set_close_exec``) instead
    of using a reload hook to close them.
    """
    _reload_hooks.append(fn)


def _reload_on_update(modify_times):
    global needs_to_reload
    if _reload_attempted:
        # We already tried to reload and it didn't work, so don't try again.
        return
    if process.task_id() is not None:
        # We're in a child process created by fork_processes.  If child
        # processes restarted themselves, they'd all restart and then
        # all call fork_processes again.
        return
    for module in list(sys.modules.values()):
        # Some modules play games with sys.modules (e.g. email/__init__.py
        # in the standard library), and occasionally this can cause strange
        # failures in getattr.  Just ignore anything that's not an ordinary
        # module.
        if not isinstance(module, types.ModuleType):
            continue
        path = getattr(module, "__file__", None)
        if not path:
            continue
        if path.endswith(".pyc") or path.endswith(".pyo"):
            path = path[:-1]

        result = _check_file(modify_times, module, path)
        if result is False:
            # If any files errored, we abort this attempt at reloading.
            return
        if result is True:
            # If any files had actual changes that import properly,
            # we'll plan to reload the next time we run with no files
            # erroring.
            needs_to_reload = True

    if needs_to_reload:
        _reload()


def _check_file(modify_times, module, path):
    try:
        modified = os.stat(path).st_mtime
    except Exception:
        return
    if path not in modify_times:
        modify_times[path] = modified
        return
    if modify_times[path] != modified:
        gen_log.info("%s modified; restarting server", path)
        modify_times[path] = modified
    else:
        return

    try:
        importlib.reload(module)
    except Exception:
        gen_log.error("Error importing %s, not reloading" % (path,))
        traceback.print_exc()
        return False
    return True

def _reload():
    global _reload_attempted
    _reload_attempted = True
    for fn in _reload_hooks:
        fn()
    if hasattr(signal, "setitimer"):
        # Clear the alarm signal set by
        # ioloop.set_blocking_log_threshold so it doesn't fire
        # after the exec.
        signal.setitimer(signal.ITIMER_REAL, 0, 0)
    # sys.path fixes: see comments at top of file.  If sys.path[0] is an empty
    # string, we were (probably) invoked with -m and the effective path
    # is about to change on re-exec.  Add the current directory to $PYTHONPATH
    # to ensure that the new process sees the same path we did.
    path_prefix = '.' + os.pathsep
    if (sys.path[0] == '' and
            not os.environ.get("PYTHONPATH", "").startswith(path_prefix)):
        os.environ["PYTHONPATH"] = (path_prefix +
                                    os.environ.get("PYTHONPATH", ""))
    if not _has_execv:
        subprocess.Popen([sys.executable] + sys.argv)
        sys.exit(0)
    else:
        try:
            os.execv(sys.executable, [sys.executable] + sys.argv)
        except OSError:
            # Mac OS X versions prior to 10.6 do not support execv in
            # a process that contains multiple threads.  Instead of
            # re-executing in the current process, start a new one
            # and cause the current process to exit.  This isn't
            # ideal since the new process is detached from the parent
            # terminal and thus cannot easily be killed with ctrl-C,
            # but it's better than not being able to autoreload at
            # all.
            # Unfortunately the errno returned in this case does not
            # appear to be consistent, so we can't easily check for
            # this error specifically.
            os.spawnv(os.P_NOWAIT, sys.executable,
                      [sys.executable] + sys.argv)
            # At this point the IOLoop has been closed and finally
            # blocks will experience errors if we allow the stack to
            # unwind, so just exit uncleanly.
            os._exit(0)
