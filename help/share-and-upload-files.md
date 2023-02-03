# Share and upload files

Zulip supports attaching files to messages, including images, documents, sound,
and video. You can edit the name of the file others see after you upload it.

Zulip will automatically generate a **thumbnail** of the file when you send
it, if it can. Image thumbnails will be shown directly in the message, and you
can click on a thumbnail to [view the full image](/help/view-and-browse-images).

## Uploading a file

{start_tabs}

{tab|via-markdown}

{!start-composing.md!}

1. Drag and drop or copy and paste a file into the compose box to
   upload and insert a named link to the file:  
   `[File-name](URL)`

1. Modify the link text as desired.

{tab|via-compose-box-buttons}

{!start-composing.md!}

1. Click the **paperclip** (<i class="fa fa-paperclip"></i>) icon at
  the bottom of the compose box to select and upload a file.

1. Modify the link text as desired.

{end_tabs}

!!! tip ""

    You can [preview the message](/help/preview-your-message-before-sending) before
    sending to see what your uploaded files will look like.

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
