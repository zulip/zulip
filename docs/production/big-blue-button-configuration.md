# Big Blue Button video calling configuration

To use the [Big Blue Button](https://bigbluebutton.org/) video call
integration on a self-hosted Zulip installation, you'll need to have a
Big Blue Button server and configure it:

1. Get the Shared Secret using the `bbb-conf --secret` command on your
   Big Blue Button Server. See also [the Big Blue Button
   documentation](https://docs.bigbluebutton.org/2.2/customize.html#extract-the-shared-secret).

2. Get the URL to your Big Blue Button API. The URL has the form of
   `https://bigbluebutton.example.com/bigbluebutton/` and can also be
   found using the `bbb-conf --secret` command.

You can then configure your Zulip server to use that Big Blue Button
Server as follows:

1. In `/etc/zulip/zulip-secrets.conf`, set `big_blue_button_secret`
   to be your Big Blue Button Server's shared secret.

2. In `/etc/zulip/settings.py`, set `BIG_BLUE_BUTTON_URL` to your
   to be your Big Blue Button Server's API URL.

3. Restart the Zulip server with
   `/home/zulip/deployments/current/scripts/restart-server`.

This enables Big Blue Button support in your Zulip server.  Finally, [configure
Big Blue Button as the video call
provider](https://zulip.com/help/start-a-call) in the Zulip
organization(s) where you want to use it.
