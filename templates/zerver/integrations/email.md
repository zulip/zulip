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
