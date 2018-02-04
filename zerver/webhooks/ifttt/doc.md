Get notifications from every event supported by IFTTT.

{!create-stream.md!}

{!create-bot-construct-url.md!}

Next, create an IFTTT recipe, picking the service you'd like
to receive notifications from as `this`, and `Maker` as `that`.

![](/static/images/integrations/ifttt/001.png)

Choose the `Make a web request` action, and configure it as
follows:

1. `URL` is the URL we created above

2. `method` is POST

3. `Content Type` is `application/json`

Finally, configure the request body. You need to construct a JSON
object with two parameters: `content` and `subject`.

Example:

`{"content": "message content", "subject": "message subject"}`

You will most likely want to specify some IFTTT **Ingredients**
(click the beaker to see the available options) to customize
the subject and content of your messages; the below screenshot
uses ingredients available if `this` is IFTTT's incoming email
service.

Example configuration:

![](/static/images/integrations/ifttt/002.png)

{!congrats.md!}

![](/static/images/integrations/ifttt/003.png)
