# SCIM provisioning

{!admin-only.md!}

SCIM (System for Cross-domain Identity Management) is a standard
protocol used by Single Sign-On (SSO) services and identity providers
to provision/deprovision user accounts and groups. Zulip supports SCIM
integration, both in Zulip Cloud and for [self-hosted](/self-hosting/)
Zulip servers.  This page describes how to configure SCIM provisioning
for Zulip.

Zulip's SCIM integration has the following limitations:

* Provisioning Groups is not yet implemented.
* While Zulip's SCIM integration is generic, it has has only been
  fully tested and documented with Okta's SCIM provider, and it is
  possible minor adjustments may be required. [Zulip
  support](/help/contact-support) is happy to help customers configure
  this integration with SCIM providers that do not yet have detailed
  self-service documentation on this page.

!!! warn ""
    Zulip Cloud customers who wish to use SCIM integration must upgrade to
    the Zulip Cloud Plus plan. Contact
    [support@zulip.com](mailto:support@zulip.com) for plan benefits and pricing.

## Configure SCIM

{start_tabs}

{tab|okta}

{!upgrade-to-plus-if-needed.md!}

1.  Contact [support@zulip.com](mailto:support@zulip.com) to request the
    **Bearer token** that Okta will use to authenticate to your SCIM API.

1. In your Okta Dashboard, go to **Applications**, and select
   **Browse App Catalog**.

1. Search for **SCIM** and select **SCIM 2.0 Test App (Header Auth)**.

1. Click **Add** and choose your **Application label**. For example, you can
   name it "Zulip SCIM".

1. Continue to **Sign-On Options**. Leave the **SAML** options as they are.
   This type of Okta application doesn't actually support SAML authentication,
   and you'll need to set up a separate Okta app to activate SAML for your Zulip
   organization.

1. In **Credentials Details**, specify the following fields:
     * **Application username format**: `Email`
     * **Update application username on**: `Create and update`

1. In the **Provisioning** tab, click **Configure API Integration**, check the
   **Enable API integration** checkbox, and specify the following fields:
     * **Base URL**: `yourorganization.zulipchat.com/scim/v2`
     * **API token**: `Bearer token` (given to you by Zulip support)

    When you proceed to the next step, Okta will verify that these details are
    correct by making a SCIM request to the Zulip server.

1. Enable the following **Provisioning to App** settings:
     * **Create Users**
     * **Update User Attributes**
     * **Deactivate Users**

1. Remove all attributes in **Attribute Mappings**, _except_ for the following:
     * **userName**
     * **givenName**
     * **familyName**

1. **Optional:** If you'd like to also sync [user role](/help/roles-and-permissions),
   you can do it by by adding a custom attribute in Okta. Go to the **Profile Editor**,
   click into the entry of the SCIM app you've just set up and **Add Attribute**.
   Configure the following:
    * **Data type**: `string`
    * **Variable name**: `role`
    * **External name**: `role`
    * **External namespace**: `urn:ietf:params:scim:schemas:core:2.0:User`

    With the attribute added, you will now be able to set it for your users directly
    or configure an appropriate **Attribute mapping** in the app's **Provisioning**
    section.
    The valid values are: **owner**, **administrator**, **moderator**, **member**, **guest**.

1. Now that the integration is ready to manage Zulip user accounts, **assign**
   users to the SCIM app.
     * When you assign a user, Okta will check if the account exists in your
       Zulip organization. If it doesn't, the account will be created.
     * Changes to the user's email or name in Okta will automatically cause the
       Zulip account to be updated accordingly.
     * Unassigning a user from the app will deactivate their Zulip account.

{end_tabs}

!!! tip ""

    Once SCIM has been configured, consider also [configuring SAML](/help/saml-authentication).

## Related articles

* [SAML authentication](/help/saml-authentication)
* [Getting your organization started with Zulip](/help/getting-your-organization-started-with-zulip)
