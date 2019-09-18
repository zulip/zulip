Receive GoSquared notifications in Zulip!

1. {!create-stream.md!}

1. {!create-bot-construct-url-indented.md!}

1. In Grafana 
   Click **Menu** -> **Alerting** -> **Notification Channels**

1. Click the **+New Channel** button 

1. On the New Channel Form. Set **URL** to the URL constructed above. Set **Name** to
   a name of your choice, such as `Zulip`. Set **Send on all alerts** to **checked**. Set **Type** to **webhook** and **Http Method** to **POST** Click on **Save** button.

1. Now add alert and ensure that **Send to** has the name of channel created.

{!congrats.md!}

![](/static/images/integrations/grafana/001.png)
