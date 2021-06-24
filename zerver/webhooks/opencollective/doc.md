This integration currently supports getting
notifications in your Zulip Stream, when a new
member signs-up in an Open Collective page.

In order to do that follow these steps:<br/>

1. Create a Stream to get notifications<br/>
2. Go to Settings and create an incoming webhook bot.<br/>
Construct the URL for the  bot using the API key and
stream name:<br/>
'https://yourZulipDomain.zulipchat.com/api/v1/external/opencollective?api_key=abcdefgh&stream=stream%20name'<br/>

If you do not specify a stream, the bot will send notifications via PMs to the creator of the bot.<br/>

If you'd like this integration to always send to a specific topic, just include the (URL-encoded) topic
as an additional parameter (E.g. for your topic, append &topic=your%20topic to the URL).<br/>

3. Go to [Open Collective Website](https://opencollective.com/), find
your desired collective page go to *Settings* -> *Webhooks* paste the
bot URL and choose *Activity* -> *New Member*<br/>

{!congrats.md!}<br/>

In the future this integration can be developed in order to
support other types of *Activity* such as *New Transaction*, *Subscription Canceled* etc. <br/>

![](/static/images/integrations/opencollective/001.png)
