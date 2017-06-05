It is easy to send Zulips on SVN commits, by configuring a post-commit hook. To do this:

First, create the stream you’d like to use for SVN commit
notifications, and subscribe all interested parties to this
stream. The integration will use the default stream `commits` if no
stream is supplied in the hook; you still need to create the stream
even if you are using this default.

Then:

1. {! download-python-bindings.md !}
2. Install `pysvn`. On Linux, you can install the `python-svn`
package. On other platforms, you can install a binary or from source
following the
[instructions on the pysvn website](http://pysvn.tigris.org/project_downloads.html).
3. Copy `integrations/svn/zulip_svn_config.py` and
`integrations/svn/post-commit` from the API bindings directory to the
`hooks` subdirectory of your SVN repository.
4. Next, open `integrations/git/zulip_svn_config.py` in your favorite
editor, and change the following lines to configure your SVN
integration:

        ZULIP_USER = "svn-bot@example.com"
        ZULIP_API_KEY = "0123456789abcdef0123456789abcdef"
        {% if api_site_required %}ZULIP_SITE = "{{ external_api_uri_subdomain }}"{% endif %}

5. The default stream used by this post-commit hook is `commits`; if
you’d prefer a different stream, change it now in
`zulip_svn_config.py`. Make sure that everyone interested in getting
these post-commit Zulips is subscribed to that stream!

{! congrats.md !}

![](/static/images/integrations/svn/001.png)
