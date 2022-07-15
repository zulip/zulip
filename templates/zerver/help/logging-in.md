# Logging in

By default, Zulip allows logging in via email/password as well as
various social authentication providers like Google, GitHub, GitLab,
and Apple.

Organization administrators can
[add other authentication methods](/help/configure-authentication-methods),
including the SAML and LDAP integrations, or disable any of the methods above.

You can log in with any method allowed by your organization, regardless of
how you signed up. E.g. if you originally signed up using your Google
account, you can later log in using GitHub, as long as your Google account
and GitHub account use the same email address.

## Log in to a Zulip organization for the first time

{start_tabs}

{tab|web}

1. Go to the Zulip URL of the organization.

1. Follow the on-screen instructions.

{tab|desktop}

!!! warn ""
    If you are having trouble connecting, you may need to set your
    [proxy settings](/help/connect-through-a-proxy) or add a
    [custom certificate](/help/custom-certificates).

1. Click the **plus** (<i class="fa fa-plus"></i>) icon in the
**organizations sidebar** on the left. You can also select **Add Organization**
from the **Zulip** menu in the top menu bar.

1. Enter the Zulip URL of the organization, and click **Connect**.

1. Follow the on-screen instructions.

{!desktop-toggle-sidebar-tip.md!}

{tab|mobile}

{!mobile-profile-menu.md!}

1. Tap **Switch account**.

1. Tap **Add new account**.

1. Enter the Zulip URL of the organization, and tap **Enter**.

1. Follow the on-screen instructions.

{end_tabs}

For subsequent logins, see [switching between organizations](/help/switching-between-organizations).

## Troubleshooting

### I don't know my Zulip URL

Some ideas:

* If you know your organization is hosted on
  [zulip.com](https://zulip.com), go to [find my
  account](https://zulip.com/accounts/find/) and enter the email
  address that you signed up with.

* Try guessing the URL. Zulip URLs often look like `<name>.zulipchat.com`,
 `zulip.<name>.com`, or `chat.<name>.com` (replace `<name>` with the name of your
  organization).

* Ask your organization administrators for your Zulip URL.

### I signed up with Google/GitHub auth and never set a password

If you signed up using passwordless authentication and want to start logging
in via email/password, you can
[reset your password](/help/change-your-password).

### I forgot my password

You can [reset your password](/help/change-your-password). This requires
access to the email address you currently have on file. We recommend
[keeping your email address up to date](change-your-email-address).

## Related articles

* [Logging out](logging-out)
* [Switching between organizations](switching-between-organizations)
* [Deactivate your account](deactivate-your-account)
