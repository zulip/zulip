# Share and upload files

Zulip supports attaching multiple files to messages, including images,
documents, sound, and video. You can edit the names of the files others see
after you upload them.

Zulip will automatically generate a **thumbnail** for each file when you send
the message, if it can. Image thumbnails will be shown directly in the message,
and you can click on a thumbnail to [view the full image](/help/view-and-browse-images).

## Uploading files

{start_tabs}

{tab|via-markdown}

{!start-composing.md!}

1. Drag and drop files, or copy and paste one or more files into the compose
   box. Zulip will upload the files, and insert named links using
   [Markdown formatting](/help/format-your-message-using-markdown#links):
   `[Link text](URL)`.

1. _(optional)_ Modify the link text as desired.

!!! tip ""

    You can [preview the message](/help/preview-your-message-before-sending)
    before sending to see what your uploaded files will look like.

{tab|via-compose-box-buttons}

{!start-composing.md!}

1. Click the **paperclip** (<i class="fa fa-paperclip"></i>) icon at
   the bottom of the compose box to select one or more files. Zulip will upload
   the files, and insert named links using
   [Markdown formatting](/help/format-your-message-using-markdown#links):
   `[Link text](URL)`.

1. _(optional)_ Modify the link text as desired.

!!! tip ""

    You can [preview the message](/help/preview-your-message-before-sending)
    before sending to see what your uploaded files will look like.

{tab|mobile}

1. Navigate to a stream, topic, or direct message view.

1. Tap the
   **paperclip** (<img src="/static/images/help/mobile-paperclip-icon.svg" alt="paperclip" class="mobile-icon"/>),
   **image** (<img src="/static/images/help/mobile-image-icon.svg" alt="image" class="mobile-icon"/>),
   or **camera** (<img src="/static/images/help/mobile-camera-icon.svg" alt="camera" class="mobile-icon"/>)
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
   (<img src="/static/images/logo/zulip-icon-circle.svg" alt="logo" class="mobile-icon"/>)
   logo.

1. Select a stream name and topic name, or tap the
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
* [View and browse images](/help/view-and-browse-images)
* [Animated GIFs](/help/animated-gifs-from-giphy)
