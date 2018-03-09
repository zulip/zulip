# Using Zulip on Android

Zulip has an Android application, compatible with Android versions 3.2 and
higher. The app can be downloaded from the
[Google Play Store](https://play.google.com/store/apps/details?id=com.zulipmobile).

## Initial setup
### Connecting to a server

When you open the app for the first time or after you log out, a screen asking
for your server's address appears. You have to write the server's URL in it, and
press **Enter**.

!!! warn ""
    **Note:** There's no need to add `https://` in case your server is running a secure
    HTTP (HTTPS) protocol.

    However, if your server uses an insecure HTTP connection, you'll have to
    write `http://` manually. A message will appear, warning you about the risks
    of using this type of connections. In case you have no other choice, choose the
    **Use HTTP** option.

### Logging in

After connecting to the server, you'll be able to log in either with an email
address and a password, or using your Google account.

* If you decide to log in with an email/password combination, enter your email
address in the **Email** field and your password in the **Password** field,
then press **Log in**.

    ![Login form](/static/images/help/android-log-in.png)

* If you prefer to log in with your Google account, press the **Log in with Google** button.

    ![Google button](/static/images/help/android-google-login-button.png)

    You will be asked to choose which one do you want to use from those you have
    configured in your device.

### Logging in (development servers)

The Android application supports connecting to development servers as well. To
do so, choose the **Dev backend testing server** option from the
**Authentication Options** menu, and select the account you want to use.

### Logging out

You only need to log out when you want to switch to another account or server.
To do so, tap the overflow ( <i class="icon-vector-ellipsis-vertical"></i> )
icon in the top right corner of the screen, and choose **Log out**.

## Using the app
### Sending a stream message

1. Press the pencil button at the right bottom side of the screen if the
   compose box isn't already there.
2. Make sure you are in **stream message** mode. You should see a person
   (![Person](/static/images/help/android-person-icon.png)) icon at the
   right-hand side of the composing box.
   If it isn't there, tap the megaphone
   (![Megaphone](/static/images/help/android-megaphone-icon.png)) icon.
3. Input the name of the stream where you want to send your message in the
   **Stream** field. Autocompletion suggestions will appear as you type the
   stream's name.
4. Enter the topic of your message in **Topic**.
5. Write your message in the field labeled **Tap on a message to compose reply**.
6. Click the send (![send](/static/images/help/android-paperplane-icon.png))
icon to send your message.

### Sending a private message

1. Press the pencil button at the right bottom side of the screen if the
   compose box isn't already there.
2. Make sure you are in **private message** mode. You should see a megaphone
(![Megaphone](/static/images/help/android-megaphone-icon.png)) icon at the
right-hand side of the compose box. If it isn't there, tap the person
(![Person](/static/images/help/android-person-icon.png)) icon.
3. Enter the email address of the person you want to chat with in the **Person**
   field. Autocomplete suggestions will appear as you type the email address.
4. Write your message in the field labeled **Tap on a message to compose reply**.
5. Click the send (![send](/static/images/help/android-paperplane-icon.png))
icon to send your message.

### Replying to a message

1. Tap the message you want to reply to in the message list.
2. The **Stream** and **Topic** fields will automatically fill.
3. Write your message in the field labeled **Tap on a message to compose reply**.
4. Click the send (![send](/static/images/help/android-paperplane-icon.png))
icon to send your message.

### Narrowing to a stream

There are multiple ways of narrowing to a stream in Zulip's Android app.

By swiping to the right from the border of the screen or clicking the menu (<i
class="icon-vector-reorder"></i>) icon, you'll be able to see a list of the
streams you're subscribed to. You can tap one of them to narrow to that stream.

!!! tip ""
    You can also click on the stream name of a message to automatically narrow
    your message list to only show messages from the pressed stream.

### Narrowing to a topic

You can narrow your message list to a specific topic by tapping the name of the
topic over a message.

### Searching for messages

You can search your organization for specific messages by using [search operators](/help/search-for-messages).

1. Tap the search (<i class="icon-vector-search"></i>)
icon at the top of the screen.
2. Enter the [search operators](/help/search-for-messages#search-operators)
that you want to use to narrow your messages.
3. Press the **Enter** key in your keyboard to begin your search.

### Filtering messages

You can filter the messages in your message list.

1. Press the filter (![Filter](/static/images/help/android-filter-icon.png))
icon on the top right side of the screen.
2. Select the filtering criteria from the dropdown that appears.
3. The message list will refresh to show only the filtered messages.

### Manually refreshing the message list

The messages will appear automatically as they are sent. However, you can
manually refresh them by:

* scrolling to the bottom of the message list
* clicking the overflow (
<i class="icon-vector-ellipsis-vertical"></i> ) icon in the top right corner
and choosing the **Refresh** option from the dropdown that appears.

### Day/Night Themes

Zulip's Android app offers two different themes: one lighter (day theme), and
one with dark colors (night theme) that makes reading more comfortable when
there isn't much light.

To switch between the two themes, click the overflow ( <i
class="icon-vector-ellipsis-vertical"></i> ) icon at the top right corner of the
screen and choosing the **Switch Day/Night Theme** option from the dropdown that
appears.
