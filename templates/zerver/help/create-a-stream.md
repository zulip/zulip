# Create a stream

Streams can either be public to anyone in the organization, or require an
invitation to join. Organization admins can always see the names and
membership of invite-only streams, but cannot read any of the messages.

If you are an administrator setting up streams for the first time, we highly
recommend reading our
[guide to streams](/help/getting-your-organization-started-with-zulip#create-streams)
first.

## Create a new stream

{!subscriptions.md!}

3. Click the plus (<i class="icon-vector-plus"></i>) icon to the right of
the **Filter streams** input.

    !!! warn ""
        **Note:** If you do not see the plus
        (<i class="icon-vector-plus"></i>) icon, it
        is probably because your organization's administrators
        have disabled stream creation for ordinary users.
        If that's the case, then you need to ask them to
        allow ordinary users to create streams, or you will have
        to ask an administrator for help creating each particular stream.

4. After clicking the plus (<i class="icon-vector-plus"></i>) icon, at
right side of the [Streams](/#streams) page, labeled
**Create stream**, will now display options for creating a stream.

5. Enter the title of your stream in the **Stream name** input.
If you designate your stream as public, the **Stream name** will be
displayed under the Streams on the left sidebar. Your stream name must
be unique to all other stream names and can be no longer than
60 characters.

    !!! tip ""
        You can optionally enter a brief description of your stream in
        **Stream description** to give other users a general idea of
        what's being discussed in your stream. The description can be
        seen under the stream name in the stream overview.

7. The **Stream privacy** option controls the privacy of your
stream. There are two options:
    * **Anybody can join** - This option makes your stream **public**
    and accessible to all users.

    * **People must be invited** - This option makes your stream
    **private**. Only users you invite will be able to access this stream.
    Only the creator of the stream can invite new users this stream.

8. If your stream is public, you can choose to alert users about the new
stream by clicking the **Announce stream** checkbox. Users who have been
added to the new stream will always be notified, but if the
**Announce stream** feature is enabled, all users will be notified
of the stream's creation.

9. To automatically subscribe a user to your stream, scroll down to
**People to add** and tick the checkboxes with the names of the users
you want to add.

    !!! tip ""
        To search for specific users, enter their usernames in the
        **Filter names** box.

10. Once you are ready to create your stream,
click the **Create** button. The stream will now appear
in the left sidebar for the users that you subscribed.
