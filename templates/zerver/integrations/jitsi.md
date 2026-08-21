# Use Jitsi Meet as your call provider in Zulip

By default, Zulip integrates with [Jitsi Meet](https://jitsi.org/jitsi-meet/),
a fully-encrypted, 100% open source video conferencing solution. Users will be
able to start a Jitsi Meet call and invite others using the **add video call**
(<i class="zulip-icon zulip-icon-video-call"></i>) or **add voice call**
(<i class="zulip-icon zulip-icon-voice-call"></i>) button [in the compose
box](/help/start-a-call).

## Configure a self-hosted instance of Jitsi Meet

Zulip uses the [cloud version of Jitsi Meet](https://meet.jit.si/) as
its default video call provider. In a self-hosted installation, you can
change it to a self-hosted Jitsi Meet server. See the [server
documentation](https://zulip.readthedocs.io/en/stable/production/video-calls.html#jitsi)
for details.

### Customization per organization

Organization administrators can use their own self-hosted instance of Jitsi Meet
for their organization:

{start_tabs}

{settings_tab|organization-settings}

1. Under **Compose settings**, confirm **Jitsi Meet** is selected in
   the **Call provider** dropdown.

1. Select **Custom URL** from the **Jitsi server URL** dropdown, and
   enter the URL of your self-hosted Jitsi Meet server.

1. Click **Save changes**.

{end_tabs}

!!! tip ""

    Self-hosted instances of Zulip can be configured to use
    [Jitsi with JWT Token Authentication](https://zulip.readthedocs.io/en/stable/production/video-calls.html#jwt-authentication).
    JWT authentication only applies to organizations using the
    server-wide default Jitsi Meet server. An organization that
    overrides the Jitsi Meet server URL in its organization settings
    falls back to unauthenticated calls against that custom server.

## Related documentation

- [How to start a call](/help/start-a-call)
- [Server-side video call configuration](https://zulip.readthedocs.io/en/stable/production/video-calls.html)
- [Zoom integration](/integrations/zoom)
- [BigBlueButton integration](/integrations/big-blue-button)
- [Constructor Groups integration](/integrations/constructor-groups)
- [Nextcloud Talk integration](/integrations/nextcloud-talk)
- [Webex integration](/integrations/webex)
