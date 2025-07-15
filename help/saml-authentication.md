# SAML authentication

{!admin-only.md!}

Zulip supports using SAML authentication for single sign-on, both for Zulip
Cloud and self-hosted Zulip servers. SAML Single Logout is also supported.

This page describes how to configure SAML authentication with several common providers:

* Okta
* OneLogin
* Entra ID (AzureAD)
* Keycloak
* Auth0

Other SAML providers are supported as well.

If you are [self-hosting](/self-hosting/) Zulip, please follow the detailed setup instructions in
the [SAML configuration for self-hosting][saml-readthedocs]. The documentation
on this page may be a useful reference for how to set up specific SAML
providers.

{!cloud-plus-only.md!}

## Configure SAML

{start_tabs}

{tab|okta}

{!upgrade-to-plus-if-needed.md!}

1. Set up SAML authentication by following
   [Okta's documentation](https://developer.okta.com/docs/guides/saml-application-setup/overview/).
   Specify the following fields, skipping **Default RelayState** and **Name ID format**:
     * **Single sign on URL**: `https://auth.zulipchat.com/complete/saml/`
     * **Audience URI (SP Entity ID)**: `https://zulipchat.com`
     * **Application username format**: `Email`
     * **Attribute statements**:
         * `email` to `user.email`
         * `first_name` to `user.firstName`
         * `last_name` to `user.lastName`

1. Assign the appropriate accounts in the **Assignments** tab. These are the users
   that will be able to log in to your Zulip organization.

1. {!send-us-info.md!}

     1. Your organization's URL
     1. The **Identity Provider metadata** provided by Okta for the application.
        To get the data, click the **View SAML setup instructions button** in
        the right sidebar in the **Sign on** tab.
        Copy the IdP metadata shown at the bottom of the page.
     {!saml-login-button.md!}

{tab|onelogin}

{!upgrade-to-plus-if-needed.md!}

1. Navigate to the OneLogin **Applications** page, and click **Add App**.

1. Search for the **SAML Custom Connector (Advanced)** app and select it.

1. Set a name and logo and click **Save**. This doesn't affect anything in Zulip,
   but will be shown on your OneLogin **Applications** page.

1. In the **Configuration** section, specify the following fields. Leave the
   remaining fields as they are, including blank fields.

    * **Audience**: `https://zulipchat.com`
    * **Recipient**: `https://auth.zulipchat.com/complete/saml/`
    * **ACS URL**: `https://auth.zulipchat.com/complete/saml/`
    * **ACS URL Validator**: `https://auth.zulipchat.com/complete/saml/`

1. In the **Parameters** section, add the following custom parameters. Set the
   **Include in SAML assertion** flag on each parameter.

      | Field name | Value
      |---         |---
      | email      | Email
      | first_name | First Name
      | last_name  | Last Name
      | username   | Email

1. {!send-us-info.md!}

     1. Your organization's URL
     1. The **issuer URL** from the **SSO** section. It contains required **Identity Provider** metadata.
     {!saml-login-button.md!}

{tab|azuread}

{!upgrade-to-plus-if-needed.md!}

1. From your Entra ID Dashboard, navigate to **Enterprise applications**,
   click **New application**, followed by **Create your own application**.

1. Enter a name (e.g., `Zulip Cloud`) for the new Entra ID application,
   choose **Integrate any other application you don't find in the
   gallery (Non-gallery)**, and click **Create**.

1. From your new Entra ID application's **Overview** page that opens, go to
   **Single sign-on**, and select **SAML**.

1.  In the **Basic SAML Configuration** section, specify the following fields:

    * **Identifier (Entity ID)**: `https://zulipchat.com`
    * **Default**: *checked* (This is required for enabling IdP-initiated sign on.)
    * **Reply URL (Assertion Consumer Service URL)**: `https://auth.zulipchat.com/complete/saml/`

1. If you want to set up IdP-initiated sign on, in the **Basic SAML
   Configuration** section, also specify:

     * **RelayState**: `{"subdomain": "<your organization's zulipchat.com subdomain>"}`

1. Check the **User Attributes & Claims** configuration, which should already be
   set to the following. If the configuration is different, please
   indicate this when contacting [support@zulip.com](mailto:support@zulip.com)
   (see next step).

      * **givenname**: `user.givenname`
      * **surname**: `user.surname`
      * **emailaddress**: `user.mail`
      * **name**: `user.principalname`
      * **Unique User Identifier**: `user.principalname`

1. {!send-us-info.md!}

     1. Your organization's URL
     1. From the **SAML Signing Certificate** section:
        * **App Federation Metadata Url**
        * Certificate downloaded from **Certificate (Base64)**
     1. From the **Set up** section
        * **Login URL**
        * **Microsoft Entra Identifier**
     {!saml-login-button.md!}

{tab|keycloak}

{!upgrade-to-plus-if-needed.md!}

1. Make sure your Keycloak server is up and running.

1. In Keycloak, register a new Client for your Zulip organization:
    * **Client-ID**: `https://zulipchat.com`
    * **Client Protocol**: `saml`
    * **Client SAML Endpoint**: *(empty)*

1. In the **Settings** tab for your new Keycloak client, set the following properties:
    * **Valid Redirect URIs**: `https://auth.zulipchat.com/*`
    * **Base URL**: `https://auth.zulipchat.com/complete/saml/`
    * **Client Signature Required**: `Disable`

1. In the **Mappers** tab for your new Keycloak client:
    * Create a Mapper for the first name:
        * **Property**: `firstName`
        * **Friendly Name**: `first_name`
        * **SAML Attribute Name**: `first_name`
        * **SAML Attribute Name Format**: `Basic`
    * Create a Mapper for the last name:
        * **Property**: `lastName`
        * **Friendly Name**: `last_name`
        * **SAML Attribute Name**: `last_name`
        * **SAML Attribute Name Format**: `Basic`
    * Create a Mapper for the email address:
        * **Property**: `email`
        * **Friendly Name**: `email`
        * **SAML Attribute Name**: `email`
        * **SAML Attribute Name Format**: `Basic`

1. {!send-us-info.md!}

     1. Your organization's URL
     1. The URL of your Keycloak realm.
     {!saml-login-button.md!}

!!! tip ""

    Your Keycloak realm URL will look something like this: `https://keycloak.example.com/auth/realms/yourrealm`.

{tab|auth0}

{!upgrade-to-plus-if-needed.md!}

1. Set up SAML authentication by following [Auth0's documentation](https://auth0.com/docs/authenticate/protocols/saml/saml-sso-integrations/configure-auth0-saml-identity-provider#configure-saml-sso-in-auth0)
   to create a new application. You don't need to save the certificates or other information detailed.
   All you will need is the **SAML Metadata URL**.
1. In the **Addon: SAML2 Web App** **Settings** tab, set the **Application Callback URL** to
   `https://auth.zulipchat.com/complete/saml/`.
1. Edit the **Settings** section to match:

    ```
    {
      "audience": "https://zulipchat.com",
      "mappings": {
        "email": "email",
        "given_name": "first_name",
        "family_name": "last_name"
      },
      "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
    }
    ```

1. {!send-us-info.md!}

     1. Your organization's URL
     1. The **SAML Metadata URL** value mentioned above. It contains required **Identity Provider** metadata.
     {!saml-login-button.md!}

{end_tabs}

!!! tip ""

    Once SAML has been configured, consider also [configuring SCIM](/help/scim).

## Synchronizing group membership with SAML

You can configure each Zulip user's [groups](/help/user-groups) to be updated based
on their groups in your Identity Provider's (IdP's) directory every time they
log in.

Your IdP directory's group names don't have to match the associated Zulip group
names (e.g., membership in your IdP's group **finance** can be synced to
membership in the Zulip group **finance-department**). See the [technical
documentation][saml-group-sync-readthedocs] on how your IdP's groups are mapped
to Zulip groups for details.

!!! tip ""

    It should be possible to set this up with any provider. If you're interested
    in using this functionality with a provider other than Okta, reach out to
    [support@zulip.com](mailto:support@zulip.com).

{start_tabs}

{tab|okta}

1. Follow the instructions [above](#configure-saml) to configure SAML, and go to
   the application you created for using SAML with Zulip in your
   **Applications** menu.

1. Select the **General** tab, and **Edit** the **SAML Settings** section.

1. Proceed through the prompts until the main **Configure SAML** prompt.

1. Scroll down below the **Attribute Statements** section (which you configured
   when creating the app) to **Group Attribute Statements**.

1. Add the following attribute:
     * **Name**: `zulip_groups`
     * **Name format**: `Unspecified`
     * **Filter**: `Matches regex: .*`

     When a user signs in to Zulip via SAML, Okta will now include a list of the
     user's groups in its response to the Zulip server.

1. To enable this feature, please email
   [support@zulip.com](mailto:support@zulip.com) with the following information:
     * Your Zulip organization URL.
     * Which groups should be synced from your IdP's directory.
     * Which groups should have a different name in Zulip (if any).

{end_tabs}

## Related articles

* [SAML configuration for self-hosting][saml-readthedocs]
* [SCIM provisioning](/help/scim)
* [Moving to Zulip](/help/moving-to-zulip)

[saml-readthedocs]: https://zulip.readthedocs.io/en/stable/production/authentication-methods.html#saml
[saml-group-sync-readthedocs]: https://zulip.readthedocs.io/en/latest/production/authentication-methods.html#synchronizing-group-membership-with-saml
