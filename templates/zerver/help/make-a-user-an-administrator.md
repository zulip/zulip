# Make a user an administrator

> With great power comes great responsibility.

By default, everyone in a realm is a user; this limits them from modifying
realm-wide settings, such as changing the organization name, activating or
deactivating users, deleting streams, etc. Zulip realm administrators can
give a user administrative rights. To do so, follow the steps below:

1. Click the (![cog](/static/images/help/cog.png)) in the upper right corner
of the right sidebar.

2. Select **Administration** from the dropdown menu.

    ![admin](/static/images/help/admin.png)

3. Upon clicking **Administration**, your view will be replaced with the
**Administration** page. Click on **Users** in the tabs list.

    ![admin panel](/static/images/help/admin-panel-generic.png)

4. In the **Users** section, you will be presented with various settings
for your users. Click on **Make admin** for the user(s) that you wish to
make an administrator.

    ![make admin](/static/images/help/make-admin.png)

After clicking the **Make admin** button, the selected user's browser will
reload and the user will gain administrative privileges immediately.

## Revoke administrative rights from a user

Administrators can also revoke the administrative rights given to a user.
In the **Users** tab of the **Administration** page, click on the **Remove
admin** button.

  ![remove admin](/static/images/help/remove-admin.png)

The selected user's browser will reload automatically, and the user will no
longer have access to the administration page.

#### Note:
* A user given administrative privileges can revoke it him/herself.
* There must be at least one administrator in a realm.
