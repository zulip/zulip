# Reporting security vulnerabilities

If you believe you’ve identified a security vulnerability in Zulip, please
[contact our security team](#how-to-report-a-possible-security-issue) as soon as
possible! Responsible disclosure helps us keep our user community safe.

Since Zulip is 100% open-source software, security researchers have
full access to [Zulip’s codebase](https://github.com/zulip/). To learn
about Zulip’s security model, check out:

- [Security overview](https://zulip.com/security/)
- [Securing your Zulip server](https://zulip.readthedocs.io/en/latest/production/securing-your-zulip-server.html)
- [Release lifecycle](https://zulip.readthedocs.io/en/latest/overview/release-lifecycle.html)

Join our low-traffic [release announcements mailing
list](https://groups.google.com/g/zulip-announce) to get notified
about new security releases.

## How to report a possible security issue

To allow us to responsibly remediate security issues, please _do not_
report them publicly on GitHub, in the Zulip development community, or
anywhere else. Thank you for helping us protect Zulip’s user
community!

Contact Zulip’s security team at [security@zulip.com](mailto:security@zulip.com)
or via our [HackerOne disclosure program](#hackerone-disclosure-program). Reach
out to [security@zulip.com](mailto:security@zulip.com) for an invitation to the
program.

Please include the following information in your report:

1. The product where you’ve identified a vulnerability, including the versions
   of the software that you tested.
2. A clear series of steps that maintainers can use to reproduce the
   vulnerability, and any investigation you’ve done into the root cause.
3. Any suggestions you have for remediating the issue.
4. How you'd like to be credited in our release announcement when we publish the
   fix, if your report is confirmed.

You are welcome to use automated tools, including AI, to research
vulnerabilities. However, please take the time to **_personally_**
verify the issue, and write the vulnerability description yourself to
avoid errors. Reporting “vulnerabilities” that were hallucinated by AI
wastes the time of open-source maintainers.

## What happens when a security issue is reported

1. When a credible report of a security issue is received, our security team
   will promptly acknowledge the report, and begin investigation. If you have
   not received a response acknowledging receipt of a report within 2 business
   days, please follow up to confirm that your report was not blocked by spam
   filters.
2. If our investigation determines that the report identifies a vulnerability in
   our software, we will create a CVE for the security issue, and begin work on
   remediation.
3. We will publish the fixes to the `main` branch and the release branch for the
   current major release series.
4. The security issue and remediation will be announced on our
   [blog](https://blog.zulip.com/tag/security/), crediting any external
   reporters.

Please do not publicly disclose an issue prior to us notifying you
that a fix has been released, or share exploit code that might be used
against self-hosted instances that have not yet upgraded to the
patched version.

## Useful resources for security researchers

- Follow our
  [guide](https://zulip.readthedocs.io/en/latest/development/overview.html)
  to set up Zulip’s development environment. This will let you test
  Zulip without risk of disrupting Zulip’s users. The development
  environment is designed for developer convenience (you can log in as
  any user with `/devlogin`; see also `/devtools` features), but those
  features use a separate URL namespace, so it's easy to determine if
  you're accidentally using one. Historically, the vast majority of
  security issues found in Zulip could be reproduced in the
  development environment.
- To test against a production instance, follow our
  [guide](https://zulip.readthedocs.io/en/latest/production/install.html) for
  setting up a Zulip production server.
- The Zulip software's [default production puppet
  configuration](https://github.com/zulip/zulip/tree/main/puppet) is a great
  resource when looking for configuration problems. Issues impacting the
  `zulip/` and `kandra/` (Zulip Cloud) configurations are in scope.
- Zulip is a [Django](https://docs.djangoproject.com/) project, and
  `zproject/urls.py` and the files it includes are a reference for the endpoints
  supported by the software, most of which are detailed in the [API
  documentation](https://zulip.com/api/).
- Zulip has [extensive developer
  documentation](https://zulip.readthedocs.io/en/latest/overview/readme.html)
  that describes how the software works under the hood.
- The [help center](https://zulip.com/help/) has extensive documentation on how
  Zulip is expected to work. We appreciate reports of any inconsistencies
  between the documented security model and actual behavior, e.g., regarding
  which users can see a given piece of information or perform a given action.

## HackerOne disclosure program

Zulip operates a private HackerOne disclosure program.

### What’s in scope

Security issues must be reported for the [latest
release](https://zulip.readthedocs.io/en/latest/overview/release-lifecycle.html)
or the `main` branch.

- **Security issues**: Security issues impacting any part of the Zulip
  open-source project, including the [Server](https://github.com/zulip/zulip/),
  [Electron desktop app](https://github.com/zulip/zulip-desktop/), [Flutter
  mobile app](https://github.com/zulip/zulip-flutter), or API bindings for
  various languages. All official projects are in the
  <https://github.com/zulip/> GitHub organization.
- **Security hardening**: We love to recognize significant work on hardening
  Zulip against potential security issues! If you’ve contributed a _merged_
  security hardening pull request, you’re welcome to submit a link to it to the
  HackerOne program to receive recognition.

### What’s out of scope

The following are out of scope for this program:

- Penetration testing against specific production installations of
  Zulip. **Do not test against an installation of Zulip that you do
  not own**. This includes `chat.zulip.org`, `zulipchat.com`, and any
  other existing install you might find. If you see a configuration
  that appears to be risky with Zulip Cloud, please report the issue;
  we will do the testing.

- Vulnerabilities in third-party libraries are in scope only if they
  can be fixed by upgrading the version of the third-party library
  used by Zulip, the library is unmaintained, or you otherwise have a
  reason to believe we can help get the vulnerability fixed sooner.

- Issues that only affect the Zulip development environment must
  explain how they violate the security model _for the development
  environment_.
