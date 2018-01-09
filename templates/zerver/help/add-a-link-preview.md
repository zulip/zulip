# Add a link preview

{!server-admin-only.md!}

Link previews are a way to see an overview of a link's content before
clicking on it. Previews can provide a useful summary of the content of a site
before you click on it, while also providing a quick integrity check to ensure
the link you meant to post is in fact correct.

![Link preview example](/static/images/help/link-preview.png)

Follow these steps to enable link previews:

1. Open the `zproject/settings.py` file in the Zulip directory.
    !!! tip ""
        To learn more about the settings and how to configure
        them, take a look at [this documentation](https://zulip.readthedocs.io/en/latest/subsystems/settings.html)

2. Search for the line with the attribute `INLINE_URL_EMBED_PREVIEW` and set the
   value from `False` to `True` to enable the embed preview feature.
   ![Setting "INLINE_URL_EMBED_PREVIEW" to true.](/static/images/help/inline-url-true.png)

3. Restart the server to apply the changes.

![Multiple link preview example](/static/images/help/link-preview-max.png)

Zulip currently supports up to five link previews per post — only the first
five link previews in the message will be shown.
