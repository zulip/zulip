# SAML Authentication

Zulip supports using SAML authentication for Single Sign On, both when
self-hosting or on the Zulip Cloud Plus plan.

This page documents details on how to setup SAML authentication with
Zulip with various common SAML Identity Providers.

## Configure SAML with Okta

1. Make sure you have created your organization. We'll assume its URL is
   `https://<subdomain>.zulipchat.com` in the instructions below.
1. Set up SAML authentication by following
   [Okta's documentation](https://developer.okta.com/docs/guides/saml-application-setup/overview/).
   Specify:
     * `https://<subdomain>.zulipchat.com/complete/saml/` for the "Single sign on URL"`.
     * `https://zulipchat.com` for the "Audience URI (SP Entity ID)".
     * Skip "Default RelayState".
     * Skip "Name ID format".
     * Set 'Email` for "Application username format".
     * Provide "Attribute statements" of `email` to `user.email`,
       `first_name` to `user.firstName`, and `last_name` to `user.lastName`.
1. Assign the appropriate accounts in the "Assignments" tab. These are the users
   that will be able to log in to your Zulip organization.
1. Send the following information to us at support@zulip.com:
     * The URL of your zulipchat-hosted organization.
     * The "Identity Provider metadata" provided by Okta for the application.
     * The name "X" that will be displayed on the "Log in with X" button in Zulip.
     * Optionally you can also send us an icon that should be shown on the button.
1. We will take care of the server-side setup and let you know as soon as it's ready.

## Configure SAML with Onelogin

1. Make sure you have created your organization. We'll assume its URL is
   `https://<subdomain>.zulipchat.com` in the instructions below.
1. Navigate to the Onelogin Applications page, and click "Add App".
1. Search for the "OneLogin SAML Test (IdP)" app and select it.
1. Set a name and logo according to your preferences and click "Save". This doesn't affect anything in Zulip,
   but will be shown on your OneLogin Applications page.
1. Go to the "Configuration" section:
    * Set `https://<subdomain>.zulipchat.com/complete/saml/` as the SAML Consumer URL, SAML Recipient
      and ACS URL Validator.
    * Set `https://zulipchat.com` as the SAML Audience.
1. Go to the "Parameters" section and configure it to match the following screenshot:

    ![](/static/images/help/onelogin_parameters.png)

    Make sure to set the "Include in SAML assertion" flag on these parameters.

1. The OneLogin side of configuration should be ready!
   Send the following information to us at support@zulip.com:
     * The URL of your zulipchat-hosted organization.
     * The issuer URL from the "SSO" section. It contains Identity Provider metadata that we will need.
     * The name "X" that will be displayed on the "Log in with X" button in Zulip.
     * Optionally you can also send us an icon that should be shown on the button.
1. We will take care of the server-side setup and let you know as soon as it's ready.

## Related Articles

* [SAML configuration][saml-readthedocs] for self-hosting.

[saml-readthedocs]: https://zulip.readthedocs.io/en/stable/production/authentication-methods.html#saml
