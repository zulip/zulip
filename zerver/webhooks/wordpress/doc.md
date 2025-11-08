# Zulip WordPress integration

Get WordPress notifications in Zulip!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Add `/wp-admin/options-general.php?page=webhooks` to the end of your
   WordPress URL, and navigate to the site. Click **Add webhook**.

1. Select an **Action** from the [supported
   events](#filtering-incoming-events) that you'd like to be notified
   about, along with these corresponding **Fields**: `post_title`,
   `post_type`, and `post_url`.

1. Set **URL** to the URL generated above, and click **Add new webhook**.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/wordpress/wordpress_post_created.png)

{!event-filtering-additional-feature.md!}

### Related documentation

- [WordPress webhooks documentation][1]

{!webhooks-url-specification.md!}

[1]: https://wordpress.com/support/webhooks/
