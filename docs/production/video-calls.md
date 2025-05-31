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
other [video call integration
options](https://zulip.com/help/configure-call-provider) on a self-hosted Zulip
server.

:::{note}
You can disable the video and voice call buttons for your organization by
[setting the call
provider](https://zulip.com/help/configure-call-provider)
to "None".
:::

## Jitsi

You can configure Zulip to use a self-hosted
instance of Jitsi Meet by providing the URL of your self-hosted Jitsi Meet
server [in organization
settings](https://zulip.com/help/configure-call-provider#use-a-self-hosted-instance-of-jitsi-meet).
No server configuration changes are required.

## Zoom

To use a [Zoom](https://zoom.us) integration on a self-hosted
installation, you'll need to register a custom Zoom application for
your Zulip server. Zulip supports two types of custom Zoom apps:

- [Server to Server OAuth app](#server-to-server-oauth-app): Easiest to set up,
  but requires users to be part of the Zoom organization that created the
  application in order to create calls.

- [General OAuth app](#general-oauth-app): Recommended for settings where the
  limitations of the Server to Server OAuth app are problematic (e.g., this is
  used by Zulip Cloud).

### Server to Server OAuth app

This Zoom application type, introduced in Zulip 10.0, is easiest to
set up, and is ideal for most installations that self-host Zulip. To
[create Zoom meeting links in Zulip
messages](https://zulip.com/help/start-a-call#start-a-call) using this
integration, users will will need to be members of your Zoom
organization and use the same email address in Zulip that they have
registered with Zoom.

You can set up this integration as follows:

1. Select [**Build App**](https://marketplace.zoom.us/develop/create)
   at the Zoom Marketplace. Create a **Server to Server OAuth App**.

1. Choose an app name such as "ExampleCorp Zulip".

1. In the **Information** tab:

   - Add a short description and company name.
   - Add a name and email for the developer contact information.

1. In the **Scopes** tab, add the `meeting:write:meeting:admin` and
   `meeting:write:meeting:master` scopes.

1. In the **Activation** tab, activate your app. You can now
   [configure your Zulip server](#configure-your-zulip-server)
   to use the app.

### General OAuth app

This Zoom application type is more flexible than the server-to-server
integration. However, current Zoom policy requires all General OAuth
apps to go through the full Zoom Marketplace review process, even for
[unlisted
apps](https://developers.zoom.us/docs/platform/key-concepts/#private-vs-beta-vs-published-vs-unlisted-apps)
that will only be used by a single customer. As a result, you have to
do quite a bit of publishing overhead work in order to create this
type of Zoom application for your Zulip server.

1. Select [**Build App**](https://marketplace.zoom.us/develop/create)
   at the Zoom Marketplace. Create a **General App**.

1. In the **Basic Information** tab:

   - Choose an app name such as "ExampleCorp Zulip".
   - Select **User-managed app**.
   - In the **OAuth Information** section, set the **OAuth Redirect URL**
     to `https://zulip.example.com/calls/zoom/complete` (replacing
     `zulip.example.com` by your main Zulip hostname).

1. In the **Scopes** tab, add the `meeting:write:meeting` scope.

1. Switch to the **Production** tab and complete the information needed
   for the [Zoom App Marketplace Review
   Process](https://developers.zoom.us/docs/distribute/app-review-process/)
   in the **App Listing** and **Technical Design** tabs.

1. [Submit your app for
   review](https://developers.zoom.us/docs/build-flow/submitting-apps-for-review/).
   Select the **Publish the app by myself** option on the **App Submission**
   page so that the app will be
   [unlisted](https://developers.zoom.us/docs/build-flow/publishing-your-apps/#unlisted-apps).

1. Once your app has been approved by the Zoom app review team, then
   you can proceed to [configure your Zulip server](#configure-your-zulip-server)
   to use the app.

### Configure your Zulip server

1. In `/etc/zulip/zulip-secrets.conf`, set `video_zoom_client_secret`
   to be your app's "Client Secret".

1. In `/etc/zulip/settings.py`, set `VIDEO_ZOOM_CLIENT_ID` to your
   app's "Client ID". If your using a Zoom
   [Server to Server OAuth app](#server-to-server-oauth-app),
   set `VIDEO_ZOOM_SERVER_TO_SERVER_ACCOUNT_ID` to be your app's "Account ID".

1. Restart the Zulip server with
   `/home/zulip/deployments/current/scripts/restart-server`.

This enables Zoom support in your Zulip server. Finally, [configure Zoom as the
video call
provider](https://zulip.com/help/configure-call-provider)
in the Zulip organizations where you want to use it.

## BigBlueButton

To use the [BigBlueButton](https://bigbluebutton.org/) video call
integration on a self-hosted Zulip installation, you'll need to have a
BigBlueButton server (version 2.4+) and configure it:

1. Get the Shared Secret using the `bbb-conf --secret` command on your
   BigBlueButton Server. See also [the BigBlueButton
   documentation](https://docs.bigbluebutton.org/administration/customize/#extract-the-shared-secret).

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
provider](https://zulip.com/help/configure-call-provider)
in the Zulip organizations where you want to use it.
