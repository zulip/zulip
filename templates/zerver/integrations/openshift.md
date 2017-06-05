Ths integration sends a notification every time a deployment is made
in an OpenShift instance.

{! download-python-bindings.md !} Move it to your local copy of the
application’s repository.

Then, create a new commit including all the changes made to the
repository, and push it to your app.

After that, connect to the application through SSH. If you don’t know
how to do this, log in to your OpenShift Online account, go to your
application’s dashboard, and click “Want to log in to your
application?”.  There you’ll find the app’s SSH user, address, and
further information on SSH, in case you need it.

![](/static/images/integrations/openshift/002.png)

Once you have connected, install the Python bindings by running:

```bash
$ cd ~/app-root/repo/<python_bindings_path>
$ python setup.py install
```

Where `<python_bindings_path>` is the path where you saved the
bindings in the first step.

Next, open `integrations/openshift/zulip_openshift_config.py` inside
the SSH terminal with your favorite editor, and change the following
lines to specify the email address and API key for your OpenShift
integration:

```
ZULIP_USER = "openshift-bot@example.com"
ZULIP_API_KEY = "0123456789abcdef0123456789abcdef"
{% if api_site_required %}ZULIP_SITE = "{{ external_api_uri_subdomain }}"{% endif %}
```

You can also specify which pushes will result in notifications and to
what stream the notifications will be sent by modifying the
`deployment_notice_destination` function in
`zulip_openshift_config.py`. By default, deployments triggered by
commits pushed to the `master` and `test-post-receive` branches will
result in a notification to stream `deployments`.

Save the file, and symlink
`$OPENSHIFT_PYTHON_DIR/virtenv/share/zulip/integrations/openshift/post-receive`
into the `~/app-root/repo/.openshift/action_hooks` directory.

Next, create the stream you’d like to use for OpenShift notifications,
and subscribe all interested parties to this stream. The integration
will use the default stream `deployments` if no stream is supplied in
the hook; you still need to create the stream even if you are using
this default.

Whenever you make a push to the `master` branch of your application’s
repository (or whichever branch you configured above), or if you force
a deployment, the Zulip OpenShift plugin will send an automated
notification.

{! congrats.md !}

![](/static/images/integrations/openshift/001.png)

**Testing**

You can test the plugin without changing your `master` branch by pushing to the `test-post-receive` branch.
