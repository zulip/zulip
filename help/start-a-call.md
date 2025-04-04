# Start a call

Zulip makes it convenient to add a video or voice call link to any message,
using the call provider (Jitsi, Zoom, etc.)
[configured](/help/configure-call-provider) by your organization's
administrators.

## Start a video call

!!! warn ""

    When you join a call, you may need to log in to a separate account for the
    call provider (Jitsi, Zoom, etc.).

{start_tabs}

{tab|desktop-web}

{!start-composing.md!}

1. Click the **Add video call** (<i class="zulip-icon zulip-icon-video-call"></i>)
   icon at the bottom of the compose box. This will insert a **Join video call.**
   link into your message.

1. Send the message.

1. Click on the link in the message to start or join the call.

!!! tip ""

    You can replace the "Join video call." label for the link with any text you
    like.

{tab|mobile}

1. Navigate to a channel, topic, or direct message view.

1. Tap the **Add video call**
   ( <img src="/static/images/help/mobile-video-icon.svg" alt="video"
   class="help-center-icon"/> )
   icon at the bottom of the app. This will insert a **Click to join video call**
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

1. Click the **Add voice call** (<i class="zulip-icon
   zulip-icon-voice-call"></i>) icon at the bottom of the compose box. This
   will insert a **Join voice call.** link into your message.

1. Send the message.

1. Click on the link in the message to start or join the call.

!!! tip ""

    You can replace the "Join voice call." label for the link with any text you
    like.

{end_tabs}

## Unlink your Zoom account from Zulip

If you linked your Zoom account to Zulip, and no longer want it to be connected,
you can unlink it.

{start_tabs}

1. Log in to the [Zoom App Marketplace](https://marketplace.zoom.us/), and
   select **Manage**.

1. Select **Added Apps** and click the **Remove** button next to the Zulip app.

1. Click **Confirm**.

{end_tabs}

[big-blue-button-configuration]: https://zulip.readthedocs.io/en/stable/production/video-calls.html#bigbluebutton
[zoom-configuration]: https://zulip.readthedocs.io/en/stable/production/video-calls.html#zoom

## Related articles

* [Configure call provider](/help/configure-call-provider)
* [Jitsi Meet integration](/integrations/doc/jitsi)
* [Zoom integration](/integrations/doc/zoom)
* [BigBlueButton integration](/integrations/doc/big-blue-button)
* [Insert a link](/help/insert-a-link)
