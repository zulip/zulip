To shut down but preserve the development environment so you can use
it again later use `vagrant halt` or `vagrant suspend`.

You can do this from the same Terminal/Git BASH window that is running
run-dev by pressing ^C to halt the server and then typing `exit`. Or you
can halt Vagrant from another Terminal/Git BASH window.

From the window where run-dev is running:

```console
2016-05-04 18:33:13,330 INFO     127.0.0.1       GET     200  92ms /register/ (unauth@zulip via ?)
^C
KeyboardInterrupt
(zulip-server) vagrant@vagrant:/srv/zulip$ exit
logout
Connection to 127.0.0.1 closed.
$
```

Now you can suspend the development environment:

```console
$ vagrant suspend
==> default: Saving VM state and suspending execution...
```

If `vagrant suspend` doesn't work, try `vagrant halt`:

```console
$ vagrant halt
==> default: Attempting graceful shutdown of VM...
```

Check out the Vagrant documentation to learn more about
[suspend](https://www.vagrantup.com/docs/cli/suspend.html) and
[halt](https://www.vagrantup.com/docs/cli/halt.html).
