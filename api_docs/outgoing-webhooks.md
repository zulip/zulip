# Outgoing webhooks

Outgoing webhooks allow you to build or set up Zulip integrations
which are notified when certain types of messages are sent in
Zulip. When one of those events is triggered, we'll send a HTTP POST
payload to the webhook's configured URL.  Webhooks can be used to
power a wide range of Zulip integrations.  For example, the
[Zulip Botserver][zulip-botserver] is built on top of this API.

Zulip supports outgoing webhooks both in a clean native Zulip format,
as well as a format that's compatible with
[Slack's outgoing webhook API][slack-outgoing-webhook], which can help
with porting an existing Slack integration to work with Zulip.

[zulip-botserver]: /api/deploying-bots#zulip-botserver
[slack-outgoing-webhook]: https://api.slack.com/custom-integrations/outgoing-webhooks

To register an outgoing webhook:

* Log in to the Zulip server.
* Navigate to *Personal settings (<i class="zulip-icon zulip-icon-gear"></i>)* -> *Bots* ->
  *Add a new bot*.  Select *Outgoing webhook* for bot type, the URL
  you'd like Zulip to post to as the **Endpoint URL**, the format you
  want, and click on *Create bot*. to submit the form/
* Your new bot user will appear in the *Active bots* panel, which you
  can use to edit the bot's settings.

## Triggering

There are currently two ways to trigger an outgoing webhook:

*  **@-mention** the bot user in a stream.  If the bot replies, its
    reply will be sent to that stream and topic.
*  **Send a direct message** with the bot as one of the recipients.
    If the bot replies, its reply will be sent to that thread.

## Timeouts

The remote server must respond to a `POST` request in a timely manner.
The default timeout for outgoing webhooks is 10 seconds, though this
can be configured by the administrator of the Zulip server by setting
`OUTGOING_WEBHOOKS_TIMEOUT_SECONDS` in the [server's
settings][settings].

[settings]: https://zulip.readthedocs.io/en/latest/subsystems/settings.html#server-settings

## Outgoing webhook format

{generate_code_example|/zulip-outgoing-webhook:post|fixture}

### Fields documentation

{generate_return_values_table|zulip.yaml|/zulip-outgoing-webhook:post}

## Replying with a message

Many bots implemented using this outgoing webhook API will want to
send a reply message into Zulip.  Zulip's outgoing webhook API
provides a convenient way to do that by simply returning an
appropriate HTTP response to the Zulip server.

A correctly implemented bot will return a JSON object containing one
of two possible formats, described below.

### Example response payloads

If the bot code wants to opt out of responding, it can explicitly
encode a JSON dictionary that contains `response_not_required` set
to `True`, so that no response message is sent to the user.  (This
is helpful to distinguish deliberate non-responses from bugs.)

Here's an example of the JSON your server should respond with if
you would not like to send a response message:

```json
{
    "response_not_required": true
}
```

Here's an example of the JSON your server should respond with if
you would like to send a response message:

```json
{
    "content": "Hey, we just received **something** from Zulip!"
}
```

The `content` field should contain Zulip-format Markdown.

Note that an outgoing webhook bot can use the [Zulip REST
API](/api/rest) with its API key in case your bot needs to do
something else, like add an emoji reaction or upload a file.

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
            <td>ID of the Zulip organization prefixed by "T".</td>
        </tr>
        <tr>
            <td><code>team_domain</code></td>
            <td>Hostname of the Zulip organization</td>
        </tr>
        <tr>
            <td><code>channel_id</code></td>
            <td>Stream ID prefixed by "C"</td>
        </tr>
        <tr>
            <td><code>channel_name</code></td>
            <td>Stream name</td>
        </tr>
        <tr>
            <td><code>thread_ts</code></td>
            <td>Timestamp for when message was sent</td>
        </tr>
        <tr>
            <td><code>timestamp</code></td>
            <td>Timestamp for when message was sent</td>
        </tr>
        <tr>
            <td><code>user_id</code></td>
            <td>ID of the user who sent the message prefixed by "U"</td>
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
 ('team_id', 'T1512'),
 ('team_domain', 'zulip.example.com'),
 ('channel_id', 'C123'),
 ('channel_name', 'integrations'),
 ('thread_ts', 1532078950),
 ('timestamp', 1532078950),
 ('user_id', 'U21'),
 ('user_name', 'Full Name'),
 ('text', '@**test**'),
 ('trigger_word', 'mention'),
 ('service_id', 27)]
```

* For successful request, if data is returned, it returns that data,
  else it returns a blank response.
* For failed request, it returns the reason of failure, as returned by
  the server, or the exception message.
