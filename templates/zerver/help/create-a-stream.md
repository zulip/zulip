# Create a stream

By default, all users other than guests can create streams.

Organization administrators can
[restrict stream creation](/help/configure-who-can-create-streams) to
admins only, or to members meeting a minimum account age.

If you are an administrator setting up streams for the first time, we highly
recommend reading our
[guide to streams](/help/getting-your-organization-started-with-zulip#create-streams)
first.

## Create a stream

{relative|stream|all}

1. Click **Create stream** on the right.

1. Fill out the requested info, and click **Create**.

!!! warn ""
    You will only see the **Create stream** button if you have
    permission to create streams.

## Stream options

There are several parameters you can set while creating a stream. All but
**Announce stream** you can change later.

* **Stream name**: Appears in the left sidebar for subscribed users. The
  stream name can be in any language, and can include spaces and other
  punctuation.

* **Stream description**: Helps users decide whether to subscribe when they
  are browsing streams.

* **Announce stream**: Posts a message to `#announce` advertising the new
  stream. Organization administrators can change the stream used for stream
  creation announcements in organization settings.

* **Stream permissions**: See [Stream permissions](/help/stream-permissions).

* **People to add**: You can copy the membership from an existing stream, or
  enter users one by one.
