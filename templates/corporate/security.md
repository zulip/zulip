We take the trust our users put in Zulip extremely seriously. Our security model
is designed to be:

- **Secure by default**: Your data is protected out-of-the-box.
- **Well-documented** and **easy to understand**, so that you’re never caught by
  surprise.
- **Flexible**, so that you can configure Zulip according to your organization’s
  needs.

This page will walk you Zulip's security tools and practices:

- [Compliance support](#zulip-serves-your-compliance-needs)
- [Data encryption](#data-is-encrypted-for-your-protection)
- [Tools to protect your data when you self-host](#self-hosting-we-give-you-the-tools-to-protect-your-data)
- [How we keep your organization secure on Zulip Cloud](#zulip-cloud-we-keep-your-organization-secure)
- [Zulip's robust 100% open-source system](#robust-100-open-source-system)
- [Highly configurable access controls](#highly-configurable-access-controls)
- [Our responsible vulnerability disclosure program](#responsible-disclosure-program)

---

## Zulip serves your compliance needs

- [GDPR and CCPA compliant](https://zulip.com/help/gdpr-compliance)
- Self-hosting facilitates HIPAA and FERPA compliance
- [Message editing and deletion policies](/help/restrict-message-editing-and-deletion)
- [Global and per-channel data retention policies](/help/message-retention-policy)
- Detailed audit log of administrative actions
- [Complete data exports](/help/export-your-organization)
- [Compliance exports](https://zulip.readthedocs.io/en/stable/production/export-and-import.html#compliance-exports)

---

## Data is encrypted for your protection

### Secure data transmission

All Zulip clients require [TLS
encryption](https://zulip.readthedocs.io/en/stable/production/ssl-certificates.html)
and authentication over HTTPS for data transmission to and from the server, both
on LAN and the Internet.

### End-to-end encryption for push notification content

You can [require end-to-end
encryption](https://zulip.com/help/mobile-notifications#end-to-end-encryption-e2ee-for-mobile-push-notifications)
for message content in mobile push notifications. If you do, content will be
omitted when sending notifications to an app that doesn't support end-to-end
encryption.

### Secure integrations
[Integrations](/integrations/) use TLS encryption and authentication over HTTPS
for data transmission. Administrators can browse,
[manage](https://zulip.com/help/manage-a-bot), and
[deactivate](https://zulip.com/help/deactivate-or-reactivate-a-bot)
integrations.

---

## Self-hosting: We give you the tools to protect your data

### Support for encryption in transit and at rest

Encrypt your database, uploads, and backups at rest on infrastructure you
control. All connections between parts of the Zulip system are secured
out-of-the-box with encryption, a protected network like a local socket, or
both. All of the inter-service connections are also authenticated, to provide a
defensive-by-default security posture, and prevent SSRF attacks.

### Firewalled and air-gapped deployments

Zulip can be hosted entirely behind your firewall, or on an air-gapped network.

### Custom security policies

- [Configurable](https://zulip.readthedocs.io/en/stable/production/authentication-methods.html#email-and-password)
  password strength requirements.
- Administrators can revoke and reset any user’s credentials.
- Configurable [session
  length](https://github.com/zulip/zulip/search?q=SESSION_COOKIE_AGE&type=code)
  and [idle
  timeouts](https://github.com/zulip/zulip/search?q=SESSION_EXPIRE_AT_BROWSER_CLOSE&type=code).
- Configurable log rotation policies.
- [Configurable rate
  limits](https://zulip.readthedocs.io/en/stable/production/securing-your-zulip-server.html#understand-zulip-s-rate-limiting-system)
  for API endpoints and authentication attempts.

---

## Zulip Cloud: We keep your organization secure

- All customer data is encrypted in transit and at rest.
- [Strong
  passwords](https://zulip.readthedocs.io/en/stable/production/password-strength.html)
  are required with the zxcvbn password strength checker.
- Users can [rotate](https://zulip.com/help/protect-your-account) their account
  credentials.
- To protect your privacy, error handling systems exclude user message content
  in reports.
- Data and server access is limited to a very small number of staff.

---

## Robust 100% open-source system

Your security team and independent security researchers have access to [Zulip’s
entire codebase](https://github.com/zulip), and can thus fully audit the system
for security issues. We are proud of our industry-leading efforts to prevent
security issues from being introduced in Zulip.

### Development process

- **Comprehensive automated testing**: The Zulip server has an remarkably
  complete automated test suite, including [complete test
  coverage](https://app.codecov.io/gh/zulip/zulip/tree/main/zerver) in
  security-sensitive code paths.
- **Stable, carefully audited APIs**: All clients share a common, highly stable
  [API](https://zulip.com/api/). API changes are carefully reviewed for security
  and necessity, and documented in a [readable API
  changelog](https://zulip.com/api/changelog).
- **Disciplined code review:** Zulip is known for its unusually disciplined
  [code review
  process](https://zulip.readthedocs.io/en/latest/contributing/review-process.html),
  ensuring that all changes are carefully verified by our maintainer team.

### System design

- **Static typing**: The Zulip server
  [pioneered](https://blog.zulip.org/2016/10/13/static-types-in-python-oh-mypy/)
  statically typed Python. Extensive use of both standard and custom linters
  helps prevent several classes of common security bugs.
- **Access control**: Access to user data (messages, channels, uploaded files,
  etc.) in the Zulip server is mediated through carefully-audited core libraries
  that consistently validate access controls.
- **Minimizing supply chain risk:** Dependencies are evaluated for quality,
  maintainability, and necessity before being integrated into the system.

---

## Highly configurable access controls

### Identity management your way

- [Email authentication](/help/invite-users-to-join), with option to [restrict
  email
  domains](/help/restrict-account-creation#configuring-email-domain-restrictions)
- [OAuth social logins](/help/configure-authentication-methods) (Google, GitHub,
  GitLab, Apple)
- SSO with [SAML](/help/saml-authentication) (Including Okta and OneLogin),
  [Microsoft Entra
  ID](https://zulip.readthedocs.io/en/stable/production/authentication-methods.html#microsoft-entra-id),
  [OpenID
  Connect](https://zulip.readthedocs.io/en/stable/production/authentication-methods.html#openid-connect)
- [AD/LDAP user and group
  sync](https://zulip.readthedocs.io/en/stable/production/authentication-methods.html#ldap-including-active-directory)
- [SAML user and group sync](/help/saml-authentication)
- [SCIM user and group sync](/help/scim)
- Configure whether users can change their
  [names](/help/restrict-name-and-email-changes), [email
  addresses](/help/restrict-name-and-email-changes), and
  [avatars](/help/restrict-profile-picture-changes)
- [Minimum app
  version](https://zulip.readthedocs.io/en/latest/overview/release-lifecycle.html#desktop-app)
  for the desktop app
- [100+ authentication
  options](https://python-social-auth.readthedocs.io/en/latest/backends/index.html#social-backends)
  with python-social-auth (self-hosted)

### Configure data access and messaging policies

- [Private channels with shared history](/help/channel-permissions#private-channels)
- [Private channels with private history](/help/channel-permissions#private-channels)
- [Channel posting permissions](/help/channel-posting-policy)
- [Direct messaging permissions](/help/restrict-direct-messages)
- [Customize permissions by channel](/help/channel-permissions)
- Authenticated access to uploaded files
- [Custom terms of service and privacy
  policy](https://zulip.readthedocs.io/en/stable/production/settings.html#terms-of-service-and-privacy-policy)
- [Configurable waiting period](/help/restrict-permissions-of-new-members) for new users

### Custom permissions with comprehensive audit log

- [Role-based access control](/help/user-roles)
- Control access by [roles](/help/user-roles), [custom
  groups](/help/user-groups), and user accounts
- Grant [permissions](/help/manage-permissions) to roles, custom groups, and
  individual users
- [Control](/help/manage-permissions) who can create channels, subscribe and
  unsubscribe users, add custom emoji and integrations, and more
- Permissions for [editing](/help/restrict-message-editing-and-deletion),
  [deleting](/help/restrict-message-editing-and-deletion) and
  [moving](/help/restrict-moving-messages) messages, and an audit history of
  these actions
- Permanent long-term audit log of important actions (e.g., changes to
  passwords, email addresses, and channel subscriptions)

### Tightly controlled guest accounts for vendors, partners, and customers

[Guest users](/help/guest-users) cannot see any channels, unless they have been
specifically subscribed, and can never invite new users. You can limit guests’
ability to see other users, and warn users when they are DMing a guest to
prevent accidental disclosures.

---

## Responsible disclosure program

- We operate a private HackerOne vulnerability disclosure program, and credit
  reporters for issues that were not discovered internally. See the [Zulip
  security reporting policy](https://github.com/zulip/zulip/security/policy).
- We publish security releases for all security vulnerabilities, and publicly
  disclose them [on our blog](https://blog.zulip.com/tag/security/) with CVE
  numbers for tracking.
- Zulip Server security and maintenance releases are carefully engineered to
  minimize the inherent risks of upgrading software, so there is never a reason
  to run an insecure version. Announcements of serious vulnerabilities
  [include](https://blog.zulip.com/2025/07/02/zulip-server-10-4-security-release/)
  applicable mitigation guidance.
- We responsibly report vulnerabilities we discover in our upstream
  dependencies.

---

## Learn more

For more information, check out our [guide on securing your Zulip
server](https://zulip.readthedocs.io/en/stable/production/securing-your-zulip-server.html).
