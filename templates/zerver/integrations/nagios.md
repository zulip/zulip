1.  {!create-channel.md!}

1.  {!download-python-bindings.md!}

1.  {!create-an-incoming-webhook.md!}

1.  Next, open `integrations/nagios/zuliprc.example` in your favorite
    editor, and change the following lines to specify the email address
    and API key for your Nagios bot, saving it to `/etc/nagios4/zuliprc`
    on your Nagios server:

    ```
    [api]
    email = NAGIOS_BOT_EMAIL_ADDRESS
    key = NAGIOS_BOT_API_KEY
    site = {{ api_url }}
    ```

1.  Copy `integrations/nagios/zulip_nagios.cfg` to `/etc/nagios4/conf.d`
    on your Nagios server.

1.  Finally, add `zulip` to the `members` list for one or more of the
    contact groups in the `CONTACT GROUPS` section of
    `/etc/nagios4/conf.d/contacts.cfg`, doing something like:

    ```
    define contactgroup {
        contactgroup_name       admins
        alias                   Nagios Administrators
        members                 monitoring, zulip
    }
    ```

1.  Once you’ve done that, reload your Nagios configuration using
    `/etc/init.d/nagios4 reload`.

1.  When your Nagios system makes an alert, you’ll see a message like the
    following, to the stream `nagios` (to change this, edit the arguments
    to `nagios-notify-zulip` in `/etc/nagios4/conf.d/zulip_nagios.cfg`)
    with a topic indicating the service with an issue.

{!congrats.md!}

![Nagios bot message](/static/images/integrations/nagios/001.png)

### Testing

If you have [external commands enabled in Nagios][1],
you can generate a test notice from your Nagios instance by
using the `Send custom service notification` command in the
`Service Commands` section of any individual service’s page
on your Nagios instance.

[1]: https://assets.nagios.com/downloads/nagioscore/docs/nagioscore/3/en/extcommands.html

### Troubleshooting

You can confirm whether you’ve correctly configured Nagios to run the
Zulip plugin by looking for `SERVICE NOTIFICATION` lines mentioning
zulip in `/var/log/nagios4/nagios.log`. You can confirm whether you’ve
configured the Zulip plugin code correctly by running
`/usr/local/share/zulip/integrations/nagios/nagios-notify-zulip`
directly.
