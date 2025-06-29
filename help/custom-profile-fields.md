# Custom profile fields

{!admin-only.md!}

[User cards](/help/user-cards) show basic information about a user, and [user
profiles](/help/view-someones-profile) provide additional details. You can add
custom profile fields to user cards and user profiles, making it easy for users
to share information, such as their pronouns, job title, or team.

Zulip supports many types of profile fields, such as dates, lists of options,
GitHub account links, and [more](#profile-field-types). You can choose which
custom profile fields to [display](#display-custom-fields-on-user-card) on user
cards. Custom profile fields can be optional or
[required](#make-a-custom-profile-field-required).

Zulip supports synchronizing custom profile fields from an external
user database such as LDAP or SAML. See the [authentication
methods][authentication-production] documentation for details.

## Add a custom profile field

{start_tabs}

{settings_tab|profile-field-settings}

1. Click **Add a new profile field**.

1. Fill out profile field information as desired, and click **Add**.

1. In the **Labels** column, click and drag the vertical dots to reorder the
   list of custom profile fields.

{end_tabs}

## Edit a custom profile field

{start_tabs}

{settings_tab|profile-field-settings}

1. In the **Actions** column, click the **edit** (<i class="zulip-icon zulip-icon-edit"></i>)
   icon for the profile field you want to edit.

1. Edit profile field information as desired, and click **Save changes**.

{end_tabs}

## Display custom fields on user card

Organizations may find it useful to display additional fields on the
user card, such as pronouns, GitHub username, job title, team, etc.

All field types other than "Long text" or "Person" have a checkbox option
that controls whether to display a custom field on the user card.
There's a limit to the number of custom profile fields that can be displayed
at a time. If the maximum number of fields is already selected, all unselected
checkboxes will be disabled.

{start_tabs}

{settings_tab|profile-field-settings}

1. In the **Actions** column, click the **edit** (<i class="zulip-icon zulip-icon-edit"></i>)
   icon for the profile field you want to edit.

1. Toggle **Display on user card**.

1. Click **Save changes**.

!!! tip ""

    You can also choose which custom profile fields will be displayed by toggling
    the checkboxes in the **Card** column of the **Custom profile fields** table.

{end_tabs}

## Make a custom profile field required

If a custom profile field is required, users who have left it blank will see a
banner every time they open the Zulip web or desktop app prompting them to fill
it out.

{start_tabs}

{settings_tab|profile-field-settings}

1. In the **Actions** column, click the **edit** (<i class="zulip-icon zulip-icon-edit"></i>)
   icon for the profile field you want to edit.

1. Toggle **Required field**.

1. Click **Save changes**.

!!! tip ""

    You can also choose which custom profile fields are required by toggling the
    checkboxes in the **Required** column of the **Custom profile fields** table.

{end_tabs}

## Configure whether users can edit custom profile fields

{!admin-only.md!}

You can configure whether users in your organization can edit custom profile
fields for their own account. For example, you may want to restrict editing if
syncing profile fields from an employee directory.

{start_tabs}

{settings_tab|profile-field-settings}

1. In the **Actions** column, click the **edit** (<i class="zulip-icon zulip-icon-edit"></i>)
   icon for the profile field you want to configure.

1. Toggle **Users can edit this field for their own account**.

1. Click **Save changes**.

{end_tabs}

## Profile field types

Choose the profile field type that's most appropriate for the requested information.

* **Date**: For dates (e.g., birthdays or work anniversaries).
* **Link**: For links to websites, including company-internal pages.
* **External account**: For linking to an account on GitHub, X (Twitter), etc.
* **List of options**: A dropdown with a list of predefined options (e.g.,
  office location).
* **Pronouns**: What pronouns should people use to refer to the user? Pronouns
  are displayed in [user mention](/help/mention-a-user-or-group) autocomplete
  suggestions.
* **Text (long)**: For multiline responses (e.g., a user's intro message).
* **Text (short)**: For one-line responses up to 50 characters (e.g., team
  name or role in your organization).
* **Users**: For selecting one or more users (e.g., manager or direct reports).

## Related articles

* [Edit your profile](/help/edit-your-profile)
* [User cards](/help/user-cards)
* [View someone's profile](/help/view-someones-profile)

[authentication-production]: https://zulip.readthedocs.io/en/stable/production/authentication-methods.html
