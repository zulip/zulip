# Zulip Sonarqube integration

Get Zulip notifications for your Sonarqube code analysis!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. To configure webhooks for a specific SonarQube project, go to the project,
    and select **Administration**. Select **Webhooks**, and click **Create**.

1. Set **Name** of the webhook to a name of your choice, such as `Zulip`.
    Set **URL** to the URL generated above, and click **Create**.

!!! tip ""

    You can also configure webhooks globally in SonarQube via
    **Configurations** -> **Webhooks**.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/sonarqube/001.png)

### Related documentation

{!webhooks-url-specification.md!}
