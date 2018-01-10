Zulip supports integration with Groove and can notify you of any events
happening on your Groove dashboard.

1. {!create-stream.md!}

2. {!create-bot-construct-url-indented.md!}

3. Next, on your Groove dashboard, go to the **Settings** tab

    ![](/static/images/integrations/groove/001.png)

4. From there, go to the **API** menu under **Company**.

    ![](/static/images/integrations/groove/002.png)

5. On the **Webhooks** option, open the **Add Webhook**
   dropdown and select the event that you wish to be notified of.

    ![](/static/images/integrations/groove/003.png)

    Currently, Zulip supports these events:

    * ―`ticket_started`: notify if there is a new ticket.
    * ―`ticket_assigned`: notify if a ticket is assigned to an agent or group.
    * ―`agent_replied`: notify if an agent replied to a ticket.
    * ―`customer_replied`: notify if a customer replied to a ticket.
    * ―`note_added`: notify if an agent left a note on a ticket.

6. Copy your webhook URL to the space below the event.

    ![](/static/images/integrations/groove/004.png)

7. Click **Add Webhook**.

{!congrats.md!}

![](/static/images/integrations/groove/005.png)
