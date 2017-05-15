Receive user reviews from your tracked apps on AppFolllow in Zulip
using the Zulip AppFollow plugin!

First, create the stream you'd like to use for AppFollow notifications, and
subscribe all interested parties to this stream. We recommend the
name `appfollow`.

Next, on your {{ settings_html|safe }}, create an AppFollow bot.

Then, log into your account on [appfollow.io](http://appfollow.io), and:

1. Click on the app for which you'd like to receive reviews.
   Click on **Integrations** and then go to the **Others** tab.
   ![](/static/images/integrations/appfollow/001.png)

2. In the Webhook URL field, enter the following URL, replacing the bot API key
   and Zulip stream with the appropriate information.
   `{{ external_api_uri_subdomain }}/v1/external/appfollow?api_key=test_api_key&stream=appfollow`

3. **Save changes** – all done!

New reviews for your app will be delivered to your Zulip stream.

![](/static/images/integrations/appfollow/002.png)
