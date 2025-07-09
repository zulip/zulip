# Share and upload files

Zulip supports attaching multiple files to messages, including images,
documents, sound, and video. You can edit the names of the files others see
after you upload them.

For images and videos, a small preview will be shown directly in the message, if
there are up to 24 attachments. People reading the message can click on the
preview to [view the full-size image or video](/help/view-images-and-videos).

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
   **paperclip** (<i class="zulip-icon zulip-icon-attachment mobile-help"></i>),
   **image** (<i class="zulip-icon zulip-icon-mobile-image mobile-help"></i>),
   or **camera** (<i class="zulip-icon zulip-icon-mobile-camera mobile-help"></i>)
   button at the bottom of the app to select one or more files. Zulip will
   upload the files, and insert named links using
   [Markdown formatting](/help/format-your-message-using-markdown#links):
   `[Link text](URL)`.

1. _(optional)_ Modify the link text as desired.

!!! warn ""

    Implementation of sharing files from other applications in the
    mobile app is tracked [on
    GitHub](https://github.com/zulip/zulip-flutter/issues/52). If
    you're interested in this feature, please react to the issue's
    description with 👍.

{end_tabs}

!!! tip ""

    The link text will default to the name of the uploaded file.

## Convert pasted to text to a file

When pasting a large amount of text, you can convert it to a text file upload.

{start_tabs}

{tab|desktop-web}

1. Paste a large amount of text into the compose box (2,000+ characters).

1. In the banner above the compose box, click **Yes, convert** to convert the
   pasted text to a file.

{end_tabs}

## Named file example

### What you type

```
[A whale of a good time](https://your.zulip.domain/user_uploads/1/46/IPvysqXEtiTG1ZdNBrwAZODi/whale-time.png)
```

### What it looks like

![Markdown image](/static/images/help/markdown-image.png)

## File upload limits

The Zulip Cloud Standard and Zulip Cloud Plus
[plans](https://zulip.com/plans/#cloud) include 5 GB of file storage per user.
Each uploaded file can be up to 1 GB.

The Zulip Cloud Free [plan](https://zulip.com/plans/#cloud) includes a total of
5 GB of file storage. Each uploaded file can be up to 10 MB.

In organizations on a self-hosted server, server administrators can configure
the maximum size for uploaded files via the `MAX_FILE_UPLOAD_SIZE`
[server setting][system-settings]. Setting it to 0 disables file uploads, and
hides the UI for uploading files from the web and desktop apps.

[system-settings]: https://zulip.readthedocs.io/en/stable/production/settings.html

## Related articles

* [Manage your uploaded files](/help/manage-your-uploaded-files)
* [View images and videos](/help/view-images-and-videos)
* [Image, video and website previews](/help/image-video-and-website-previews)
* [Animated GIFs](/help/animated-gifs-from-giphy)
