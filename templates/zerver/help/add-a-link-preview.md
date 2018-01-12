# Add a link preview

{!admin-only.md!}

Link preview is a way to see an overview of the content before clicking it.
This can be useful for various reasons, from safety precautions to quick
integrity check to make sure the user actually posted the right link.
Here's an example of link preview:

![Link preview example](/static/images/help/link-preview.png)

Follow these steps to enable a link preview:

1. Go to your server's Django settings file, `settings.py`. If you have a
   problem locating one, try searching it in `/etc/zulip/`.
   Open the file.
   ![Settings file](/static/images/help/settings-file.png)

    !!! tip ""
        To learn more about the settings and how to configure
        them, take a look at [this documentation](https://zulip.readthedocs.io/en/latest/subsystems/settings.html)

2. Search for the word `INLINE_URL`. This is enough to find the key that we
   wanted (`INLINE_URL_EMBED_PREVIEW`)
   ![Inline URL](/static/images/help/inline-url-search.png)

3. Set the value from `False` to `True`. This enables the embed preview
   feature.
   ![Inline URL True](/static/images/help/inline-url-true.png)

4. Restart the server to apply the changes.

Link preview supports up to 5 previews per post:

![Link preview max URL](/static/images/help/link-preview-max.png)

Above that, Zulip doesn't show any link preview for any of the links posted:

![Link preview none](/static/images/help/link-preview-none.png)

