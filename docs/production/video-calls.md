# Video call providers

This page documents the server-level configuration required to support
non-default [video call integration
options](https://zulip.com/help/start-a-call) on a self-hosted Zulip
server.

## Zoom

To use the [Zoom](https://zoom.us) integration on a self-hosted
installation, you'll need to register a custom Zoom app as follows:

1. Select [**Build App**](https://marketplace.zoom.us/develop/create)
   at the Zoom Marketplace.

1. Create an app with the **OAuth** type.

   * Choose an app name such as "ExampleCorp Zulip".
   * Select **User-managed app**.
   * Disable the option to publish the app on the Marketplace.
   * Click **Create**.

1. Inside of the Zoom app management page:

   * On the **App Credentials** tab, set both the **Redirect URL for
     OAuth** and the **Whitelist URL** to
     `https://zulip.example.com/calls/zoom/complete` (replacing
     `zulip.example.com` by your main Zulip hostname).
   * On the **Scopes** tab, add the `meeting:write` scope.

You can then configure your Zulip server to use that Zoom app as
follows:

1. In `/etc/zulip/zulip-secrets.conf`, set `video_zoom_client_secret`
   to be your app's "Client Secret".

1. In `/etc/zulip/settings.py`, set `VIDEO_ZOOM_CLIENT_ID` to your
   app's "Client ID".

1. Restart the Zulip server with
   `/home/zulip/deployments/current/scripts/restart-server`.

This enables Zoom support in your Zulip server.  Finally, [configure
Zoom as the video call
provider](https://zulip.com/help/start-a-call) in the Zulip
organization(s) where you want to use it.

## Big Blue Button

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
