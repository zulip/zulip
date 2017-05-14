Get Zulip notifications for your Airbrake bug tracker!

First, create the stream you'd like to use for Airbrake notifications, and
subscribe all interested parties to this stream. We recommend the
name `airbrake`.

Next, on your {{ settings_html|safe }}, create an Airbrake bot. Construct the
URL for the Airbrake bot using the API key and stream name:

`{{ external_api_uri_subdomain }}/v1/external/airbrake?api_key=abcdefgh&stream=airbrake`


Now, go to your project's settings on the Airbrake site. Click
on the `Integration` section. Choose `Webhook`, provide the above URL,
check `Enabled`, and save. Your Webhook configuration should look similar to:

![](/static/images/integrations/airbrake/001.png)

**Congratulations! You're done!**

Your messages may look like:

![](/static/images/integrations/airbrake/002.png)
