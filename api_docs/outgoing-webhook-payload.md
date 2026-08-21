# Outgoing webhook payloads

Zulip supports [outgoing webhooks](/help/outgoing-webhooks) in a clean,
native [Zulip format](#zulip-format), as well as in a [Slack-compatible
format](#slack-compatible-format).

## Zulip format

{generate_code_example|/zulip-outgoing-webhook:post|fixture}

### Fields documentation

{generate_return_values_table|zulip.yaml|/zulip-outgoing-webhook:post}

## Slack-compatible format

This webhook format is compatible with [Slack's outgoing webhook
API](https://api.slack.com/custom-integrations/outgoing-webhooks),
which can help with porting an existing Slack integration to work with
Zulip, and allows immediate integration with many third-party systems
that already support Slack outgoing webhooks.

**Changes**: In Zulip 13.0 (feature level ZF-4d8ff9), the
`command` field was added to requests triggered by a leading bot
mention, and the leading bot mention is no longer included in `text`
for those requests.

The following table details how the Zulip server translates a Zulip
message into the Slack-compatible webhook format.

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
            <td>Channel ID prefixed by "C"</td>
        </tr>
        <tr>
            <td><code>channel_name</code></td>
            <td>Channel name</td>
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
            <td>The content of the message (in Markdown). When the
            webhook is triggered by a bot mention at the start of the
            message, the mention is stripped from <code>text</code>
            and sent separately in the <code>command</code> field.</td>
        </tr>
        <tr>
            <td><code>command</code></td>
            <td>Present when the message starts with a mention of the
            bot. Contains the mention transformed into a
            slash-command-style string, e.g., <code>/My Bot</code>.
            Omitted when the message does not start with a bot
            mention.</td>
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
 ('text', 'do something'),
 ('trigger_word', 'mention'),
 ('service_id', 27),
 ('command', '/My Bot')]
```

* For successful requests, if data is returned, it returns that data,
  else it returns a blank response.
* For failed requests, it returns the reason of failure, as returned by
  the server, or the exception message.
