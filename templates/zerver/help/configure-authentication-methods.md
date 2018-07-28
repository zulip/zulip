# Configure authentication methods

{!admin-only.md!}

You can configure your organization settings to allow users to authenticate
themselves using passwords, Google/GitHub OAuth, LDAP (currently on premises
only), and/or various other SSO methods (also currently on premises only).

!!! tip ""
    If you are unsure about what these mean, don't worry! Zulip
    allows logging in via email and password by default.

{settings_tab|auth-methods}

2. Toggle the checkboxes next to the available login options to enable your
organization's authentication methods. Not all methods will show up by
default. To enable more methods, contact your server administrator at
{{support_email}} and ask them to add more authentication backends by
configuring the server with
[these instructions](https://zulip.readthedocs.io/en/latest/production/authentication-methods.html).

     * **Email** - Use an email and password created on Zulip to log in.

     * **GitHub** - Use [GitHub](https://github.com/) accounts to log in.

     * **Google** - Use [Google](https://google.com/) accounts to log in.

     * **LDAP** - Use a [LDAP](https://en.wikipedia.org/wiki/Lightweight_Directory_Access_Protocol)
     username and password to log in.

     * **RemoteUser** - Use a [Single-Sign-On](https://en.wikipedia.org/wiki/Single_sign-on)
     system to log in.


{!save-changes.md!}
