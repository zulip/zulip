# Video call providers

Zulip makes it convenient to [start a
call](https://zulip.com/help/start-a-call) with the click of a button, using the
call provider of your choice. The call providers
supported by Zulip are:

- [Jitsi Meet](https://zulip.com/integrations/doc/jitsi), a fully-encrypted,
  100% open source video conferencing solution.
- [Zoom](https://zulip.com/integrations/doc/zoom)
- [BigBlueButton](https://zulip.com/integrations/doc/big-blue-button)

By default, Zulip uses the [cloud version of Jitsi Meet](https://meet.jit.si/)
as its call provider. This page documents the configurations required to support
other [video call integration options](https://zulip.com/help/start-a-call) on a
self-hosted Zulip server.

:::{note}
It is possible to disable the video and voice call buttons for your
organization by [setting the call
provider](https://zulip.com/help/start-a-call#change-your-organizations-call-provider)
to "None".
:::

## Jitsi

You can configure Zulip to use a self-hosted
instance of Jitsi Meet by providing the URL of your self-hosted Jitsi Meet
server [in organization
settings](https://zulip.com/help/start-a-call#use-a-self-hosted-instance-of-jitsi-meet).
No server configuration changes are required.

## Zoom

To use the [Zoom](https://zoom.us) integration on a self-hosted
installation, you'll need to register a custom Zoom app as follows:

1. Select [**Build App**](https://marketplace.zoom.us/develop/create)
   at the Zoom Marketplace.

1. Create an app with the **OAuth** type.

   - Choose an app name such as "ExampleCorp Zulip".
   - Select **User-managed app**.
   - Disable the option to publish the app on the Marketplace.
   - Click **Create**.

1. Inside the Zoom app management page:

   - On the **App Credentials** tab, set both the **Redirect URL for
     OAuth** and the **Whitelist URL** to
     `https://zulip.example.com/calls/zoom/complete` (replacing
     `zulip.example.com` by your main Zulip hostname).
   - On the **Scopes** tab, add the `meeting:write` scope.

You can then configure your Zulip server to use that Zoom app as
follows:

1. In `/etc/zulip/zulip-secrets.conf`, set `video_zoom_client_secret`
   to be your app's "Client Secret".

1. In `/etc/zulip/settings.py`, set `VIDEO_ZOOM_CLIENT_ID` to your
   app's "Client ID".

1. Restart the Zulip server with
   `/home/zulip/deployments/current/scripts/restart-server`.

This enables Zoom support in your Zulip server. Finally, [configure Zoom as the
video call
provider](https://zulip.com/help/start-a-call#change-your-organizations-call-provider)
in the Zulip organizations where you want to use it.

## BigBlueButton

To use the [BigBlueButton](https://bigbluebutton.org/) video call
integration on a self-hosted Zulip installation, you'll need to have a
BigBlueButton server and configure it:

1. Get the Shared Secret using the `bbb-conf --secret` command on your
   BigBlueButton Server. See also [the BigBlueButton
   documentation](https://docs.bigbluebutton.org/admin/customize.html#extract-the-shared-secret).

2. Get the URL to your BigBlueButton API. The URL has the form of
   `https://bigbluebutton.example.com/bigbluebutton/` and can also be
   found using the `bbb-conf --secret` command.

You can then configure your Zulip server to use that BigBlueButton
Server as follows:

1. In `/etc/zulip/zulip-secrets.conf`, set `big_blue_button_secret`
   to be your BigBlueButton Server's shared secret.

2. In `/etc/zulip/settings.py`, set `BIG_BLUE_BUTTON_URL` to your
   to be your BigBlueButton Server's API URL.

3. Restart the Zulip server with
   `/home/zulip/deployments/current/scripts/restart-server`.

This enables BigBlueButton support in your Zulip server. Finally, [configure
BigBlueButton as the video call
provider](https://zulip.com/help/start-a-call#change-your-organizations-call-provider)
in the Zulip organizations where you want to use it.
