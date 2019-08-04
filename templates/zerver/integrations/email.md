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

The default behavior of this integration is designed to be convenient
in the common case.  We offer a few options for overriding the default
behavior, configured by editing the Zulip email address:

Example: `general.abcd1234.show-sender.include-footer@example.zulipchat.com`

* `show-sender`: Will cause `From: <Sender email address>` to be
  displayed at the top of Zulip messages sent via this integration.
* `include-footer`: Include footer sections of emails (by default,
  they are not included, to minimize clutter).
* `include-quotes`: Include quoted sections of emails in the Zulip
  message (By default, Zulip includes them only for forwarded emails,
  i.e. those where the subject starts with `Fwd:` or similar)
* You can use `+` instead of the `.` separators if you prefer.  We
  recommend the `.` syntax by default because Google Groups silently
  drops `+` from email addresses subscribed to its mailing lists.
