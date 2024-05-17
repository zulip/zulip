# Share and upload files

Zulip supports attaching multiple files to messages, including images,
documents, sound, and video. You can edit the names of the files others see
after you upload them.

For images and videos, a small preview will be shown directly in the message.
People reading the message can click on the preview to
[view the full-size image or video](/help/view-images-and-videos).

## Uploading files

{start_tabs}

{tab|via-drag-and-drop}

1. Drag and drop one or more files anywhere in the Zulip app,
   whether or not the compose box is open.
   Zulip will upload the files, and insert named links using
   [Markdown formatting](/help/format-your-message-using-markdown#links):
   `[Link text](URL)`.

1. _(optional)_ Modify the link text as desired.

!!! tip ""

    You can [preview the message](/help/preview-your-message-before-sending)
    before sending to see what your uploaded files will look like.

{tab|via-paste}

{!start-composing.md!}

1. Copy and paste one or more files into the compose box.
   Zulip will upload the files, and insert named links using
   [Markdown formatting](/help/format-your-message-using-markdown#links):
   `[Link text](URL)`.

1. _(optional)_ Modify the link text as desired.

!!! tip ""

    You can [preview the message](/help/preview-your-message-before-sending)
    before sending to see what your uploaded files will look like.

{tab|via-compose-box-buttons}

{!start-composing.md!}

1. Click the **paperclip** (<i class="zulip-icon zulip-icon-attachment"></i>)
   icon at the bottom of the compose box to select one or more files.
   Zulip will upload the files, and insert named links using
   [Markdown formatting](/help/format-your-message-using-markdown#links):
   `[Link text](URL)`.

1. _(optional)_ Modify the link text as desired.

!!! tip ""

    You can [preview the message](/help/preview-your-message-before-sending)
    before sending to see what your uploaded files will look like.

{tab|mobile}

1. Navigate to a channel, topic, or direct message view.

1. Tap the
   **paperclip** (<img src="/static/images/help/mobile-paperclip-icon.svg" alt="paperclip" class="help-center-icon"/>),
   **image** (<img src="/static/images/help/mobile-image-icon.svg" alt="image" class="help-center-icon"/>),
   or **camera** (<img src="/static/images/help/mobile-camera-icon.svg" alt="camera" class="help-center-icon"/>)
   button at the bottom of the app to select one or more files. Zulip will
   upload the files, and insert named links using
   [Markdown formatting](/help/format-your-message-using-markdown#links):
   `[Link text](URL)`.

1. _(optional)_ Modify the link text as desired.

{end_tabs}

!!! tip ""

    The link text will default to the name of the uploaded file.

## Sharing files

You can share files from other apps on Zulip.

{start_tabs}

{tab|android}

1. Select one or more files and tap the **Zulip**
   (<img src="/static/images/logo/zulip-icon-circle.svg" alt="logo" class="help-center-icon"/>)
   logo.

1. Select a channel name and topic name, or tap the
   **Direct message** tab and **Choose recipients**.

1. _(optional)_ Write a message.

1. Tap the **Send** button.

{end_tabs}

## Named file example

### What you type

```
[A whale of a good time](https://your.zulip.domain/user_uploads/1/46/IPvysqXEtiTG1ZdNBrwAZODi/whale-time.png)
```

### What it looks like

![Markdown image](/static/images/help/markdown-image.png)

## Troubleshooting info

Zulip does not generate thumbnails for messages with more than ten
attachments.

The maximum file size for attachments is 25MB in most Zulip installations.
This limit can be changed by the server administrator.

## Related articles

* [Manage your uploaded files](/help/manage-your-uploaded-files)
* [View images and videos](/help/view-images-and-videos)
* [Block image and link previews](/help/allow-image-link-previews)
* [Animated GIFs](/help/animated-gifs-from-giphy)
