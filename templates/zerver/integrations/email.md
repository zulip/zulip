You can send emails to Zulip! This is useful:

* If you use a service that can send emails but does not easily lend
  itself to more direct integration
* If you have an email that you want to discuss on Zulip
* As a structured, searchable, commentable archive for mailing list
  traffic

To send an email to a Zulip stream:

1. Visit your {{ subscriptions_html|safe }} and click on the stream
   row to expand it.

2. Copy the stream email address(e.g. `{{ email_gateway_example }}`).
   If the stream name contains special characters, we've transformed
   the name so it is a safe email recipient.

3. Send an email (To, CC, and BCC all work) to the stream email address.
   The email subject will become the stream topic, and the email
   body will become the Zulip message content.

Please note that it may take up to one minute for the message to show
up in Zulip.

**Additional options**

This integration supports additional options when sending an email into it,
controled through the email address. The way you use them is by adding
`.option-name` at the end of the first part of the email address.
The options can be used in conjunction with each other.
Example: `{{ email_gateway_example_with_options }}`

* `show-sender`: Add `.show-sender` in the address (as specified above)
  if you want `From: <Sender email address>` to be displayed at the top
  of your message.
* `include-footer`: By default, Zulip tries to remove the footer from the messages,
  as they can cause unnecessary clutter. If you want the footer to be kept,
  add `.include-footer` in the address when sending the message.
* `include-quotes`: Just like footers, quotations of other emails are removed by default.
  To keep them, add `.include-quotes` in the address.
  Additional note: If the email is forwarded (this is determined by the presence of `FWD:`,
  or similar, at the beginning of the subject), quotations are kept by default,
  regardless of usage of this option.

**Final notes**

* The stream name (with the following `.`) can be omitted from the address,
  and the email will still be properly processed as long as the alphanumeric token
  is correct.
* Alternatively, `+` can be used in place of the `.` separators, but this is supported
  mainly for backward compatibility.
