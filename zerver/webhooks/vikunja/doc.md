# Zulip Vikunja integration

Get Zulip notifications from your Vikunja projects and tasks!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

    Make sure to set the **Vikunja Host URL** to your Vikunja instance, so that links to your projects and tasks can be constructed.
    It is usually something like `https://vikunja.example.com`.

2. In Vikunja, choose a project (or parent project) you would like to connect to Zulip.
   In the project options dropdown select `Webhooks`.

3. Set **Target URL** to your earlier generated webhook URL.
   Select all events you would like to receive updates for.
   Click **Create Webhook**.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/vikunja/001.png)

### Supported Events
This integration is built for Vikunja 1.1. All task and project events currently provided by Vikunja are supported.

### Known limitations
- For most of the possible task interactions Vikunja triggers the `task.updated` event hook. The provided data does not contain information about the difference of values before and after the update. Therefore it is impossible to know what value has actually changed. That includes these attributes: Description, Status, Labels, Priority, Progress, Color, all dates, and the position in buckets.
Updating any of these will trigger a message containing all these pieces of information. They are placed in an expandable spoiler tag to not flood the message thread too much.

- Moving a task between buckets will trigger two messages, because Vikunja triggers the `task.updated` event twice. First when the old bucket information is removed. Then a second time, when the new bucket is added.

- Assigning users to tasks (and removing them) will trigger both `task.assignee.created` (or `task.assignee.deleted`) as well as `task.updated` and will therefore send two messages.

- Vikunja tasks and labels contain color information. Since it is not (yet) possible to style text with colors in Zulips markdown syntax, their colors will be mapped to the closest available colored circle emoji.


### Related documentation

- [Vikunja's webhooks documentation](https://vikunja.io/docs/webhooks/)

{!webhooks-url-specification.md!}

