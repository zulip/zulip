# SCIM provisioning

SCIM (System for Cross-domain Identity Management) is an standard
protocol used by Single Sign-On (SSO) services and identity providers
to provision/deprovision user accounts and groups. Zulip's SCIM
integration is currently beta and has a few limitations:

* Provisioning Groups is not yet implemented.
* It has only been fully tested and documented with Okta.

The instructions below explain how to configure SCIM in Okta for Zulip
Cloud customers. Like SAML, feature is currently only available in
Zulip Cloud with the Zulip Cloud Plus plan.

These instructions can also be used by self-hosters to setup the Okta
side of SCIM for their deployment.

## Configure SCIM with Okta

1. Before you begin, contact [email support](mailto:support@zulip.com) to receive
   the bearer token that Okta will use to authenticate to make its SCIM requests.
1. In your Okta Dashboard, go to `Applications` and choose `Browse App Catalog`.
1. Search for `SCIM` and select `SCIM 2.0 Test App (Header Auth)`.
1. Click `Add` and choose your `Application label`. For example, you can name it `Zulip SCIM`.
1. Continue to `Sign-On Options`. Leave the `SAML` options, as this type of Okta application
   doesn't actually support `SAML` authentication, and you'll need to set up a separate Okta app
   to activate `SAML` for your Zulip organization.
1. In `Credentials Details`, set `Application username format` to `Email` and
    `Update application username on` to `Create and update`.
1. The Okta app has been added. Navigate to the `Provisioning` tab.
1. Click `Configure API Integration` and check the `Enable API integration` box.
   Okta will ask you for the `Base URL` and `API token`. The `Base URL` should be
   `yourorganization.zulipchat.com/scim/v2` and for `API token` you'll set the value
   given to you by support. When you proceed to the next step, Okta will verify that
   these details are correct by making a SCIM request to the Zulip server.
1. In the `To App` section of the `Provisioning` tab (which should be opened by default
   when you continue from the previous step), edit the `Provisioning to App` settings
   to enable `Create Users`, `Update User Attributes` and `Deactivate Users`.
1. In `Attribute Mappings`, remove all attributes except `userName`, `givenName`
   and `familyName`.
1. Now the integration should be ready and you can `Assign` users to
   the app to configure their Zulip accounts to be managed by
   SCIM. When you assign a user, Okta will check if the account exists
   in your Zulip organization and if it doesn't, the account will be
   created. Changes to the user's email or name in Okta will
   automatically cause the Zulip account to be updated accordingly.
   Unassigning a user from the app will deactivate their Zulip
   account.

If you want to also set up SAML authentication, head to our
[SAML configuration instructions](/help/saml-authentication). It will require
adding a separate Okta application.
