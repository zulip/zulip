# Add custom profile fields

{!admin-only.md!}

By default, user profiles show their name, email, date they joined, and when
they were last active. You can also add custom profile fields like country
of residence, birthday, manager, Twitter handle, and more.

Custom profile fields are always optional, and do not appear in users'
profiles until they fill them out.

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

## Profile field types

There are several different types of fields available.

* **Short text**: For one line responses, like
    "Job title". Responses are limited to 50 characters.
* **Long text**: For multiline responses, like "Biography".
* **Date picker**: For dates, like "Birthday".
* **Link**: For links to websites.
* **External account**: For linking to GitHub, Twitter, etc.
* **List of options**: Creates a dropdown with a list of options.
* **Person picker**: For selecting other users, like "Manager" or
    "Direct reports".

## Display custom fields in user profile summaries

Organizations may find it useful to display additional fields in a user's
profile summary, such as pronouns, GitHub username, job title, team, etc.

All field types other than "Long text" or "Person" have a checkbox option
that controls whether to display a custom field in a user's profile summary.
There's a limit to the number of custom profile fields that can be displayed
at a time. If the maximum number of fields is already selected, all unselected
checkboxes will be disabled.

{start_tabs}

{settings_tab|profile-field-settings}

1. Click the **pencil** (<i class="fa fa-pencil"></i>) icon on the profile field
   you want to edit.

1. Toggle **Display in profile summary**.

4. Click **Save changes**.

!!! tip ""

    You can also choose which custom profile fields will be displayed by toggling
    the checkboxes in the **Summary** column of the **Custom profile fields** table.

{end_tabs}

## Related articles

* [Edit your profile](/help/edit-your-profile)
* [View someone's profile](/help/view-someones-profile)

[authentication-production]: https://zulip.readthedocs.io/en/latest/production/authentication-methods.html
