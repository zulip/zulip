# Logging in

By default, Zulip allows logging in via email/password as well as
various social authentication providers like Google, GitHub, GitLab,
and Apple.

Organization administrators can
[add other authentication methods](/help/configure-authentication-methods),
including the SAML and LDAP integrations, or disable any of the methods above.

You can log in with any method allowed by your organization, regardless of
how you signed up. For example, if you originally signed up using your Google
account, you can later log in using GitHub, as long as your Google account
and GitHub account use the same email address.

## Find the Zulip log in URL

Here are some ways to find the URL for your Zulip organization.

{start_tabs}

{tab|logged-out}

* If your organization is hosted on [Zulip Cloud](https://zulip.com/plans/)
  (usually at `*.zulipchat.com`), go to the [**Find your
  accounts**](https://zulip.com/accounts/find/) page and enter the email address
  that you signed up with. You will receive an email with the sign-in
  information for any Zulip organizations associated with your email address.

* Search your email account for a registration email from Zulip. The subject
  line will include `Zulip: Your new account details` or `Zulip: Your new
  organization details`. This email provides your organization's log in URL.

* If you have visited your organization's log in page in the past, try reviewing
  your browser's history. Searching for `zulipchat.com` should find the right
  page if your Zulip organization is hosted on [Zulip
  Cloud](https://zulip.com/plans/).

* You can ask your organization administrators for your Zulip URL.

{tab|logged-in}

* If using Zulip in the browser, your organization's Zulip log in URL is the first part
  of what you see in the URL bar (e.g., `<organization-name>.zulipchat.com` for
  [Zulip Cloud](https://zulip.com/plans/) organizations).

* In the Desktop app, select **Copy Zulip URL** from the **Zulip** menu to
  copy the URL of the currently active organization. You can also access the
  **Copy Zulip URL** option by right-clicking on an organization logo in the
  **organizations sidebar** on the left.

* In the Mobile app, tap your **profile picture** in the bottom right corner of
  the app, then tap **switch account** to see the URLs for all the organizations
  you are logged in to.

* On [Zulip Cloud](https://zulip.com/plans/) and other Zulip servers updated to
  [Zulip 6.0 or
  higher](https://zulip.readthedocs.io/en/stable/overview/changelog.html#zulip-6-x-series),
  click the **gear** (<i class="zulip-icon zulip-icon-gear"></i>) icon in the upper right
  corner of the web or desktop app. Your organization's log in URL is shown in the top
  section of the menu.

{end_tabs}

## Log in for the first time

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

## Switch between organizations

{!switching-between-organizations.md!}

## Set or reset your password

If you signed up using passwordless authentication and want to start logging in
via email/password, you will need to create a password by following the instructions below. You can also reset a
forgotten password.

{!change-password-via-email-confirmation.md!}

## Related articles

* [Logging out](logging-out)
* [Switching between organizations](switching-between-organizations)
* [Change your email address](change-your-email-address)
* [Change your password](change-your-password)
* [Deactivate your account](deactivate-your-account)
