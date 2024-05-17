Get Zulip notifications for your Groove events!

1. {!create-channel.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-integration-url.md!}

1. On your Groove dashboard, click on **Settings**. Under **Company**,
   click on **API**. Open the **Add Webhook** dropdown and select an
   event that you would like to be notified about.

    Currently, Zulip supports these events:

    * `ticket_started`: notify if there is a new ticket.
    * `ticket_assigned`: notify if a ticket is assigned to an agent or group.
    * `agent_replied`: notify if an agent replied to a ticket.
    * `customer_replied`: notify if a customer replied to a ticket.
    * `note_added`: notify if an agent left a note on a ticket.

1. Enter the URL constructed above in the space below the event.
   Click **Add Webhook**.

1. Repeat the last two steps (using the same URL) for every event you'd like
   to be notified about.

{!congrats.md!}

![](/static/images/integrations/groove/001.png)
