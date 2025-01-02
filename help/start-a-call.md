# Start a call

Zulip makes it convenient to add a video or voice call link to any message,
using the call provider (Jitsi, Zoom, etc.)
[configured](#change-your-call-provider) by your organization's administrators.

## Start a video call

!!! warn ""

    When you join a call, you may need to log in to a separate account for the
    call provider (Jitsi, Zoom, etc.).

{start_tabs}

{tab|desktop-web}

{!start-composing.md!}

1. Click the **video camera** (<i class="zulip-icon zulip-icon-video-call"></i>)
   icon at the bottom of the compose box. This will insert a **Join video call.**
   link into your message.

1. Send the message.

1. Click on the link in the message to start or join the call.

!!! tip ""

    You can replace the "Join video call." label for the link with any text you
    like.

{tab|mobile}

1. Navigate to a channel, topic, or direct message view.

1. Tap the **video camera**
   (<img src="/static/images/help/mobile-video-icon.svg" alt="video" class="help-center-icon"/>)
   button at the bottom of the app. This will insert a **Click to join video call**
   link into your message.

1. If you are in a channel view, choose a destination topic by tapping the
   compose box and selecting an existing topic or typing a new topic name.

1. Send the message.

1. Tap the link in the message to start or join the call.

!!! tip ""

    You can replace the "Click to join video call" label for the link with any
    text you like.

{end_tabs}

## Start a voice call

{start_tabs}

{tab|desktop-web}

{!start-composing.md!}

1. Click the **phone** (<i class="zulip-icon zulip-icon-voice-call"></i>) icon
   at the bottom of the compose box. This will insert a **Join voice call.**
   link into your message.

1. Send the message.

1. Click on the link in the message to start or join the call.

!!! tip ""

    You can replace the "Join voice call." label for the link with any text you
    like.

{end_tabs}

## Change your call provider

{!admin-only.md!}

By default, Zulip integrates with
[Jitsi Meet](https://jitsi.org/jitsi-meet/), a fully-encrypted, 100% open
source video conferencing solution. Organization administrators can also
change the organization's call provider. The call providers
supported by Zulip are:

* [Jitsi Meet](/integrations/doc/jitsi)
* [Zoom integration](/integrations/doc/zoom)
* [BigBlueButton integration](/integrations/doc/big-blue-button)

!!! tip ""

    You can disable the video and voice call buttons for your organization
    by setting the **call provider** to "None".

### Change your organization's call provider

{start_tabs}

{settings_tab|organization-settings}

1. Under **Other settings**, select the desired provider from the
   **Call provider** dropdown.

{!save-changes.md!}

{end_tabs}

### Use a self-hosted instance of Jitsi Meet

Zulip uses the [cloud version of Jitsi Meet](https://meet.jit.si/)
as its default call provider. You can also use a self-hosted
instance of Jitsi Meet.

{start_tabs}

{settings_tab|organization-settings}

1. Under **Other settings**, select **Custom URL** from the
   **Jitsi server URL** dropdown.

1. Enter the URL of your self-hosted Jitsi Meet server.

{!save-changes.md!}

{end_tabs}

[big-blue-button-configuration]: https://zulip.readthedocs.io/en/stable/production/video-calls.html#bigbluebutton
[zoom-configuration]: https://zulip.readthedocs.io/en/stable/production/video-calls.html#zoom

## Related articles

* [Insert a link](/help/insert-a-link)
