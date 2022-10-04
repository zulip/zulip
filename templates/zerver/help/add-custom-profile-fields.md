# Add custom profile fields

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

## Related articles

* [Edit your profile](/help/edit-your-profile)
* [View someone's profile](/help/view-someones-profile)

[authentication-production]: https://zulip.readthedocs.io/en/latest/production/authentication-methods.html
