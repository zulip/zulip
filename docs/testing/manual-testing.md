# Manual testing

As a general rule, we like to have automated tests for everything that
can be practically tested. However, there are certain types of bugs
that are best caught with old fashioned manual testing (also called
manual QA). Manual testing not only catches bugs, but it also helps
developers learn more about the system and think about the existing
semantics of a feature they're working on.

This doc assumes you know how to set up a local development server
and open the Zulip app in the browser. It also assumes a basic
knowledge of how to use Zulip.

## Basic stuff

When testing Zulip manually, here are things to focus on:

- The best bugs to catch are security/permissions bugs.
- Don't rush manual testing. Look for small details like
  display glitches.
- Always test with multiple users (you can use incognito windows
  to facilitate this).
- Always keep the inspector console open and watch for warnings
  or errors.
- Be methodical about collecting information on bugs. (You will
  eventually want to create tickets, but you may want to consolidate
  your own notes before filing tickets.)

You generally want to test with Cordelia as the primary user,
and use Hamlet as her primary conversation partner. Use Iago
when you need to test administrative functions. Send messages
to Othello or Prospero if you want to verify things such as
Cordelia not being able to receive messages not intended for her.

The rest of this document groups tasks into basic areas of
functionality of the system. If you have multiple people testing
at once, you can divvy up QA tasks by these sections in the doc.

### Message view

We mostly test the message view as part of testing everything
else, but there are few things to specially test here.

Try using all the navigation hotkeys:

- Up/k
- Down/j
- PgUp/K
- PgDn/J/Spacebar
- End (or fn-right-arrow on OSX)
- also try scrolling aggressively with the mouse

Try narrowing from the message view:

- Hotkeys
  - use a to go to Combined feed
  - use s to narrow to a stream (select message first
    and verify in sidebar)
  - use S to narrow to the topic (and verify in sidebar)
  - use v to navigate to direct messages
- Click on the recipient bar
  - narrow to a stream
  - narrow to a topic
  - narrow to direct messages with one user
  - narrow to a group direct message
