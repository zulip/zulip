Zulip supports integration with GoCD and can notify you of
your build statuses.

{start_tabs}

1. {!create-stream.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Add the following to your `Config.XML` file.

    ```
    <pipeline name="mypipeline">
        <trackingtool link="<URL constructed above>" regex="##(\d+)"/>
        ...
    </pipeline>
    ```

    Push this change to your repository. For further information,
    see [GoCD's documentation](https://docs.gocd.org/current/integration/).

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/gocd/001.png)

### Related documentation

{!webhooks-url-specification.md!}