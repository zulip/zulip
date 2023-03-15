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

{tab|via-compose-box-buttons}

{!start-composing.md!}

1. Click the **paperclip** (<i class="fa fa-paperclip"></i>) icon at
   the bottom of the compose box to select one or more files. Zulip will upload
   the files, and insert named links using
   [Markdown formatting](/help/format-your-message-using-markdown#links):
   `[Link text](URL)`.

1. _(optional)_ Modify the link text as desired.

{end_tabs}

!!! tip ""

    You can [preview the message](/help/preview-your-message-before-sending)
    before sending to see what your uploaded files will look like.

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
