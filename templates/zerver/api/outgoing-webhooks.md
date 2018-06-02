# Outgoing Webhooks

Outgoing Webhooks allow you to build or set up Zulip integrations
which are notified when certain types of messages are sent in
Zulip. When one of those events is triggered, we'll send a HTTP POST
payload to the webhook's configured URL.  Webhooks can be used to
power a wide range of Zulip integrations.  For example, the
[Zulip Botserver][zulip-botserver] is built on top of this API.

Zulip supports outgoing webhooks both in a clean native Zulip format,
as well as a format that's compatible with
[Slack's outgoing webhook API][slack-outgoing-webhook], which can help
with porting an existing Slack integration to work with Zulip.

[zulip-botserver]: https://zulipchat.com/api/deploying-bots#zulip-botserver
[slack-outgoing-webhook]: https://api.slack.com/custom-integrations/outgoing-webhooks

To register an outgoing webhook:

* Log in to the Zulip server.
* Navigate to *Settings (<i class="fa fa-cog"></i>)* -> *Your bots* ->
  *Add a new bot*.  Select *Outgoing webhook* for bot type, the URL
  you'd like Zulip to post to as the **Endpoint URL**, the format you
  want, and click on *Create bot*. to submit the form/
* Your new bot user will appear in the *Active bots* panel, which you
  can use to edit the bot's settings.

## Triggering

There are currently two ways to trigger an outgoing webhook:
1.  **@-mention** the bot user in a stream.  If the bot replies, its
    reply will be sent to that stream and topic.
2.  **Send a private message** with the bot as one of the recipients.
    If the bot replies, its reply will be sent to that thread.

## Zulip message format

The Zulip-format webhook messages post the following data, encoded as JSON:

```
data:       content of message in a ready-to-use format (with the mention stripped)
token:      A string of alphanumeric characters you can use to
            authenticate the webhook request (each bot user uses a fixed token).
message:    the message which triggered outgoing webhook
├── id
├── sender_email
├── sender_full_name
├── sender_short_name
├── sender_realm_str
├── sender_id
├── type
├── display_recipient
├── recipient_id
├── subject
├── timestamp
├── avatar_url
├── client
```

A correctly implemented endpoint will do the following:

* For a successful request, it should return receives either a json
  encoded dictionary, describing how to respond to the user.
* If the dictionary contains `response_not_required` set to `True`, no
  response message is sent to the user.
* If the dictionary contains `response_string` key, the corresponding
  value is used as the `content` for a Zulip message sent in response;
  otherwise, a generic default response message is sent.
* For a failed request, the endpoint should return data on the
  error.

### Example payload

{generate_code_example|zulip-outgoing-webhook-payload|fixture}

## Slack-format webhook format

This interface translates the Zulip's outgoing webhook's request into
Slack's outgoing webhook request.  Hence the outgoing webhook bot
would be able to post data to URLs which support Slack's outgoing
webhooks.  Here's how we fill in the fields that a Slack format
webhook expects:

```
token:          string of alphanumeric characters (similar to above)
team_id:        string id of the Zulip organization
team_domain:    domain of the Zulip organization
channel_id:     stream id
channel_name:   stream name
timestamp:      timestamp when message was sent
user_id:        id of user who sent the message
user_name:      full name of sender
text:           content of message in a more readable format
trigger_word:   trigger method
service_id:     id of bot user
```

The above data is posted as list of tuples (not JSON), here's an example:

```
[('token', 'abcdef'),
 ('team_id', 'zulip'),
 ('team_domain', 'zulip.com'),
 ('channel_id', '123'),
 ('channel_name', 'integrations'),
 ('timestamp', 123456),
 ('user_id', 21),
 ('user_name', 'Sample User'),
 ('text', '@**test**'),
 ('trigger_word', 'mention'),
 ('service_id', None)]
```

* For successful request, if data is returned, it returns that data,
  else it returns a blank response.
* For failed request, it returns the reason of failure, as returned by
  the server, or the exception message.
