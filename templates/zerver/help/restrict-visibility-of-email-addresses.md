# Restrict visibility of email addresses

{!admin-only.md!}

By default, any user can find and view the email address of any other
user.  Organization administrators can restrict access so that only
admins (or nobody) can view other users' email addresses.

### Restrict visibility of email addresses

{start_tabs}

{settings_tab|organization-permissions}

2. Under **User identity**, configure **Who can access user email addresses**.

{!save-changes.md!}

{end_tabs}

## Caveats

There are a few places in the app where Zulip shows fake email addresses (like
`Ada Starr <user1234@example.zulipchat.com>`) rather than just `Ada Starr`. This might
cause some confusion for users. The fake email addresses do not work, and
email sent to those addresses will bounce.

## Related articles

* [Moderating open organizations](/help/moderating-open-organizations)
