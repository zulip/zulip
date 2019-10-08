# Configure message editing and deletion

{!admin-only.md!}

There are several settings that control who can edit and delete messages and
topics. By default, users have 10 minutes after posting a message to edit
it, they can edit any topic at any time, and they cannot delete their
messages.

Different organizations have different message editing needs, so this area
is highly configurable. Two things are true under any configuration:

* Message content can only ever be modified by the original author.
* Any message can be deleted at any time by an organization administrator.

|                                    | Admins   | Members |
|---                                 |---       |---      |
| Edit your message content          | [1]      | [1]     |
| Edit others' message content       |          |         |
| Edit your message topics           | [1]      | [1]     |
| Add a topic to a topicless message | [1]      | [1]     |
| Edit others' message topics        | [1]      | [1, 2]  |
| Delete your messages               | &#10004; | [3]     |
| Delete others' messages            | &#10004; |         |

[1] Controlled by **Allow message editing**.

[2] Controlled by **Users can edit the topic of any message**.

[3] Controlled by **Allow message deleting**.

There are a few useful things to understand about the message editing
settings.

* **Allow message editing** can be set to **Never**, **Any time** or
  **Up to [a customizable time limit] after posting**. If set to **Never**,
  users cannot edit message topics either. For any other value, users can
  edit message topics at any time.

* If a user can edit a message, they can also "delete" it by removing all
  the message content. This is different from proper message deletion in two
  ways: the original content will still show up in
  [message edit history](view-a-messages-edit-history), and will be included
  in [exports](/help/export-your-organization). Deletion
  permanently (and irretrievably) removes the message from Zulip.

You can access the message editing and deletion settings as follows.

{settings_tab|organization-settings}

4. Under **Message editing**, configure **Allow message editing**,
   **Users can edit the topic of any message**, and **Allow message deleting**.

{!save-changes.md!}

## Related articles

* [Disable message edit history](/help/disable-message-edit-history)
