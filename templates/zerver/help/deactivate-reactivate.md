# Deactivate or reactivate a user

Zulip realm administrators have the ability to deactivate or reactivate any
user's account in their realm.

## Deactivate a user

To properly remove a user’s access to a Zulip orgnanization, it does not
suffice to change their password or deactivate their account in the SSO system,
since neither of those actions prevents authentication with the user’s API key
or any API keys of the bots the user has created.

Instead, you should deactivate the user’s account using the Zulip administration
interface; this will also automatically deactivate any bots the user has
created.

1. Click the cog (![cog](/static/images/help/cog.png)) in the upper right corner
of the right sidebar.

2. Select **Administration** from the dropdown menu that appears.

    ![Administration dropdown](/static/images/help/administration.png)

3. Upon clicking **Administration**, your view will be replaced with the
**Administration** page. Click the **Users** tab at the top of the
panel; it turns gray upon hover.

    ![Administration](/static/images/help/admin-panel-users.png)

4. In the **Users** section, click the red **Deactivate** button
to the right of the user account that you want to deactivate.

    ![Deactivated Users](/static/images/help/deactivate-panel-admin.png)

4. After clicking the **Deactivate Account** button, a modal window titled
**Deactivate (user's email address)** will appear.

    ![Deactivate your account modal](/static/images/help/deactivate-modal-admin.png)

5. To confirm the deletion of the user's account, click the red **Deactivate now**
button. Please note that any bots that the user maintains will be
disabled.

6. After clicking the **Deactivate now** button, the button will transform into
a orange **Reactivate** button, and the **Make admin** button will also
disappear, confirming the success of the account's deactivation.

    The user will be logged out immediately and returned to the Zulip login page
    and will not be able to log back in.

## Reactivate a user

Zulip realm administrators can choose to reactivate a user's deactivated account
by following the following steps.

1. Click the cog (![cog](/static/images/help/cog.png)) in the upper right corner
of the right sidebar.

2. Select **Administration** from the dropdown menu that appears.

    ![Administration dropdown](/static/images/help/administration.png)

3. Upon clicking **Administration**, your view will be replaced with the
**Administration** page. Click the **Deactivated Users** tab at the top of the
panel; it turns gray upon hover.

    ![Administration](/static/images/help/admin-panel.png)

4. In the **Deactivated users** section, click the orange **Reactivate** button
to the right of the user account that you want to reactivate.

    ![Deactivated Users](/static/images/help/deactivate-panel.png)

5. After clicking the **Reactivate** button, the button will transform into a
red **Deactivate** button, confirming the success of the account's reactivation.

    ![Reactivate success](/static/images/help/reactivate-success.png)
