# Configure authentication methods

{!owner-only.md!}

You can choose which authentication methods to enable for users to log in to
your organization. The following options are available on all
[plans](https://zulip.com/plans/):

- Email and password
- Social authentication: Google, GitHub, GitLab, Apple

The following options are available for organizations on Zulip Cloud Standard,
Zulip Cloud Plus, and all self-hosted Zulip servers:

- Oauth2 with Microsoft Entra ID (AzureAD)

The following options are available for organizations on Zulip Cloud Plus, and all self-hosted Zulip servers:

- [SAML authentication](/help/saml-authentication), including Okta, OneLogin, Entra ID (AzureAD), Keycloak, Auth0
- [SCIM provisioning](/help/scim)

The following authentication and identity management options are available for
all self-hosted servers. If you are interested in one of these options for a
Zulip Cloud organization, contact [support@zulip.com](mailto:support@zulip.com)
to inquire.

- [AD/LDAP user
  sync](https://zulip.readthedocs.io/en/stable/production/authentication-methods.html#ldap-including-active-directory)
- [AD/LDAP group
  sync](https://zulip.readthedocs.io/en/stable/production/authentication-methods.html#ldap-including-active-directory)
- [OpenID
  Connect](https://zulip.readthedocs.io/en/stable/production/authentication-methods.html#openid-connect)
- [Custom authentication
  options](https://python-social-auth.readthedocs.io/en/latest/backends/index.html#social-backends)
  with python-social-auth

### Configure authentication methods

!!! warn ""

    For self-hosted organizations, some authentication options require
    that you first [configure your
    server](https://zulip.readthedocs.io/en/stable/production/authentication-methods.html)
    to support the option.

!!! tip ""

    Before disabling an authentication method, test that you can
    successfully log in with one of the remaining authentication methods.
    The [`change_auth_backends` management
    command](https://zulip.readthedocs.io/en/stable/production/management-commands.html)
    can help if you accidentally lock out all administrators.

{start_tabs}

{settings_tab|auth-methods}

1. To use SAML authentication or SCIM provisioning, Zulip Cloud organizations
   must upgrade to [Zulip Cloud Plus](https://zulip.com/plans/), and contact
   [support@zulip.com](mailto:support@zulip.com) to enable these methods.

1. Toggle the checkboxes next to the available login options.

{!save-changes.md!}

{end_tabs}

## Related articles

* [Configuring authentication methods](https://zulip.readthedocs.io/en/stable/production/authentication-methods.html)
  for server administrators (self-hosted only)
* [SAML authentication](/help/saml-authentication)
* [SCIM provisioning](/help/scim)
