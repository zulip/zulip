Zulip supports using BigBlueButton as its video call video call
provider. This is currently only possible on self-hosted Zulip
installations.

To use the [BigBlueButton](https://bigbluebutton.org/) video call
integration, you'll need to have a BigBlueButton server and
configure your zulip server to use that BigBlueButton server.

### Configure BigBlueButton server

1. Get the Shared Secret using the `bbb-conf --secret` command on your
   BigBlueButton Server. See also
   [BigBlueButton documentation](https://docs.bigbluebutton.org/admin/customize.html#extract-the-shared-secret).

1. Get the URL to your BigBlueButton API. The URL has the form of
   `https://bigbluebutton.example.com/bigbluebutton/` and can also be
   found using the `bbb-conf --secret` command.

### Configure zulip server

1. In `/etc/zulip/zulip-secrets.conf`, set `big_blue_button_secret`
   as your BigBlueButton Server's shared secret.

1. In `/etc/zulip/settings.py`, set `BIG_BLUE_BUTTON_URL`
   as your BigBlueButton Server's API URL.

1. Restart the Zulip server with
   `/home/zulip/deployments/current/scripts/restart-server`.

### Using BigBlueButton

1. Select BigBlueButton as the organization's [video call provider](/help/start-a-call#changing-your-organizations-video-call-provider).

1. Zulip's [call button](/help/start-a-call) will now create meetings
   using BigBlueButton.
