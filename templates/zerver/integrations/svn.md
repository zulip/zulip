It is easy to send Zulips on SVN commits, by configuring a
post-commit hook. To do this:

1. {!create-channel.md!}

1. {!download-python-bindings.md!}

1. Install `pysvn`. On Linux, you can install the `python-svn`
   package. On other platforms, you can install a binary or from
   source by following the [instructions on the pysvn website][1].

   [1]: http://pysvn.tigris.org/project_downloads.html

1. {!change-zulip-config-file.md!}

1. Copy `integrations/svn/zulip_svn_config.py` and
   `integrations/svn/post-commit` from the API bindings directory
   to the `hooks` subdirectory of your SVN repository.

1. The default stream used by this post-commit hook is `commits`; if
   you’d prefer a different stream, change it now in
   `zulip_svn_config.py`. Make sure that everyone interested in getting
   these post-commit Zulips is subscribed to that stream!

{!congrats.md!}

![SVN commit bot message](/static/images/integrations/svn/001.png)
