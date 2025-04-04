# Image, video and website previews

Zulip displays previews of images, videos and websites in your message feed. To
avoid disrupting the flow of conversation, these previews are small. You can
configure how animated images are previewed, and organization administrators can
also disable previews altogether.

## Configure how animated images are played

In the desktop and web apps, you can configure previews of animated images to
always show the animation, show it when you hover over the image with your
mouse, or not show it at all. For large animated images, only the first part of
the animation will be shown in the preview.

You can always see the full animated image by opening it in the [image
viewer](/help/view-images-and-videos).

!!! warn ""

    This configuration applies only to images uploaded since July 21, 2024 on
    Zulip Cloud, or on Zulip Server [9.0+](/help/view-zulip-version) in
    self-hosted organizations. Previews of images uploaded earlier are always
    animated.

{start_tabs}

{tab|desktop-web}

{settings_tab|preferences}

1. Under **Information**, select the desired option from the **Play animated
   images** dropdown.

{end_tabs}

## Configure whether image and video previews are shown

{!admin-only.md!}

{start_tabs}

{settings_tab|organization-settings}

1. Under **Message feeed settings**, toggle **Show previews of uploaded and
   linked images and videos**.

{!save-changes.md!}

{end_tabs}

## Configure whether website previews are shown

{!admin-only.md!}

{start_tabs}

{settings_tab|organization-settings}

1. Under **Message feed settings**, toggle **Show previews of linked websites**.

{!save-changes.md!}

{end_tabs}

## Security

To prevent images from being used to track Zulip users, Zulip proxies all
external images in messages through the server.

## Related articles

* [Manage your uploaded files](/help/manage-your-uploaded-files)
* [Share and upload files](/help/share-and-upload-files)
* [View images and videos](/help/view-images-and-videos)
* [Animated GIFs](/help/animated-gifs-from-giphy)
