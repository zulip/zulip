Get WordPress notifications in Zulip!

If you're hosting your WordPress blog yourself (i.e., not on WordPress.com),
first install the
[HookPress plugin](https://wordpress.org/plugins/hookpress/) (experimental).

{start_tabs}

1. {!create-stream.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Go to
   `https://YOUR-WORDPRESS-BLOG/wp-admin/options-general.php?page=webhooks`,
   after replacing `YOUR-WORDPRESS-BLOG` appropriately. Click **Add webhook**.

1. Select the **Action** that you'd like to be notified about, along with
   the corresponding **Fields**. The list of currently supported actions is:

    * **publish_post**: Use fields *post_title*, *post_type*, and *post_url*
    * **publish_page**: Use fields *post_title*, *post_type*, and *post_url*
    * **user_register**: Use fields *display_name* and *user_email* (available on self-hosted blogs only)
    * **wp_login**: Use field *user_login* (available on self-hosted blogs only)

1. Set **URL** to the URL constructed above, and click **Add new webhook**.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/wordpress/wordpress_post_created.png)

### Related documentation

{!webhooks-url-specification.md!}