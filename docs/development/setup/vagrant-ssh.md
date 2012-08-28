Once `vagrant up` has completed, connect to the development environment
with `vagrant ssh`:

```console
$ vagrant ssh
```

You should see output that starts like this:

```console
Welcome to Ubuntu 22.04.3 LTS (GNU/Linux 5.15.0-92-generic x86_64)
```

Congrats, you're now inside the Zulip development environment!

You can confirm this by looking at the command prompt, which starts
with `(zulip-server) vagrant@`. If it just starts with `vagrant@`, your
provisioning failed and you should look at the
[troubleshooting section](/development/setup-recommended.md#troubleshooting-and-common-errors).

Next, start the Zulip server:

```console
(zulip-server) vagrant@vagrant:/srv/zulip$ ./tools/run-dev
```

You will see something like:

```console
Starting Zulip on:

        http://localhost:9991/

Internal ports:
   9991: Development server proxy (connect here)
   9992: Django
   9993: Tornado
   9994: webpack

Tornado server (re)started on port 9993

2023-12-15 20:57:14.206 INFO [process_queue] 13 queue worker threads were launched
frontend:
  frontend (webpack 5.89.0) compiled successfully in 8054 ms
```

Now the Zulip server should be running and accessible. Verify this by
navigating to <http://localhost:9991/devlogin> in the browser on your main machine.

You should see something like this:

![Image of Zulip devlogin](/images/zulip-devlogin.png)

The Zulip server will continue to run and send output to the terminal window.
When you navigate to Zulip in your browser, check your terminal and you
should see something like:

```console
2016-05-04 18:21:57,547 INFO     127.0.0.1       GET     302 582ms (+start: 417ms) / (unauth@zulip via ?)
[04/May/2016 18:21:57]"GET / HTTP/1.0" 302 0
2016-05-04 18:21:57,568 INFO     127.0.0.1       GET     301   4ms /login (unauth@zulip via ?)
[04/May/2016 18:21:57]"GET /login HTTP/1.0" 301 0
2016-05-04 18:21:57,819 INFO     127.0.0.1       GET     200 209ms (db: 7ms/2q) /login/ (unauth@zulip via ?)
```
