Get Zulip notifications from Alertmanager!

{start_tabs}

1. {!create-stream.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

    Additionally, you may specify URL parameters named `name` and `desc` to specify which labels
    or annotations will be used to construct the alert message. This allows you to use arbitrary labels
    and annotations defined in your alerting rules.

        {{ api_url }}{{ integration_url }}?api_key=abcdefgh&stream=stream%20name&name=host&desc=alertname

1. In your Alertmanager config, set up a new webhook receiver, like so:

    ```
    - name: ops-zulip
      webhook_configs:
        - url: "<the URL constructed above>"
    ```

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/alertmanager/001.png)
