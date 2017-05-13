# View and edit your message drafts

When you close the compose box with content in it, Zulip stores the
content in a draft, so that you never lose your work and need to
retype a message.  Zulip's [Drafts](/#drafts) UI allows you to
retrieve, edit, and eventually send these drafts.

## View your drafts

To view a list of all your currently saved drafts, you can open the
[Drafts](/#drafts) modal by clicking the **Drafts** button on the left side of
the compose box located at the bottom of your window, clicking the **Drafts**
link located at the bottom-left corner of an open compose box, or pressing the
`d` key. Upon doing so, the **Drafts** modal will appear, displaying all of the
drafts you currently have, in the order that they were created.

![Drafts modal](/static/images/help/drafts-modal.png)

Each draft created from a discarded stream message is displayed with the
following information:

* **Stream** — If the discarded message that the draft was created from had a
specified stream, the draft will display the message's specified stream in the
top-left corner.

* **Topic** — If the discarded message that the draft was created from had a
specified topic, the draft will display the message's topic to the right of the
message's stream.

* **Content** — The content of the discarded message that the draft was created
from is displayed as the draft's content.

If a draft was created from a discarded private message instead of a stream
message, the private message's recipient(s) will be displayed in place of the
stream and topic.

!!! tip ""
    There are various [keyboard shortcuts](/help/keyboard-shortcuts#drafts) that
    allow you to easily navigate the **Drafts** modal and quickly
    clean up drafts you no longer want.

## Edit a draft

To edit the content of a draft, click the pencil (<i
class="icon-vector-pencil"></i>) icon or press the `Enter` key to open the
selected draft in the compose box, where you can change the contents of the
draft.

To save the changes you made to the draft, exit out of the compose box by
clicking the x (<i class="icon-vector-remove"></i>) or pressing the `Esc` key.

!!! warn ""
    **Note:** Drafts cannot be converted from one message type to another
    (stream to private message and vice versa). You can use copy-paste
    to transfer your content in this situation.

## Send a draft

Once you are ready to send a draft as a message, click the pencil (<i
class="icon-vector-pencil"></i>) icon or press the `Enter` key to open the
selected draft in the compose box. You can now send the draft as a message by
pressing the `Enter` key or clicking the **Send** button, depending on your
settings.

## Delete a draft

You can delete the selected draft by clicking the trash (<i
class="icon-vector-trash"></i>) icon or pressing the `Backspace` key.

!!! warn ""
    **Warning:** Discarded drafts cannot be retrieved, so please be careful
    while you are deleting drafts.
