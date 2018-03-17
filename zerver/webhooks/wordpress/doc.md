See WordPress.com blog notifications in Zulip!

Support for self-installed blogs using software from <a href="">
[WordPress.org](http://wordpress.org) and the
[HookPress plugin](https://wordpress.org/plugins/hookpress/)
is experimental. For more details on the two, please see the
WordPress support page about
[the difference between WordPress.com and WordPress.org][1].

[1]: https://en.support.wordpress.com/com-vs-org/

Some actions are only available for self-installed blogs. For a
complete list of supported action types, please scroll to the
bottom of this page.

{!create-stream.md!}

{!create-bot-construct-url.md!}

***Important:** the HookPress plugin requires URL parameters to
be delimited by semicolons instead of ampersands. If you have a
self-installed blog, separate parameters with `;` instead of `&`.*

### Configuration

To configure a new webhook from WordPress, go to the **Webhooks**
page in the **Settings** section of your blog dashboard and click
**Add webhook**.

![](/static/images/integrations/wordpress/wordpress_hookpress.png)

If you have trouble locating the correct page on WordPress.com, you
can reach it by manually typing the URL in your browser address bar
as in this example:

`https://yourblogname.wordpress.com/wp-admin/options-general.php?page=webhooks`

Select the hook type **action** and the specific action that should
trigger this webhook notification. This example uses **publish_post**,
which is triggered when a new blog post is created.

The Zulip WordPress integration uses the fields **post_title**,
**post_type**, and **post_url** for a **publish_post** action,
so select those three fields in the list.

Next, for a WordPress.com blog, enter the URL created above for
the Zulip endpoint, making sure that the parameters in the URL
are delimited by `&`.

For a self-installed blog, enter the URL created above for the
Zulip endpoint, making sure that the parameters in the URL are
delimited by `;`

![](/static/images/integrations/wordpress/wordpress_configure_url.png)

When you are done, your configured webhook should look like this:

![](/static/images/integrations/wordpress/wordpress_config_done.png)

{!congrats.md!}

![](/static/images/integrations/wordpress/wordpress_post_created.png)

### Types of Actions

To configure other actions, choose a supported action from the
dropdown list and select the appropriate fields.

* publish_post
    * **Required Fields**: post_title, post_type, post_url
    * **Blog Type**: Both
* publish_page
    * **Required Fields**: post_title, post_type, post_url
    * **Blog Type**: Both
* user_register
    * **Required Fields**: display_name, user_email
    * **Blog Type**: Self-installed only
* wp_login
    * **Required Fields**: user_login
    * **Blog Type**: Self-installed only
