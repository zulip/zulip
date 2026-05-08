# Zulip Confluence Cloud integration

Get Zulip notifications for your Confluence Cloud spaces via a
[Forge](https://developer.atlassian.com/platform/forge/) app!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Follow [Atlassian's Forge getting-started
   guide](https://developer.atlassian.com/platform/forge/getting-started/)
   to install the Forge CLI and create a new app targeting Confluence.

    - In the app's `manifest.yml`, declare a `confluence:trigger` module
      for the events you want (e.g., `avi:confluence:created:page`) and
      set the handler to forward the enriched event payload via HTTP POST
      to the Zulip webhook URL generated above.

    - Format the POST body to match the structure that this integration
      expects. The JSON fixtures in
      `zerver/webhooks/confluence_cloud/fixtures/` of the Zulip source
      tree are the authoritative reference; one fixture exists per
      supported event. At minimum, the payload must include:

          - `webhookEvent`: one of the supported event-name strings listed
            below.
          - `user.displayName`: the human-readable name shown in the Zulip
            message.
          - For page and blog events, a `page` object with `title`,
            `space.name`, and `_links.base` + `_links.webui`.
          - For comment events, a `comment.container` object with `title`
            and `_links.base` + `_links.webui` (the container is the parent
            page or blog post).


1. Run `forge deploy` and `forge install` to activate the app on your
   Confluence Cloud site.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/confluence/001.png)

{!event-filtering-additional-feature.md!}

### Related documentation

- [Atlassian Forge documentation](https://developer.atlassian.com/platform/forge/)
- [Forge event reference for Confluence](https://developer.atlassian.com/platform/forge/events-reference/confluence/)

{!webhooks-url-specification.md!}
