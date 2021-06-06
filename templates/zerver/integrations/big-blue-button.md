Zulip supports using Big Blue Button as its video call video call
provider. This is currently only possible on self-hosted Zulip
installations.

To use the [Big Blue Button](https://bigbluebutton.org/) video call
integration, you'll need to have a Big Blue Button server and
configure your zulip server to use that Big Blue Button server.

### Configure Big Blue Button server

1. Get the Shared Secret using the `bbb-conf --secret` command on your
   Big Blue Button Server. See also
   [Big Blue Button documentation](https://docs.bigbluebutton.org/2.2/customize.html#extract-the-shared-secret).

1. Get the URL to your Big Blue Button API. The URL has the form of
   `https://bigbluebutton.example.com/bigbluebutton/` and can also be
   found using the `bbb-conf --secret` command.

### Configure zulip server

1. In `/etc/zulip/zulip-secrets.conf`, set `big_blue_button_secret`
   as your Big Blue Button Server's shared secret.

1. In `/etc/zulip/settings.py`, set `BIG_BLUE_BUTTON_URL`
   as your Big Blue Button Server's API URL.

1. Restart the Zulip server with
   `/home/zulip/deployments/current/scripts/restart-server`.

### Using Big Blue Button

1. Select Big Blue Button as the organization's [video call provider](/help/start-a-call#changing-your-organizations-video-call-provider).

1. Zulip's [call button](/help/start-a-call) will now create meetings
   using Big Blue Button.
