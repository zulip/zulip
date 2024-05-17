1. {!create-channel.md!}

1. {!create-an-incoming-webhook.md!}

1. In Home Assistant, you need to add the `notify` service to your
    `configuration.yaml` file.  This should look something like this:

    ![](/static/images/integrations/homeassistant/001.png)

1. The `api_key` parameter should correspond to your bot's key. The `stream`
    parameter is not necessarily required; if not given, it will default to
    the `homeassistant` channel.

1. And the URL under `resource` should start with:

    `{{ api_url }}/v1/external/homeassistant`

1. Finally, you need to configure a trigger for the service by adding
    an automation entry in the HomeAssistant `configuration.yaml` file.

    ![](/static/images/integrations/homeassistant/002.png)

    The `data` object takes at least a `message` property and an optional
    `title` parameter which will be the conversation topic and which defaults
    to `homeassistant` if not given.

{!congrats.md!}

![](/static/images/integrations/homeassistant/003.png)
