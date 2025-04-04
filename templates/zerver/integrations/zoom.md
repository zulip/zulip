# Use Zoom as your call provider in Zulip

You can configure Zoom as the call provider for your organization. Users will be
able to start a Zoom call and invite others using the **add video call** (<i
class="zulip-icon zulip-icon-video-call"></i>) or **add voice call** (<i
class="zulip-icon zulip-icon-voice-call"></i>) button [in the compose
box](/help/start-a-call).

## Configure Zoom as your call provider

By default, Zulip integrates with
[Jitsi Meet](https://jitsi.org/jitsi-meet/), a fully-encrypted, 100% open
source video conferencing solution. You can configure Zulip to use Zoom as your
call provider instead.

### Configure Zoom on Zulip Cloud

{start_tabs}

{settings_tab|organization-settings}

1. Under **Compose settings**, select Zoom from the **Call provider** dropdown.

1. Click **Save changes**.

{end_tabs}

Users will be prompted to log in to their Zoom account the first time they
join a call.

## Configure Zoom for a self-hosted organization

If you are self-hosting, you will need to [create a Zoom
application](https://zulip.readthedocs.io/en/latest/production/video-calls.html#zoom)
in order to use this integration.

## Related documentation

- [How to start a call](/help/start-a-call)
- [Jitsi Meet integration](/integrations/doc/jitsi)
- [BigBlueButton integration](/integrations/doc/big-blue-button)
