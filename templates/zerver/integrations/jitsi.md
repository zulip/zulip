# Use Jitsi Meet as your call provider in Zulip

By default, Zulip integrates with [Jitsi Meet](https://jitsi.org/jitsi-meet/),
a fully-encrypted, 100% open source video conferencing solution. Users will be
able to start a Jitsi Meet call and invite others using the **add video call**
(<i class="zulip-icon zulip-icon-video-call"></i>) or **add voice call**
(<i class="zulip-icon zulip-icon-voice-call"></i>) button [in the compose
box](/help/start-a-call).

## Configure a self-hosted instance of Jitsi Meet

Zulip uses the [cloud version of Jitsi Meet](https://meet.jit.si/)
as its default video call provider. You can also use a self-hosted
instance of Jitsi Meet.

{start_tabs}

{settings_tab|organization-settings}

1. Under **Compose settings**, confirm **Jitsi Meet** is selected in the
   **Call provider** dropdown.

1. Select **Custom URL** from the **Jitsi server URL** dropdown, and enter
   the URL of your self-hosted Jitsi Meet server.

1. Click **Save changes**.

{end_tabs}

## Related documentation

- [How to start a call](/help/start-a-call)
- [Zoom integration](/integrations/doc/zoom)
- [BigBlueButton integration](/integrations/doc/big-blue-button)
