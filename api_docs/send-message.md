{generate_api_header(/messages:post)}

## Usage examples

{start_tabs}

{generate_code_example(python)|/messages:post|example}

{generate_code_example(javascript)|/messages:post|example}

{tab|curl}

``` curl
# For stream messages
curl -X POST {{ api_url }}/v1/messages \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY \
    --data-urlencode type=stream \
    --data-urlencode 'to="Denmark"' \
    --data-urlencode topic=Castle \
    --data-urlencode 'content=I come not, friends, to steal away your hearts.'

# For direct messages
curl -X POST {{ api_url }}/v1/messages \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY \
    --data-urlencode type=direct \
    --data-urlencode 'to=[9]' \
    --data-urlencode 'content=With mirth and laughter let old wrinkles come.'
```

{tab|zulip-send}

You can use `zulip-send`
(available after you `pip install zulip`) to easily send Zulips from
the command-line, providing the message content via STDIN.

```bash
# For stream messages
zulip-send --stream Denmark --subject Castle \
    --user othello-bot@example.com --api-key a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5

# For direct messages
zulip-send hamlet@example.com \
    --user othello-bot@example.com --api-key a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5
```

#### Passing in the message on the command-line

If you'd like, you can also provide the message on the command-line with the
`-m` or `--message` flag, as follows:


```bash
zulip-send --stream Denmark --subject Castle \
    --message 'I come not, friends, to steal away your hearts.' \
    --user othello-bot@example.com --api-key a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5
```

You can omit the `user` and `api-key` parameters if you have a `~/.zuliprc`
file.

{end_tabs}

## Parameters

{generate_api_arguments_table|zulip.yaml|/messages:post}

{generate_parameter_description(/messages:post)}

## Response

{generate_return_values_table|zulip.yaml|/messages:post}

{generate_response_description(/messages:post)}

#### Example response(s)

{generate_code_example|/messages:post|fixture}
