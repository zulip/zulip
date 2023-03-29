# Configure authentication methods

{!owner-only.md!}

By default, Zulip allows logging in via email/password as well as
various social authentication providers like Google, GitHub, GitLab,
and Apple. You can restrict users to logging in via only a subset of
these methods.

LDAP and various custom SSO login methods are currently restricted to
self-hosted Zulip organizations only. SAML authentication is supported
by Zulip Cloud but requires contacting support@zulip.com to configure it.

**Note:** If you are running your own server,
[read this](https://zulip.readthedocs.io/en/stable/production/authentication-methods.html)
first. Server configuration is needed for several of the authentication
methods listed above.

### Configure authentication methods

{start_tabs}

{settings_tab|auth-methods}

2. Toggle the checkboxes next to the available login options.

{!save-changes.md!}

{end_tabs}

## Related articles

* [Configuring authentication methods](https://zulip.readthedocs.io/en/stable/production/authentication-methods.html)
  for server administrators (self-hosted only)
