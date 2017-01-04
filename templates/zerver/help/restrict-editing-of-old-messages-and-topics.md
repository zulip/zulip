# Restrict editing of old messages and topics

If you are an administrator of a Zulip organization, you can easily change the
time limit that your realm's users have to change their messages after sending
them. Alternatively, you can choose to disable message editing for your realm
users.

{!go-to-the.md!} [Organization Settings](/#administration/organization-settings)
{!admin.md!}

4. Locate the **Users can edit old messages**
checkbox and **Message edit limit in minutes (0 for no limit)** input field
underneath it.

    By default, user message editing is enabled for 10 minutes after sending.

    * **Users can edit old messages** - Uncheck this option if you wish to
    disable message editing. Upon doing so, the **Message edit limit in minutes (0 for no limit)**
    input field will be grayed out.

    * **Message edit limit in minutes (0 for no limit)** - If you enable message
    editing in your realm, you can restrict the time that realm users have to
    edit their messages. Simply input the time limit in minutes that you would
    like to set; for example, if you want to set a message edit time limit of 5
    minutes, enter **5** in the field.

        If you would like to disable the message editing time limit for your realm,
enter **0** in the field. This enables users to edit their messages whenever
they want.

5. To save any changes you have made to your organization settings, click the
**Save changes** button at the bottom of the **Organizations settings**
section.
