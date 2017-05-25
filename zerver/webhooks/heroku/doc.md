Receive notifications in Zulip whenever a new version of an app
is pushed to Heroku using the Zulip Heroku plugin!

{!create-stream.md!}

{!create-bot-construct-url.md!}

Then, log into your account on [Heroku](http://heroku.com), and

1. Visit the page for the project for which you'd like to generate
   Zulip notifications. Click the **Resources** tab, and add the
   **Deploy Hooks** addon. Choose the **HTTP Post Hook** plan, and
   click **Provision**.
   ![](/static/images/integrations/heroku/001.png)

2. Click on the **Deploy Hooks** add-on that you just added.
   You should be redirected to a page that looks like this:
   ![](/static/images/integrations/heroku/002.png)

3. Enter the webhook URL created earlier, replacing the bot API
   key and Zulip stream with the appropriate information.

{!congrats.md!}

![](/static/images/integrations/heroku/003.png)

When you deploy to Heroku, the team can see these updates in
real time in Zulip.
