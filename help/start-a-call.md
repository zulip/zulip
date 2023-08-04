# Start a video call

{start_tabs}

{!start-composing.md!}

{tab|desktop-web}

1. Click the **video camera** (<i class="fa fa-video-camera"></i>) icon at the
   bottom of the compose box. This will insert a **Join video call.** link into
   your message.

1. Send the message.

1. Click on the link in the message to start or join the call.

!!! tip ""

    You can replace the "Join video call." label for the link with any text you
    like.

{tab|mobile}

1. Navigate to a stream, topic, or direct message view.

1. Tap the **video camera**
   (<img src="/static/images/help/mobile-video-icon.svg" alt="video" class="mobile-icon"/>)
   button at the bottom of the app. This will insert a **Click to join video call**
   link into your message.

1. If you are in a stream view, choose a destination topic by tapping the
   compose box and selecting an existing topic or typing a new topic name.

1. Send the message.

1. Tap the link in the message to start or join the call.

!!! tip ""

    You can replace the "Click to join video call" label for the link with any
    text you like.

{end_tabs}

## Change your video call provider

By default, Zulip integrates with
[Jitsi Meet](https://jitsi.org/jitsi-meet/), a fully-encrypted, 100% open
source video conferencing solution. Organization administrators can also
change the organization's video call provider. The video call providers
supported by zulip are:

* [Jitsi Meet](/integrations/doc/jitsi)
* [Zoom integration](/integrations/doc/zoom)
* [BigBlueButton integration](/integrations/doc/big-blue-button)

!!! tip ""

    It is also possible to disable the video call button for your organization by
    setting the provider to "None".

### Change your organization's video call provider

{start_tabs}

{settings_tab|organization-settings}

1. Under **Other settings** select appropriate provider from **Video call provider** dropdown.

1. Click **Save changes**.

{end_tabs}

[big-blue-button-configuration]: https://zulip.readthedocs.io/en/stable/production/video-calls.html#bigbluebutton
[zoom-configuration]: https://zulip.readthedocs.io/en/stable/production/video-calls.html#zoom

## Related articles

* [Insert a link](/help/insert-a-link)
