# GDPR compliance

This page covers how Zulip interacts with the EU's landmark GDPR
legislation; you can read the
[Zulip Cloud privacy policy](https://zulip.com/policies/privacy) for our
general privacy policies.

## What is GDPR?

The General Data Protection Regulation (GDPR) is a wide-ranging law designed
to protect the privacy of individuals in the European Union (EU) and
give them control over how their personal data is collected,
processed, and used.  The law applies to any company that collects or
processes the data of European consumers.

## How Zulip supports GDPR compliance

GDPR compliance is supported [for Zulip
Cloud](#gdpr-compliance-with-zulip-cloud) and [for self-hosted Zulip
installations](#gdpr-compliance-for-self-hosted-installations).

A [Data Processing Addendum
(DPA)](https://zulip.com/static/images/policies/Zulip-Data-Processing-Addendum.pdf)
is incorporated into Zulip's [Terms of
Service](https://zulip.com/policies/terms).

## GDPR compliance with Zulip Cloud

The Zulip Cloud service is operated by Kandra Labs, Inc. To deliver the Zulip
Cloud service, Kandra Labs, Inc. acts as a compliant data
[processor](#background-on-controllers-and-processors), with each of our
customers acting as the data
[controller](#background-on-controllers-and-processors).  Kandra Labs receives
personal data from our customers in the context of providing our Zulip Cloud
team chat services to the customer.

Zulip makes it easy for organizations to comply with GDPR-related requests from
users:

* Zulip users can [edit their profile
  information](/help/edit-your-profile#edit-your-profile), [configure privacy
  settings](/help/review-your-settings#review-your-privacy-settings), and
  [delete their own
  messages](/help/delete-a-message#delete-a-message-completely) and [uploaded
  files](/help/manage-your-uploaded-files#delete-a-file), if permissions to do
  so are enabled by your organization.
* Organization administrators can also [edit or remove any user's profile
  information](/help/manage-a-user), or [deactivate a user](/help/deactivate-or-reactivate-a-user).
* You can [export](/help/export-your-organization) all the data related to a
  Zulip user or organization.
* The [Zulip REST API](/api/rest) lets you automate your processes for handling
  GDPR requests.

Contact [support@zulip.com](mailto:support@zulip.com) for
any assistance with GDPR compliance with Zulip Cloud.

## GDPR compliance for self-hosted installations

Compliance is often simpler when running software on-premises, since
you can have complete control over how your organization uses the data
you collect.

The Zulip [Mobile Push Notification Service][mobile-push] is operated by Kandra
Labs, Inc. Kandra Labs acts as a data processor to deliver the service, which
uses the same hosting infrastructure and [terms of
service](https://zulip.com/policies/terms) as Zulip Cloud.

[mobile-push]: https://zulip.readthedocs.io/en/stable/production/mobile-push-notifications.html

In addition to the features [described
above](#gdpr-compliance-with-zulip-cloud), the following tools help self-hosted
Zulip installations comply with GDPR-related requests from users:

* The Zulip server comes with a [command-line tool][management-commands],
  `manage.py export_single_user`, which is a variant of the main server
  [export tool][export-and-import-tool], that exports a single Zulip
  user's account details, preferences, channel subscriptions, and message
  history in a structured JSON format.
* The Django management shell (`manage.py shell`) and database shell
  (`manage.py dbshell`) allows you to query, access, edit, and delete
  data directly.

There's a lot more that goes into GDPR compliance, including securing your
server infrastructure responsibly, internal policies around access, logging, and
backups, etc. [Zulip Business](https://zulip.com/plans/#self-hosted) and [Zulip
Enterprise](https://zulip.com/plans/#self-hosted) customers can contact
[support@zulip.com](mailto:support@zulip.com) for assistance with GDPR
compliance with Zulip.

[management-commands]: https://zulip.readthedocs.io/en/stable/production/management-commands.html
[export-and-import-tool]: https://zulip.readthedocs.io/en/stable/production/export-and-import.html

## Background on controllers and processors

There are two key relationships that are defined in the GDPR. As a
customer of Zulip Cloud, you operate as the controller when using our
products and services. You have the responsibility for ensuring that
the personal data you are collecting is being processed in a lawful
manner as described above and that you are using processors, such as
Zulip Cloud, that are committed to handling the data in a compliant
manner.

Zulip Cloud is considered a **data processor**. We act on the
instructions of the controller (you). Similar to controllers,
processors are expected to enumerate how they handle personal data,
which we have outlined in this document and the legal documents listed
below. As a processor, we rely on our customers to ensure that there
is a lawful basis for processing.

Processors may leverage other third-parties in the processing of
personal data. These entities are commonly referred to as
sub-processors. For example, Kandra Labs leverages cloud service
providers like Amazon Web Services and Mailgun to host Zulip Cloud.
See [full list of subprocessors for Zulip
Cloud](/policies/subprocessors).

## Related articles

* [Zulip Cloud privacy policy](https://zulip.com/policies/privacy)
* [Terms of Service](https://zulip.com/policies/terms)
* [Data Processing Addendum
  (DPA)](https://zulip.com/static/images/policies/Zulip-Data-Processing-Addendum.pdf)
* [Subprocessors for Zulip Cloud](/policies/subprocessors)
