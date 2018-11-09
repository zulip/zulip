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

<table class="table">
    <thead>
        <tr>
            <th>Name</th>
            <th>Description</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td><code>bot_email</code></td>
            <td>Email of the bot user</td>
        </tr>
        <tr>
            <td><code>data</code></td>
            <td>The content of the message (in Markdown)</td>
        </tr>
        <tr>
            <td><code>message</code></td>
            <td>A dict containing details on the message which
            triggered the outgoing webhook</td>
        </tr>
        <tr>
            <td><code>token</code></td>
            <td>A string of alphanumeric characters you can use to
            authenticate the webhook request (each bot user uses a fixed token)</td>
        </tr>
        <tr>
            <td><code>trigger</code></td>
            <td>Trigger method</td>
        </tr>
    </tbody>
</table>

Some of the important fields in the `message` dict include the following:

<table class="table">
    <thead>
        <tr>
            <th>Name</th>
            <th>Description</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td><code>recipient_id</code></td>
            <td>Unique ID of the stream that will persist even if the stream is renamed</td>
        </tr>
        <tr>
            <td><code>rendered_content</code></td>
            <td>The content of the message, rendered in HTML</td>
        </tr>
    </tbody>
</table>

A correctly implemented endpoint will do the following:

* It will calculate a response that we call the "content" of
  the response.
* It will encode the content in Zulip's flavor of markdown (or
  just plain text).
* It will then make a dictionary with key of "content" and
  the value being that content.  (Note that "response_string" is
  a deprecated synonym for "content".)
* It will encode that dictionary as JSON.

If the bot code wants to opt out of responding, it can explicitly
encode a JSON dictionary that contains `response_not_required` set
to `True`, so that no response message is sent to the user.  (This
is helpful to distinguish deliberate non-responses from bugs.)

### Example incoming payload

This is an example of the JSON payload that the Zulip server will `POST`
to your server:

{generate_code_example|zulip-outgoing-webhook-payload|fixture}

### Example response payloads

Here's an example of the JSON your server should respond with if
you would not like to send a response message:

```
{
    "response_not_required": true
}
```

Here's an example of the JSON your server should respond with if
you would like to send a response message:

```
{
    "content": "Hey, we just received something from Zulip!"
}
```

## Slack-format webhook format

This interface translates Zulip's outgoing webhook's request into the
format that Slack's outgoing webhook interface sends.  As a result,
one should be able to use this to interact with third-party
integrations designed to work with Slack's outgoing webhook interface.
Here's how we fill in the fields that a Slack-format webhook expects:

<table class="table">
    <thead>
        <tr>
            <th>Name</th>
            <th>Description</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td><code>token</code></td>
            <td>A string of alphanumeric characters you can use to
            authenticate the webhook request (each bot user uses a fixed token)</td>
        </tr>
        <tr>
            <td><code>team_id</code></td>
            <td>String ID of the Zulip organization</td>
        </tr>
        <tr>
            <td><code>team_domain</code></td>
            <td>Domain of the Zulip organization</td>
        </tr>
        <tr>
            <td><code>channel_id</code></td>
            <td>Stream ID</td>
        </tr>
        <tr>
            <td><code>channel_name</code></td>
            <td>Stream name</td>
        </tr>
        <tr>
            <td><code>timestamp</code></td>
            <td>Timestamp for when message was sent</td>
        </tr>
        <tr>
            <td><code>user_id</code></td>
            <td>ID of the user who sent the message</td>
        </tr>
        <tr>
            <td><code>user_name</code></td>
            <td>Full name of sender</td>
        </tr>
        <tr>
            <td><code>text</code></td>
            <td>The content of the message (in Markdown)</td>
        </tr>
        <tr>
            <td><code>trigger_word</code></td>
            <td>Trigger method</td>
        </tr>
        <tr>
            <td><code>service_id</code></td>
            <td>ID of the bot user</td>
        </tr>
    </tbody>
</table>

The above data is posted as list of tuples (not JSON), here's an example:

```
[('token', 'v9fpCdldZIej2bco3uoUvGp06PowKFOf'),
 ('team_id', 'zulip'),
 ('team_domain', 'zulip.com'),
 ('channel_id', '123'),
 ('channel_name', 'integrations'),
 ('timestamp', 1532078950),
 ('user_id', 21),
 ('user_name', 'Sample User'),
 ('text', '@**test**'),
 ('trigger_word', 'mention'),
 ('service_id', 27)]
```

* For successful request, if data is returned, it returns that data,
  else it returns a blank response.
* For failed request, it returns the reason of failure, as returned by
  the server, or the exception message.
