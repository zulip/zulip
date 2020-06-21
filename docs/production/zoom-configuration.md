# Zoom Video Calling OAuth Configuration

To use the [Zoom](https://zoom.us) integration on a self-hosted
installation, you'll need to register a custom Zoom Application as
follows:

1. Visit the [Zoom Marketplace](https://marketplace.zoom.us/develop/create).

1. Create a new application, choosing **OAuth** as the app type.
We recommend using a name like "ExampleCorp Zulip".

1. Select *account-level app* for the authentication type, disable
the option to publish the app in the Marketplace, and click **Create**.

1. Inside of the Zoom app management page, set the Redirect URL to
`https://zulip.example.com/calls/zoom/complete` (replacing
`zulip.example.com` by your main Zulip hostname).

1. Set the "Scopes" to `meeting:write:admin`.

You can then configure your Zulip server to use that Zoom application
as follows:

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
