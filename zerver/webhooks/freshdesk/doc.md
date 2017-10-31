See customer support interactions right in Zulip, with our Freshdesk
integration! Note that this integration must be set up by an
administrator for your Freshdesk instance.

{!create-stream.md!}

Next, on your {{ settings_html|safe }}, create a Freshdesk bot.

Now we can set up the Freshdesk events that will trigger Zulip's.
Freshdesk provides separate triggering mechanisms for ticket
creation and ticket changes, so we'll set up these triggers in two
parts.

### Part 1: Zulip notifications for new Freshdesk tickets

1. Visit your Freshdesk admin page. Under the **Helpdesk Productivity**
   section, click the **Dispatch'r** icon:
   ![](/static/images/integrations/freshdesk/001.png)

2. Click the **New rule** button to create a new Dispatch'r rule that
   will send notifications to Zulip when Freshdesk tickets are opened.

3. On the Dispatch'r rule creation page, give the rule a name and
   description. Next, we need to specify the conditions under which to
   trigger Zulip notifications. There isn't a shortcut for "always
   generate a notification on ticket creation", so we'll instead fake it
   by picking two complementary conditions: when the source **is email**,
   and when the source **is not email**:
   ![](/static/images/integrations/freshdesk/002.png)

4. In the **Action** section, add a new action of type **Trigger Webhook**.
   Set the **Request Type** to **POST**. Set the following **Callback URL**,
   replacing the Zulip stream with your desired stream:
   `{{ api_url }}/v1/external/freshdesk?stream=freshdesk`

5. Check the **Requires Authentication** box, and supply the bot email
   address and API key. The **Action** section should look like this so
   far:
   ![](/static/images/integrations/freshdesk/003.png)

6. Select **JSON** for the **Encoding**. Under the encoding, select
   **Advanced**. Paste the following JSON into the **Content** box:
```
{"freshdesk_webhook":
{
    "triggered_event":"&#123;&#123;triggered_event&#125;&#125;",
    "ticket_id":"&#123;&#123;ticket.id&#125;&#125;",
    "ticket_url":"&#123;&#123;ticket.url&#125;&#125;",
    "ticket_type":"&#123;&#123;ticket.ticket_type&#125;&#125;",
    "ticket_subject":"&#123;&#123;ticket.subject&#125;&#125;",
    "ticket_description":"&#123;&#123;ticket.description&#125;&#125;",
    "ticket_status":"&#123;&#123;ticket.status&#125;&#125;",
    "ticket_priority":"&#123;&#123;ticket.priority&#125;&#125;",
    "requester_name":"&#123;&#123;ticket.requester.name&#125;&#125;",
    "requester_email":"&#123;&#123;ticket.requester.email&#125;&#125;",
}
}
```

These ticket details are what will be forwarded to Zulip. The
pasted JSON should look like this:

![](/static/images/integrations/freshdesk/004.png)

Lastly, save your new Dispatch'r rule. The next time a Freshdesk ticket
is opened, the team will get a notification in Zulip!

If you only want to receive Zulip notifications on ticket creation,
stop here, you're done! If you also want notifications on important ticket
changes, please continue to the next section.

### Part 2: Zulip notifications on ticket changes

1. Visit your Freshdesk admin page. Under the **Helpdesk Productivity**
   section, click the **Observer** icon:
   ![](/static/images/integrations/freshdesk/005.png)

2. Click the **New rule** button to create a new Observer rule that will
   send notifications to Zulip when Freshdesk tickets are updated.

3. On the Observer rule creation page, give the rule a name and
   description. Under **When Any Of These Events Occur**, create
   these new rules:
    * Priority is changed, from Any Priority, to Any Priority
    * Status is changed, from Any Status, to Any Status
    * Note is added, Type Any

4. If you do not want to receive Zulip notifications on one or more of
   these events, leave out the rule for that event.

5. Under **And The Events Are Performed By**, select **Anyone**.
   So far, the rule should look like this:
   ![](/static/images/integrations/freshdesk/006.png)

6. Next, we need to specify the types of tickets that will trigger
   Zulip notifications. There isn't a shortcut for "always generate a
   notification on ticket update", so as before we'll instead fake it by
   picking two complementary conditions: when the source **is email**,
   and when the source **is not email**:
   ![](/static/images/integrations/freshdesk/007.png)

7. Under **Perform These Actions**, add a new action of type
   **Trigger Webhook**. Set the **Request Type** to **POST**. Set the
   following **Callback URL**, replacing the Zulip stream with your
   desired stream:
   `{{ api_url }}/v1/external/freshdesk?stream=freshdesk`

8. Check the **Requires Authentication** box, and supply the bot e-mail
   address and API key. The Action section should look like this so far:
   ![](/static/images/integrations/freshdesk/008.png)

9. Select **JSON** for the **Encoding**. Under the encoding, select
   **Advanced**. Paste the following JSON into the **Content** box:

```
{"freshdesk_webhook":
    {
        "triggered_event":"&#123;&#123;triggered_event&#125;&#125;",
        "ticket_id":"&#123;&#123;ticket.id&#125;&#125;",
        "ticket_url":"&#123;&#123;ticket.url&#125;&#125;",
        "ticket_type":"&#123;&#123;ticket.ticket_type&#125;&#125;",
        "ticket_subject":"&#123;&#123;ticket.subject&#125;&#125;",
        "ticket_description":"&#123;&#123;ticket.description&#125;&#125;",
        "ticket_status":"&#123;&#123;ticket.status&#125;&#125;",
        "ticket_priority":"&#123;&#123;ticket.priority&#125;&#125;",
        "requester_name":"&#123;&#123;ticket.requester.name&#125;&#125;",
        "requester_email":"&#123;&#123;ticket.requester.email&#125;&#125;",
    }
}
```

These ticket details are what will be forwarded to Zulip. The
pasted JSON should look like this:

![](/static/images/integrations/freshdesk/009.png)

Finally, save your new Observer rule. The next time a Freshdesk
ticket is updated, the team will get a notification in Zulip!

{!congrats.md!}

![](/static/images/integrations/freshdesk/010.png)
