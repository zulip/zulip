Zulip supports integration with Papertrail as a
[Webhook](http://www.perforce.com/perforce/doc.current/manuals/p4sag/chapter.scripting.html)
that fires upon finding a certain log. To do this:

{!create-stream.md!}

{!create-bot-construct-url.md!}

Next, log into your Papertrail Account and browse through
your logs. Search for logs you want to get alerts for and press
**Save Search** to open up a modal window, then fill out the
details and press the **Save & Setup an Alert** button.

![](/static/images/integrations/papertrail/000.png)

![](/static/images/integrations/papertrail/001.png)

Go to the **Create an alert** section, press the **Webhooks**
link and place the URL created above into the **Webhook URL**
section. Be sure to set the frequency to either minute, hour or
day.

![](/static/images/integrations/papertrail/002.png)

{!congrats.md!}

![](/static/images/integrations/papertrail/003.png)
