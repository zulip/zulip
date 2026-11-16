# Example advisories

Three advisories that show the expected style. The first two are lower severity and
use the standard structure. The third is a more serious issue with a Severity section,
a Workarounds section, and an Impact-first structure.

## Example 1: Data exposure, no workaround (fixed in 12.4)

```markdown
Title: Exports with member consent include direct messages of deleted users' conversations

### Summary

An organization export of public and private data with member consent treated every deleted user as having consented to the export of their private data. As a result, the export included direct messages from conversations that a deleted user had been part of, including messages written by other participants who had not consented. Severity is limited: creating such an export requires administrator permissions, and only conversations involving a deleted user are affected. User deletion isn't available in the Zulip apps: on self-hosted servers, it requires running the `manage.py delete_user` management command, and on Zulip Cloud, it's done by Zulip's support team.

### Details

The "Public and private data (with consent)" export includes the private data of users who have allowed administrators to export it. Since Zulip Server 11.0, it also treats mirror dummy accounts as consenting. Mirror dummies are placeholder accounts that represent users from data imported from other products, such as Slack, and they only contain data that was already accessible to the exporting organization.

When a user is deleted (as opposed to deactivated), their account is turned into a mirror dummy too, so `get_consented_user_ids` (`zerver/lib/export.py`) considered them to be consenting. Deleting a user also disables their export consent setting, but since mirror dummies are considered consenting regardless of that setting, this had no effect. The deleted account remains a participant in its direct message conversations, so the export included those conversations, along with messages from the other participants.

### Impact

An organization administrator could obtain, through an export with member consent, direct messages in conversations that a deleted user had been part of. This includes messages sent in such conversations by other participants who had not allowed administrators to export their private data, as well as any remaining messages of the deleted user, whose consent setting was disabled when they were deleted.

This affects Zulip Server 11.0 through 12.3, and only organizations with at least one deleted user.

This is fixed in Zulip Server 12.4.

### References

- [Export your organization](https://zulip.com/help/export-your-organization)
- [Configure whether administrators can export your private data](https://zulip.com/help/export-your-organization#configure-whether-administrators-can-export-your-private-data)
```

Notes: there was no real workaround, so Workarounds was left out. ("Use the public
data export instead" was rejected because it just means not using the feature.)
Sentences about a migration for users deleted before 12.0 and about existing exports
were cut as noise.

## Example 2: Authentication bypass with a workaround

```markdown
Title: Sign-up via reusable invitation links skips single sign-on

### Summary

In Zulip organizations where only external authentication methods are enabled (e.g., SAML, OpenID Connect or Google), anyone with a reusable invitation link could create an account without using any of those methods. They only needed to control an email address the organization allows. Severity is low: it requires a valid reusable invitation link, which only administrators can create by default.

### Details

A reusable invitation link's sign-up page doesn't show the email form when no password-based authentication method (email or LDAP) is enabled. However, the server still accepted an email address submitted to the link (`/join/<key>/`). It sent a confirmation email to that address, and following the confirmation link created the account and logged the user in.

The check that rejects email-based sign-up in such organizations, added for CVE-2025-31478 in `HomepageForm.clean_email` (`zerver/forms.py`), was skipped for requests coming from reusable invitation links (`from_multiuse_invite`).

### Impact

This lets someone skip the organization's single sign-on requirement. It affects organizations that:
- have no password-based authentication method enabled; and
- have at least one active reusable invitation link.

The person must possess the link and control the email address used. The resulting account has the role and channel subscriptions specified by the link. Restricting sign-up to specific email domains limits which addresses can be used. Revoking reusable invitation links fully mitigates the issue until upgrading.

This is fixed in Zulip Server 12.4.
```

Notes: the workaround (revoking reusable invitation links) fully neutralizes the bug,
so it's stated in Impact.

## Example 3: Critical impersonation issue (fixed in 12.3)

```markdown
Title: Organization members could forge the sender of a group direct message

### Impact

In an affected organization, any member could send a group direct message that appears to have been sent by a different user. The fabricated message would be stored and delivered as a normal direct message, displayed under the impersonated person's name with no indication to recipients that it did not come from them. The same flaw let a member bypass restrictions on who is permitted to send or initiate direct messages, by attributing the message to a user who is allowed to.

This was only possible through the API, by forging a specific client identifier, and not through Zulip's web, desktop, or mobile apps.

This required a specific configuration of settings in order to be exploitable:
- The organization must restrict account creation to a list of domains
- The impersonated user's email visibility must generally be set to permit everyone to see the email address. On installations where the organization's own hostname is one of the restricted email domains, this condition does not apply and any user may be impersonated.

Additionally the forged message was restricted by the following conditions:
- The impersonated sender account's email address must be within the aforementioned email domains
- The message must be a direct message whose conversation includes the attacker's account. A 1-1 direct message is technically possible - the attacker Bob can forge a message from Charlie into their own 1-1 thread with Charlie - but this is of little use, since the only viewer who isn't the attacker is Charlie. The meaningful case is a group direct message with at least one other recipient. For example, Bob can forge a message appearing as if sent by Charlie, but only into a group containing `{Alice, Bob, Charlie}` (or a superset) - never a conversation Bob is not part of.

This is an integrity issue only - it does not grant the attacker access to any private messages, channels, or other data they could not already see.

### Severity

CVSS 6.5 (Medium); note that CVSS does not capture the impersonation and non-repudiation aspects, which we consider the more serious real-world impact.

### Workarounds

A possible mitigation is to explicitly remove the email domains configured for the aforementioned sign-up restriction. The vulnerable mirroring API only accepts a forged sender whose email domain is one of those configured, so with none configured it cannot be used. Note that simply disabling the sign-up restriction by itself is not enough: the configured domains remain in place. Removing the last domain turns the restriction off automatically. To compensate, organizations can [require an invitation to join](https://zulip.com/help/restrict-account-creation#set-whether-invitations-are-required-to-join) and use [email invitations](https://zulip.com/help/invite-new-users#send-email-invitations) to control which email addresses users can register with.

### References

- [Restricting account creation to specific email domains](https://zulip.com/help/restrict-account-creation#configuring-email-domain-restrictions)
- [Configuring email address visibility](https://zulip.com/help/configure-email-visibility)
- [Restricting direct messages](https://zulip.com/help/restrict-direct-messages)
```

Notes: for a high-impact issue, the exploitability conditions are listed in detail,
and so is what the attacker can't do. The workaround explains exactly which setting
change neutralizes the bug and how to compensate for losing it.
