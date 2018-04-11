# Configure authentication methods

{!admin-only.md!}

You can configure your organization settings to allow users to authenticate
themselves using passwords, Google/GitHub OAuth, LDAP (currently on premise
only), and/or various other SSO methods (also currently on premise only).

!!! tip ""
    If you are unsure about what these mean, don't worry! Zulip
    allows logging in via email and password by default.

1. Go to the [Authentication methods](/#organization/auth-methods)
{!admin.md!}

2. Toggle the checkboxes next to the following options to configure your organization's authentication methods:

     * **Email** - Use an email and password created on Zulip to log in.

     * **GitHub** - Use [GitHub](https://github.com/) accounts to log in.

     * **Google** - Use [Google](https://google.com/) accounts to log in.

     * **LDAP** - Use a [LDAP](https://en.wikipedia.org/wiki/Lightweight_Directory_Access_Protocol)
     username and password to log in.

     * **RemoteUser** - Use a [Single-Sign-On](https://en.wikipedia.org/wiki/Single_sign-on)
     system to log in.

        !!! tip ""
            Not all methods will show up by default. To enable more methods,
            modify the `AUTHENTICATION_BACKENDS` list in the
            `/etc/zulip/settings.py` file.

{!save-changes.md!} authentication methods.