- Click on the Zulip logo
  - narrow to a topic
  - click on the Zulip logo (and verify you're in the Recent conversations view)

### Messagebox

With messagebox we want to test mainly the functioning of all
all the keyboard shortcuts and click handlers.

Apart from that there are three views of a message box, we want
to test their appearance too:

- Message that includes sender
- Message without the sender
- "/me" message

Here's how we're going to test the message appearances:

- narrow to a new topic and send a message (this message will include sender)
  - edit the message ("EDITED" label should appear beside sender name)
- send another message (will not include sender)
  - edit the message ("EDITED" label should appear in the left column, where the avatar is)
- send a "/me" message (`/me test message`)
  - message should appear alongside sender name
  - edit the message ("EDITED" label should appear beside the message)

For all the three cases, we need to test the click handlers and
the hotkeys too:

- Sender popover:
  - click on the avatar and sender name for messages which include sender
  - press 'u' to open the sender popover for all messages
- Message reply:
  - click on message to reply
  - use 'r' or Return hotkey to reply
  - use '>' to quote and reply
  - use '@' to mention and reply
- Reactions:
  - click on the reactions button to open menu
  - use ':' to open the reactions menu
  - react to a message
- Chevron
  - click on chevron to open menu
  - use 'i' to open chevron menu
- Message edit
  - click on message edit/view source button
  - use 'i' + Return to edit/view source message
  - click on the 'copy and close' option in view source and verify positioning of 'Copied!' label.
- Star a message:
  - click on the star button in the right column
  - use 'Ctrl + S' to star a message
- Message length
  - send a long message and see if 'Show more' button appears
  - click on the 'more' or 'collapse' link
  - use i to collapse/expand a message irrespective of message length
- use 'v' to show all images in the thread
- use 'M' to mute the thread

Play with the screen size to check if the messagebox appears
fine in different screens too.

### Message editing

With message editing we mainly want to exercise topic changes.

Here are some tasks:

- Do lots of editing

  - send a message to the topic "original"
  - edit the message content
  - send two messages to the "original" stream
  - start to edit a message but then cancel
  - change the topic for the first message to "change1" (just
    this message)
  - narrow back to "original"
  - send one more message to the stream
  - change the topic for the last two messages to "change2"
  - narrow back to "original"
  - send two more messages to the stream
  - edit the 2nd message on topic and change all messages to
    "change3"

- Test UI entry points
  - hit "i" then down arrow to edit with the popup
  - use the popup using the mouse
  - enter edit mode using the pencil icon

### Narrowing

Zulip uses the term "narrowing" to refer to opening different views
of your messages, whether by clicking on sidebar options, recipient
bars, or by using search. The main focus of these tasks should
be watching unread counts. Of course, you also want to see messages
show up in the message pane. And, finally, you should make sure
that no messages outside the narrow show up in Cordelia's view.

:::{important}
Make sure that Cordelia is subscribed to Verona but not
subscribed to Denmark; if not, you should use different streams
for your testing.
:::

When testing narrows, you want to have Hamlet send the same message
several times in a row, while cycling Cordelia through various narrows.

Here are the main tasks for Hamlet (and each message gets sent several
times):

- Send Cordelia/Othello a direct message.
- Send Cordelia a direct message.
- Send Othello a direct message.
- Post to Verona/foo.
- Post to Verona/bar.
- Post to Denmark/foo.
- Post to Denmark/foo and mention Cordelia.

For each of the above types of messages, you will want to cycle
through the following views for Cordelia (and have Hamlet send new
messages after each narrow):

- Go to Combined feed view.
- Go to Direct message feed view.
- Go to Direct messages w/Hamlet.
- Go to Direct messages w/Hamlet and Othello.
- Go to Verona view.
- Go to Verona/bar view.
- Go to Verona/foo view.
- Go to Denmark view.
- Go to Denmark/foo view.

There are 56 things to test here. If you can get into a rhythm
where you can test each case in about 30 seconds, then the whole
exercise is about 30 minutes, assuming no bugs.

### Composing messages

We have pretty good automated tests for our Markdown processor, so
manual testing is targeted more to other interactions. For composing
a message, pay attention to details like what is automatically
populated and where the focus is placed.

- Hotkeys

  - use r to reply to a stream message
  - use r to reply to a direct message
  - use R to reply to the author of a direct message
  - use R to reply to the author of a direct message stream
  - use c to compose a stream message
  - use x to compose a new direct message

- Buttons

  - Narrow to a stream and click on "New topic"
  - Narrow to "Direct message feed" and click on "New topic"
  - Narrow to a stream and click on "New direct message"
  - Narrow to "Direct message feed" and click on "New direct message"

- Topics

  - Compose/send a message to a stream with no topic.
  - Compose/send a message to a stream with a new topic.
  - Compose/send a message to a stream with autocomplete.
  - Compose/send a message to a stream manually typing an
    existing topic.

- Formatting stuff

  - Use the "A" icon to get Markdown help.
  - Use the eyeball icon to show a preview and send from preview mode.
  - Toggle in and out of preview before sending a message.
  - Use @-mention to mention Hamlet (and send him a message).
  - Use `#**devel**` syntax and send to Hamlet, then follow the link.
  - Create a bulleted list.
  - Use the emoji icon to find an emoji in the picker.

- Attachments

  - Send a message with an attachment using the paperclip icon.
  - Send a message with multiple attachments.
  - Copy an image from the clipboard.
  - Use drag/drop from the desktop to upload an image.

- Drafts

  - Start composing a message then click outside the compose box.
  - Use "restore drafts" to restore the draft.
  - Start composing then use "Esc" to abort the message.
  - Use "restore drafts" to restore the draft.
  - Start composing a stream message and then abort using
    the little "x" icon in the compose box.
  - Click on "New direct message" and restore the draft. (You
    should now be sending to a stream.)

- Click to send
  - Turn off Enter-to-send.
    - Send a two-paragraph message using Tab and Enter.
    - Send a two-paragraph message using Ctrl-Enter or Cmd-Enter.
  - Turn on Enter-to-send.
    - Hit Enter to send.

### Popover menus

For this task you just want to go through all of our popover menus
and exercise them. The main nuance here is that you occasionally want
to click somewhere on the UI outside of an existing popover to see if
the popover menu is "too sticky." Also, occasionally actions will be
somewhat jarring; for example, if you mute a message in the current view,
then the message will disappear from the view.

Here are the things to test:

- Stream sidebar menus (click ellipsis when hovering over stream filters)

  - Stream settings (just make sure it goes there)
  - Narrow (and then have Hamlet send a message)
  - Pin/unpin (do both)
  - Compose (send a message to the stream)
  - Mark as read (scroll back and then have Hamlet send you a message)
  - Mute/unmute (do both)
  - Unsubscribe (and then go to Stream settings in the gear menu to resubscribe)
  - Choose custom color (play around with this)

- Topic sidebar menus (click ellipsis when hovering over topics)

  - Narrow (and then have Hamlet send a message)
  - Mute/unmute (try both)
  - Mark as read (scroll back and then have Hamlet send you a message)

- Left-message-pane menus (click on person's name)

  - Verify email
  - Verify date message sent
  - Send a direct message (make sure compose box is filled out ok)
  - Narrow to direct messages with
  - Narrow to direct messages sent by

- Right-pane-pane menus (click on chevron when hovering)

  - use "i" hotkey to open the menu
  - Edit a message you sent (using the down-arrow key to navigate the popup)
  - View Source for somebody else's message (make sure
    it's not editable)
  - Reply (send a message)
  - Collapse/uncollapse (try both)
  - Mute/unmute (try both, watch left sidebar)
  - Link to this conversation

- Buddy list menus (click ellipsis when hovering over users)
  - Narrow to direct messages with
  - Narrow to message sent by
  - Compose a message to

### Sidebar filtering

This is a fairly quick task where we test the search filters on the left sidebar
and the buddy list. If Cordelia is not subscribed to Denmark, subscribe her to
that stream.

- Streams filtering

  - Use "w" hotkey to open the search.
  - Filter on "d".
  - Pin/unpin Denmark.
  - Clear filter.
  - Use "A" and "D" hotkeys to cycle through the streams.
  - Filter again and then click somewhere else.

- Buddy list filtering
  - Use "q" hotkey to open the search.
  - Filter for Hamlet, Prospero, Othello, etc.
  - Log on Hamlet and log off Hamlet while filtering for Hamlet.
  - Log on/log off Hamlet while filtering for Othello.
  - Log on/log off Hamlet while not filtering at all.
  - Filter again and then click somewhere else.

### Stream permissions

This is an important category to test, because we obviously do not
want to have bugs where people can read messages on streams they
should not have access to.

The general flow here is for Hamlet to create the streams and verify
that Cordelia has the correct visibility to them.

First, we start off with "positive" tests.

- Positive tests
  - Have Hamlet create a public stream w/Cordelia subscribed and
    have him post a message to the stream.
  - Have Hamlet create a public stream without Cordelia and then...
    - Have Hamlet post to the stream.
    - Have Cordelia subscribe to the stream.
    - Verify Cordelia can see the previous message.
    - Have Cordelia post a message to the stream.
  - Have Hamlet create a private stream with Cordelia
    invited and test a two-way conversation between the two
    users.

For negative tests, we want to dig a little deeper to find back
doors for Cordelia to access the stream. Here are some techniques
to try:

- Try to have her compose a message to the stream by
  circumventing autocomplete.
- Try to have her narrow to the stream using stream:foo
  in search.
- Go to stream settings and see if the stream shows up.

For public streams, it's ok for Cordelia to know the stream exists,
and she can subsequently subscribe. For private streams, she should
not even know they exist (until she's invited, of course).

- Negative tests
  - Have Hamlet create a public stream without inviting Cordelia.
    - Verify Cordelia can see the stream in her settings.
    - Verify Cordelia can't compose a message to the stream.
    - Verify that Cordelia sees nothing when Hamlet posts to
      the stream.
  - Have Hamlet create a public stream with Cordelia, but then
    have Iago revoke her subscription using the admin page.
    - Verify that the stream appears in Cordelia's left sidebar
      and then goes away.
    - Try to have Cordelia view the stream using a sneaky
      search along the lines of `stream:foo`.
  - Have Hamlet create a private stream without inviting Cordelia.
    - Verify Cordelia can't compose a message to the stream.

### Search

The main task for testing search is to play around with search
suggestions (autocomplete). Once you select an option, verify the
message view is consistent with the search and that the left sidebar
reflects the current narrow. If a search comes up legitimately
empty, have Hamlet send a message that matches the search.

Here are searches you should be able to do with autocomplete:

- stream:design
- stream:Verona topic:Verona1
- stream:Verona keyword
- sent by me
- @-mentions
- starred messages
- messages sent by Hamlet
- direct messages with Hamlet
- direct messages with Hamlet matching keyword "foo"

There are some things you can try that don't come up in autocomplete:

- -stream:Verona (exclude Verona)
- stream:Verona stream:devel (should return no results)

Miscellaneous:

- Use the "/" hotkey to start a search.
- Use the "x" icon to clear a search.
- Use the "Esc" hotkey to clear a search.

### Stream settings

Test various UI entry points into stream settings:

- Use small gear menu in left sidebar, then filter to "devel".
- Use popover menu in left sidebar next to "devel".
- Use gear menu above buddy list and filter to "devel".
- Use gear menu and click on "devel."
- Use gear menu and then click on chevron menu next to "devel."
  (I'm not sure why we still have the chevron at this writing.)

Create new public stream "public1" and add Hamlet:

- Type "public1" in the text box and then click "Create new stream."
- Select "People must be invited" and then verify you can't
  select "Announce new stream in #[announcement stream]".
- Select "Anyone can join" again to make it be public.
- Check the checkbox for Hamlet.
- Hit the "Create" button.

Test subscribe/unsubscribe:

- Log in as Hamlet and go to his stream settings.
- As Cordelia, unsubscribe from "public1" using the checkmark in the
  stream settings page.
- Verify that Hamlet sees that Cordelia has unsubscribed (and the
  subscriber count should decrement).
- As Cordelia, resubscribe to "public1."
- Verify Hamlet sees that change.

As Cordelia, exercise different options in Create Stream
dialog by creating streams s1, s2, s3, etc.:

- s1: anyone can join, announce it, and add Hamlet using filter feature
- s2: people must be invited
- s3: anyone can join, don't announce
- s4: check all, then uncheck all, then invite only Hamlet
- s5: invite everybody but Hamlet
- s6:
  - create the stream as public, but don't subscribe anybody initially
  - then click on stream options to add Hamlet using "Add" button

Test per-stream options:

- Use "devel" stream and send a message to it
- Do mute and unmute, have Hamlet send messages
- Test notifications on/off, have Hamlet send messages
- Test pin and unpin, view left sidebar
- Change stream color, and then view the left sidebar and the All
  messages view
- Verify stream subscriber counts in the main stream view

### User settings

You can modify per-user settings by choosing "Settings" in the gear menu.
Do these tasks as Cordelia.

- Your account
  - Change full name (Hamlet should see the name change)
  - Customize profile picture
  - Deactivate account (and then log in as Iago to re-activate Cordelia)
- Preferences
  - Right now, these unfortunately require reloads to take effect.
  - Default language (change to Spanish)
  - 24-hour time (and then test going back to AM/PM)
- Notifications
  - Stream message
    - turn off notifications at user level
      - create a new stream
      - have Hamlet send a message
    - turn on notifications at user level
      - create a new stream
      - have Hamlet send a message
      - then turn off notifications for that stream
      - have Hamlet send another message
  - Direct messages and @-mentions
    - Test Desktop/Audible options
    - You can ignore other stuff for now
- Bots/API key
  - Create a bot with a generic avatar and send it a direct message
  - Create a bot with a custom avatar and send it a direct message
  - Change your API key
- Alert words
  - Create an alert word
  - Have Hamlet send you a message that includes the alert word
- Zulip labs
  - Turn on auto-scroll to new messages (and have Hamlet send you one)
  - Turn on/off "Enable desktop notifications for new streams" and test.
    (We may eliminate this option soon.)

### Keyboard shortcuts

We mostly test keyboard shortcuts as part of other tasks.

Here are the tasks for this section:

- Use the "?" hotkey to open the keyboard help
- Proofread the dialog for typos.
- Close the dialog.
- Re-open the keyboard help using the gear menu.
- Find a hotkey that you don't frequently use and experiment with its
  usage.

### Miscellaneous menu options

Make sure that these options launch appropriate help screens:

- Proofread and try a couple random options:
  - Message formatting
  - Search filters
- Make sure help launches in a separate browser tab:
  - Desktop and mobile apps
  - Integrations
  - API documentation

### Inviting users/tutorial

Here are the tasks:

- Invite ignore@zulip.com using the link beneath the buddy list but
  then don't take further action.
- Fully invite foo@zulip.com using the gear menu.
- Go to the development console to get the login link for foo@zulip.com.
- Go through the signup flow.
- Follow the tutorial.
- Use the gear menu to log out.
- Log back in as Cordelia (admittedly, this step doesn't really QA
  much of our production code, since the login flow is customized for
  the development environment).

### To be continued...

This document does not cover settings/admin options yet. The main
things to do when testing the settings system are:

- Verify that changes are synced to other users.
- Verify error messages appear if you do something wrong and look right.
- For organization settings, verify that they look right in read-only
  mode (i.e. when not logged into an administrator account).
