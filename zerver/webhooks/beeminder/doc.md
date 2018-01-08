Get Beeminder notifications in Zulip whenever you're going to derail from your goal!

{!create-stream.md!}

The webhook URL should look like:

`{{api_url}}?api_key=BOT'S_API_KEY&email=foo@example.com`

Modify the parameters of the URL above where `api_key` is the API key of your Zulip bot
and `email` is your Zulip email.

* When creating or editing a goal in Beeminder, you can check the **Make private** option to make sure
the bot sends you private messages; otherwise, the bot will send messages to a public stream.

![](/static/images/integrations/beeminder/001.png)

* Copy the above URL and paste it in the `WEBHOOK` input option in the `reminders`
setting of your Beeminder account.

![](/static/images/integrations/beeminder/002.png)

{!congrats.md!}

![](/static/images/integrations/beeminder/003.png)
