# Configure message editing and deletion

{!admin-only.md!}

There are several settings that control who can [edit and delete
messages](/help/edit-or-delete-a-message) and topics. By default,
users have 10 minutes after posting a message to edit it, they can
edit any topic at any time, and they cannot delete their messages.

Different organizations have different message editing needs, so this area
is highly configurable. Two things are true under any configuration:

* Message content can only ever be modified by the original author.
* Any message can be deleted at any time by an organization administrator.

<div class="centered_table"></div>
|                                       | Admins   | Members |
|---                                    |---       |---      |
| Edit your message content             | [1]      | [1]     |
| Edit others' message content          |          |         |
| Edit your message topics              | [1]      | [1]     |
| Add topic to messages without a topic | [1]      | [1]     |
| Edit others' message topics           | [1]      | [2]     |
| Move topics between streams           | [3]      | [3]     |
| Delete your messages                  | &#10004; | [4]     |
| Delete others' messages               | &#10004; |         |

[1] Controlled by **Allow message editing**.

[2] Controlled by **Who can edit topic of any message**.

[3] Controlled by **Who can move messages between streams**, in
addition to other restrictions on editing topics.

[4] Controlled by **Who can delete their own messages**
and **Time limit for deleting messages**.

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

## Configure message editing and deletion

{start_tabs}

{settings_tab|organization-permissions}

1. Under **Message editing**, configure:

    - **Allow message editing**
    - **Who can edit topic of any message**
    - **Who can delete their own messages**
    - **Time limit for deleting messages**

{!save-changes.md!}

{end_tabs}

## Configure who can move topics between streams

You can configure which [roles](/help/roles-and-permissions)
have permission to move topics between streams.

{start_tabs}

{settings_tab|organization-permissions}

1. Under **Message editing**, configure
   **Who can move messages between streams**.

{!save-changes.md!}

{end_tabs}

## Related articles

* [Disable message edit history](/help/disable-message-edit-history)
* [Configure message retention policy](/help/message-retention-policy)
* [Move content to another stream](/help/move-content-to-another-stream)
* [Rename a topic](/help/rename-a-topic)
* [Restrict topic editing](/help/configure-who-can-edit-topics)
