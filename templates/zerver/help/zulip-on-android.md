# Using Zulip on Android

Zulip has an Android application, compatible with Android versions 3.2 and
higher.

It's available on the Google Play Store, and can be downloaded from
[here](https://play.google.com/store/apps/details?id=com.zulip.android), or by
clicking the badge below.

[![Play Store badge](/static/images/help/google-play-badge.png)](
https://play.google.com/store/apps/details?id=com.zulip.android)

## Initial setup
### Connecting to a server

When you open the app for the first time, or after you log out, a screen asking
for your server's address appears. You have to write the server's URL in it, and
press *Enter*.

!!! tip ""
    There's no need to add `https://` in case your server is running secure
    HTTP (HTTPS) protocol.

!!! warn ""
    If your server uses unsecure HTTP, you'll have to
    write `http://` manually. A message will appear, warning you about the risks
    of using this type of connections. In case you have no other choice, choose
    *Use HTTP*.

### Logging in

After connecting to the server, you'll be able to log in either with an email
address and a password, or using your Google account.

!!! tip ""
    If you decide to log in with an email/password combination, enter them in
    the text fields and press *Log in*.

    ![Login form](/static/images/help/android-log-in.png)

!!! tip ""
    If you prefer to log in with your Google account, press the *Sign in* button
    with Google's logo on it.

    ![Google button](/static/images/help/android-google-sign-in-button.png)

    You will be asked to choose which one do you want to
    use, between those you have configured in your device.

### Logging in (development servers)

The Android application supports using development servers as well. However,
after connecting to the server, the following will appear:

![Dev login screen](/static/images/help/android-dev-login-screen.png)

In order to log in, press *Dev backend testing server*, and choose the account
you want to use:

![Dev accounts](/static/images/help/android-dev-accounts.png)

### Logging out

You only need to do this when you want to switch to another account or server.

Tap the three dots (<i class="icon-vector-ellipsis-vertical"></i>)
in the top right corner of the screen, and choose *Log out*.

![Log out](/static/images/help/android-log-out.png)

## Using the app
### Sending a stream message

1. Press the pencil button at the right bottom side of the screen, in case the
   compose box isn't already there.
2. Make sure you are in the "stream message" mode. You should see the
   icon of a person
   (![Person icon](/static/images/help/android-person-icon.png)) at the
   right-hand side of the composing area.
   If it isn't there, tap the megaphone
   (![Megaphone icon](/static/images/help/android-megaphone-icon.png)).
3. Fill the name of the stream where you want to send your message in the
   *Stream* field.

    !!! tip ""
        Suggestions matching the entered name will appear as you type the stream's
        name.

4. Enter the topic of your message in *Topic*.
5. Write your message in the field at the bottom, the one that says *Tap on a
   message to compose reply*.
6. Hit the paper plane icon
   (![Paper plane icon](/static/images/help/android-paperplane-icon.png)) to
   send your message.

![Stream message](/static/images/help/android-stream-message.png)

### Sending a private message

1. Press the pencil button at the right bottom side of the screen, in case the
   compose box isn't already there.
2. Make sure you are in the "stream message" mode. You should see the
   icon of a megaphone
   (![Megaphone icon](/static/images/help/android-megaphone-icon.png)) at the
   right-hand side of the composing area.
   If it isn't there, tap the person
   (![Person icon](/static/images/help/android-person-icon.png)).
3. Enter the email address of the person you want to chat with in the *Person*
   field.

    !!! tip ""
        Suggestions matching the entered email address will appear as you type it.

4. Write your message in the field at the bottom, the one that says *Tap on a
   message to compose reply*.
5. Hit the paper plane icon
  (![Paper plane icon](/static/images/help/android-paperplane-icon.png)) to
  send your message.

![Private message](/static/images/help/android-private-message.png)

### Replying to a message

1. Tap the message you want to reply to in the message list.
2. The *Stream* and *Topic* fields will automatically fill.
3. Write your message in the field at the bottom, the one that says *Tap on a
   message to compose reply*.
4. Hit the paper plane icon
   (![Paper plane icon](/static/images/help/android-paperplane-icon.png)) to
   send your message.

### Narrowing to a stream

There are multiple ways of narrowing to a stream in Zulip's Android app.

By swiping to the right from the border of the screen, or by hitting the menu
(<i class="icon-vector-reorder"></i>) icon, you'll be able to see a list of the
streams you're subscribed to.

![Streams list](/static/images/help/android-streams-list.png)

You can tap one of them to narrow to that stream.

Another way is to press the name of a stream in a message. This will
automatically narrow your message list to the pressed stream.

### Narrowing to a topic

You can narrow your message list to a specific topic by tapping the name of the
topic over a message.

### Searching for messages

To look for messages containing some specific terms:

1. Tap the magnifying glass
    (![Magnifying glass icon](/static/images/help/android-magnifying-icon.png))
    icon at the top of the screen.
2. Write the desired search terms.
3. Press enter in your keyboard.

![Message search](/static/images/help/android-search.png)

### Filtering messages

You can filter the messages in your list. To do it:

1. Press the filter
   (![Filter icon](/static/images/help/android-filter-icon.png)) icon in the top
   right side of the screen (between the magnet and the three dots
   <i class="icon-vector-ellipsis-vertical"></i>).
2. Choose the filtering criteria.
3. The message list will refresh, showing only the matching messages.

### Manually refreshing the message list

The messages will appear automatically as they are sent. However, you can
manually refresh them by scrolling to the bottom, or by tapping the three dots
(<i class="icon-vector-ellipsis-vertical"></i>) in the top right corner, and
choosing *Refresh*.

![Refresh option](/static/images/help/android-refresh.png)

### Day/Night themes

Zulip's Android app offers two different themes. One lighter (day theme), and
one with dark colors (night theme), that makes reading more comfortable when
there isn't much light.

![Night theme](/static/images/help/android-night-theme.png)

To switch between both, tap the three dots
(<i class="icon-vector-ellipsis-vertical"></i>) at the top right corner of the
screen, and hit *Switch Day/Night Theme*.

![Switch themes](/static/images/help/android-switch-themes.png)
