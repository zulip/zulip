{!create-stream.md!}

{!create-bot-construct-url.md!}

{!append-topic.md!}

Make sure to specify the topic in the URL above. Otherwise, the
default topic `General` will be used.

Remember to URL-encode the stream and topic names in the above
URL. Spaces need to be replaced with `%20`. For instance, if
you want your stream to be called "My awesome project", it
should be encoded as `My%20awesome%20project`.

Since Taiga allows you to integrate services on a per project
basis, you have to perform the following steps for *every project*
that you want to send notifications to Zulip.

1. Go to **Admin** > **Integration** > **Webhooks** menu.

2. Click **Add a new webhook**.

3. Fill out the form by following the instructions:
    * **Name** - to recognize this service, preferably `Zulip`
    * **URL** - the URL we created above
    * **Secret key** - once again the bot API key created in Zulip

4. Click **Save** once you've finished filling out the form.

{!congrats.md!}

![](/static/images/integrations/taiga/001.png)

There are **two different ways** you may want to consider
when organizing your Taiga - Zulip integration:

* Use a separate Zulip stream for Taiga messages - name it `taiga`
  (as recommended above). For every integrated project, provide a
  new topic in the URL as described above.

* If you already have a Zulip stream for managing a project,
  you can also use this existing stream and provide `Taiga`
  as the topic in the URL.
