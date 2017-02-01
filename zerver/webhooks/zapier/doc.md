### Get notifications from every event supported by Zapier.

{!create-stream.md!}

{!create-bot-construct-url.md!}

Next, create a ZAP, picking the service you'd like
to receive notifications from as **Trigger (Step 1)**

![](/static/images/integrations/zapier/001.png)

and **Webhook** as **Action (Step 2)**.

![](/static/images/integrations/zapier/002.png)

As **Step 2 Action** please choose `POST`:

![](/static/images/integrations/zapier/003.png)

Configure **Set up Webhooks by Zapier POST** as follows:

* `URL` is the webhook URL we created above
* `Payload Type` set to `JSON`

Finally, configure **Data**. You have to add 2 fields:

* `subject` is the field corresponding to the subject of a message
* `content` is the field corresponding to the content of a message

Example configuration:
![](/static/images/integrations/zapier/004.png)

{!congrats.md!}

![](/static/images/integrations/zapier/005.png)

### Weather Update with Zapier!

Sign into your Zapier account, then go to the URL
`https://zapier.com/app/explore`.

![](/static/images/integrations/zapier/006.png)

Choose the trigger app, **Weather by Zapier**.

![](/static/images/integrations/zapier/007.png)

Next, select the option **Today's Forecast**.

![](/static/images/integrations/zapier/008.png)

Fill in the latitude and longitude of your location.

Next, fill in your choice of units, Fahrenheit or Celsius.

![](/static/images/integrations/zapier/009.png)

Configure **Set up Webhooks by Zapier POST** as follows:

* `URL` is the webhook URL we created above
* `Payload Type` set to `JSON`

Finally, configure **Data**. You have to add 2 fields:

* `subject` is the field corresponding to the subject of a message
* `content` is the field corresponding to the content of a message

![](/static/images/integrations/zapier/010.png)

**Congratulations! You're done!**
