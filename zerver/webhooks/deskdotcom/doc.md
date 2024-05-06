1. {!create-channel.md!}

    Keep in mind you still need to create the channel first even
    if you are using this recommendation.

1. {!create-an-incoming-webhook.md!}

1. Next, in Desk.com, open your **Admin** view via the top-left
    dropdown. In the **Admin** view, click on **Apps**, then
    click **Install** under **Custom Action**:

    ![](/static/images/integrations/desk/001.png)

1. From there, click **Install Custom Action** and accept the terms.
    Fill in the form like this:

     * **Name**: Zulip
     * **Authentication Method**: Basic Auth
     * **URL**: `{{ api_url }}/v1/external/deskdotcom`
     * **User name**: *your bot's user name, e.g.* `desk-bot@yourdomain.com`
     * **Password**: *your bot's API key*

    ![](/static/images/integrations/desk/002.png)

1. Click **Create** to save your settings. From the next screen, click
    **Add Action** to add a new action. You'll do this for every action
    you want a notification on Zulip for. (To add another action later,
    look for your custom action on the **Apps** page under
    **Installed Apps.**

    ![](/static/images/integrations/desk/003.png)

1. Let's say you want a notification each time a case is updated. Put
    in a descriptive name like **Announce case update**, select
    **POST a string to a URL** for **Action Type**, and copy-paste this
    to the **Appended URL path**:

    {% raw %}

    `?stream=desk&topic={{ case.id }}:+{{ case.subject }}`

    {% endraw %}

    The "appended URL path" will be the same for every notification —
    it makes sure the notification goes to the appropriate channel and topic
    within Zulip.

1. Next, copy this template Zulip message into **Message to POST**:

    {% raw %}

        Case [{{ case.id }}, {{ case.subject }}]({{ case.direct_url }}), was updated.

        * Status: {{ case.status.name }}
        * Priority: {{ case.priority }}
        * Customer: {{ customer.name }}
        * Company: {{ customer.company }}
        * Description: {{ case.description }}

    {% endraw %}

    You don't need to edit that, although you may if you wish. All the
    funny-looking stuff inside `{{ "{{" }}` and `{{ "}}" }}` will be filled in by
    Desk.com for each event. The dialog should look like this:

    ![](/static/images/integrations/desk/004.png)

1. Click **Add Action** to save, and then on the next screen, click the
    slider next to the action to enable it. This is important — actions are
    turned off by default!

    ![](/static/images/integrations/desk/005.png)

1. Now you need to create a rule that triggers this action. Desk.com's
    support center has a [lengthy article on rules][1], but in short,
    click on **Cases** up at the top, **Rules** on the left side, and
    then the specific event you want to notify on — in our example,
    **Inbound Interaction**.

    [1]: https://support.desk.com/customer/portal/articles/1376

    ![](/static/images/integrations/desk/006.png)

1. Select the types of interaction you want your rule to apply to,
    such as **Chat**. Specify the name and click on **Add Rule**.

    ![](/static/images/integrations/desk/007.png)

1. In the next screen, provide the details. First, click **Add Actions**
    to display the rule actions. Select **Trigger an App Action** in the
    dropdown, and then the name of the custom action you created earlier
    when the second dropdown appears. You can add additional **All** or
    **Any** conditions if desired. Also select when the rule should run
    (if not **Anytime**) and enable it.

    ![](/static/images/integrations/desk/008.png)

1. Finally, click **Update**.

{!congrats.md!}

![](/static/images/integrations/desk/009.png)

When a case is updated, you'll see a notification like the one above,
to the channel `desk`, with a topic that matches the case's subject name.
