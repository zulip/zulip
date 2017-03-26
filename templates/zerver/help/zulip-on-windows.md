# Using Zulip on Windows

Zulip has a Windows client, compatible with Windows versions 7, 8 and 10; it is identical in
functionality to the Zulip web application. The client
can be download through the [Zulip website](https://zulip.org/).

The client is regularly updated and is a wrapper of the web application, but with enhanced
notifications and can run in the background. The current version does not contain
any significant features additional to those in the web application.

!!! warn ""
    **Note:** Since Zulip is no longer running on a browser, many external keyboard shortcuts
    endemic to a browser will no longer work, for example, ALT-LEFT to go back to the previous page.

## Connecting to a server

When you open the Zulip client for the first time, you will come across a screen
asking for your organizations's server address on Zulip. Enter your organization's
address and press the **Connect** button.

!!! warn ""
    There's no need to add `https://` in the case that your server is running a secure
    HTTP (HTTPS) protocol.

    However, if your server uses an insecure HTTP connection, you'll have to
    write `http://` manually. A message will appear, warning you about the risks
    of using this type of connections. In case you have no other choice, choose the
    **Use HTTP** option.
