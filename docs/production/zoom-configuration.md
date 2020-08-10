# Zoom video calling OAuth configuration

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
