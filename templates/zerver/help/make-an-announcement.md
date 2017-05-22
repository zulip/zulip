# Make an announcement

An announcement on Zulip is a message which will reach
all users in an organization.

## The #announce stream

The #announce stream is just like other streams in most ways, but it's
conventionally used for organization-wide announcements.

![Example message](/static/images/help/announce-message.png)

By default, everybody is subscribed to this stream. For this reason,
you'll want to keep the traffic on it low, so that people don't mute
it and miss an important announcement.

Additionally, Zulip's notification bot uses this stream for its
messages.

## Send an announcement

1. To send an announcement, click the **New stream message**
 button located at the bottom of your screen.
 A box similar to the one shown in the below image will appear.

    ![New stream message](/static/images/help/new-stream.png)

3. In the **Stream** field, input `announce` to select the `#announce` stream.

4. Enter the topic for your announcement in the **Topic** field.

    !!! tip ""
        Your topic name cannot be longer than 52 characters.

5. Enter your announcement in **Compose your message here...**
  (also known as the compose box).

6. Finally, you can now send your announcement by
  clicking the **Send** button or by pressing the enter key
  (if you have checked the option **Press Enter to send**).

!!! tip ""
    You can always cancel your message by clicking the x (<i
    class="icon-vector-remove"></i>) icon located at the top-right corner of
    your compose box or pressing the `Esc` key.


!!! warn ""
    **Note:** By default all users are subscribed to the `#announce` stream,
    but users can unsubscribe from and mute the stream. This means that
    announcements, although organization-wide, will not reach users who
    have muted or unsubscribed from the `#announce` stream.
