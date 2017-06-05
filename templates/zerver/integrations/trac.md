First, create the stream you’d like to use for Trac notifications, and
subscribe all interested parties to this stream. The integration will
use the default stream `trac` if no stream is supplied in the hook;
you still need to create the stream even if you are using this
default.

{! download-python-bindings.md !}

Next, open `integrations/trac/zulip_trac_config.py` in your favorite
editor, and change the following lines to specify your bot’s email
address, API key, and where you’d like your notification messages to
go (by default, stream `trac`):

```
ZULIP_USER = "trac-notifications-bot@example.com"
ZULIP_API_KEY = "0123456789abcdef0123456789abcdef"
STREAM_FOR_NOTIFICATIONS = "trac"
TRAC_BASE_TICKET_URL = "https://trac.example.com/ticket"
{% if api_site_required %}ZULIP_SITE ="{{ external_api_uri_subdomain }}"{% endif %}
```

Copy `integrations/trac/zulip_trac.py` and
`integrations/trac/zulip_trac_config.py` into your Trac installation’s
`plugins/` subdirectory. Once you’ve done that, edit your Trac
installation’s `conf/trac.ini` to add `zulip_trac` to the
`[components]` section, as follows:

```bash
[components]
zulip_trac = enabled
```

You may then need to restart Trac (or Apache) so that Trac will load
our plugin.

When people open new tickets (or edit existing tickets), you’ll see a
message like the following, to the stream `trac` (or whatever you
configured above) with a topic that matches the ticket name

{! congrats.md !}

![](/static/images/integrations/trac/001.png)

**Additional trac configuration**

After using the plugin for a while, you may want to customize which
changes to tickets result in a Zulip notification using the
`TRAC_NOTIFY_FIELDS` setting in `zulip_trac_config.py`.
