# Exporting data from a large multi-realm Zulip server

## Draft status

This is a draft design document considering potential future
refinements and improvements to make large migrations easier going
forward, and is not yet a set of recommendations for Zulip systems
administrators to follow.

## Overview

Zulip includes an export tool, `management/export.py`, which
exports data for a single Zulip realm. `management/export.py`
is beneficial when migrating a Zulip realm to a new server.

This document covers the logistics a big conversion of a
multi-realm Zulip installation, supplementing the explanation in
`management/export.py`.

There are many major operational aspects to doing a conversion,
including:

- Getting new servers running
- Exporting data from the old DB
- Exporting files from Amazon S3
- Importing files into new storage
- Importing data into new DB
- Restarting new servers
- Decommissioning the old server

This document focuses on **exporting** data from the old DB and
Amazon S3.  For informatoin on installing or running Zulip see
[Zulip installation instructions](../index.html#zulip-in-production).

## Exporting multiple realms' data when moving to a new server

As of summer 2016, Zulip can:
- Export single realms (but not yet limit users within the
  realm)
- Export single users (but doesn't get realm-wide data in
  the process)
- Run exports simultaneously (but have to navigate a bunch of
  /tmp directories)

In the future, it may be useful for Zulip to:
- Export multiple realms simultaneously
- Export multiple single users simultaneously
- Limit users within realm exports
- Introduce more operational robustness/convenience
  while doing several exports simultaneously
- Merge multiple export files to remove duplicates

### Data Classes

Zulip has a few major classes of data.  They are listed below in
the order that Zulip processes them in `do_export_realm()`:

<table>
    <tr>
        <th>Data Class</th>
        <th>Path</th>
        <th>Notes</th>
    </tr>
    <tr>
        <td>Public Realm</td>
        <td><code>Realm/RealmDomain/RealmEmoji/RealmFilter/DefaultStream</code></td>
        <td></td>
    </tr>
    <tr>
        <td>Cross Realm</td>
        <td><code>Client/zerver_userprofile_cross_realm</code></td>
        <td>Cross realm data includes includes <code>Client</code> and three bots.
            <br><br> <code>Client</code> is unique in being a fairly core table
            that is not tied to <code>UserProfile</code> or <code>Realm</code> (unless you
            tie it back to users in a bottom-up fashion though other tables).</td>
    </tr>
    <tr>
        <td>Disjoint User</td>
        <td><code>UserProfile/UserActivity/UserActivityInterval/UserPresence</code></td>
        <td></td>
    </tr>
    <tr>
        <td>Recipient</td>
        <td><code>Recipient/Stream/Subscription/Huddle</code></td>
        <td>Recipient data tables re tied back to users, but
            introduce complications when you try to deal with multi-user
            subsets.</td>
    </tr>
    <tr>
        <td>File-related</td>
        <td><code>Attachment</code></td>
        <td>File-related data includes <code>Attachment</code>, and it references
            the <code>avatar_source</code> field of <code>UserProfile</code>.  Most
            importantly, it requires you to grab files from S3.
            <code>Attachment</code>'s <code>m2m</code> relationship ties to <code>Message</code>.</td>
    </tr>
    <tr>
        <td>Message</td>
        <td><code>Message/UserMessage</code></td>
        <td></td>
    </tr>
</table>

### Data Gathering

There are two approaches to getting data: top-down and bottom-up.

```
!!! warn ""
    **Note:** Zulip have not yet integrated the approved-transfer
    model, which says which users can be moved.
```

#### Top-down

The first step in a top-down approach is to get realm data.
Next, get all users in realm, then all recipients, then all
messages, and so on.

The problem with a top-down approach is **filtering**.  Also,
if errors arise during top-down passes, it may be time consuming to
re-run processes.

#### Bottom-up

The first step in a bottom-up approach is to get the users. Then,
get their recipient data, an so on.

The problem with a bottom-up approach is **merging**.  Also,
if you run multiple bottom-up passes, there is the danger of
duplicating some work, particularly on the message side of things.

### Data Class Risks

Here are the classes of data, listed in roughly
decreasing order of riskiness:

- Message Data (sheer volume/lack of time/security)
- File-Related Data (S3/security/lots of moving parts)
- Recipient Data (complexity/security/cross-realm considerations)
- Cross Realm Data (duplicate ids)
- Disjoint User Data
- Public Realm Data

(Note the above list is essentially in reverse order of how Zulip
processes the data, which isn't surprising for a top-down approach.)

#### Message Data

- models: `Message`/`UserMessage`.
- assets: `messages-*.json`, subprocesses, partial files

Rows in the `Message` model depend on `Recipient/UserProfile`.

Rows in the `UserMessage` model depend on `UserProfile/Message`.

The biggest concern here is the **sheer volume** of data, with
security being a close second.  (They are interrelated, as without
security concerns, Zulip could just bulk-export everything one time.)

Zulip currently has these measures in place for top-down processing:
- chunking
- multi-processing
- messages are filtered by both sender and recipient


#### File Related Data

- models: `Attachment`
- assets: S3, `attachment.json`, `uploads-temp/`, image files in
  `avatars/`, assorted files in `uploads/`, `avatars/records.json`,
  `uploads/records.json`, `zerver_attachment_messages`

When it comes to exporting attachment data, Zulip has some minor volume
issues, but the main concern is just that there are **lots of moving
parts**:

- S3 needs to be up, and Zulip gets some metadata from it as well as
  files.
- There are security concerns about copying over only files that belong
  to users who approved the transfer.
- This piece is just different in how Zulip stores data from all the other
  DB-centric pieces.
- At import time Zulip has to populate the `m2m` table (but fortunately,
  this is pretty low risk in terms of breaking anything.)

#### Recipient Data
- models: `Recipient/Stream/Subscription/Huddle`
- assets: `realm.json`, `(user,stream,huddle)_(recipient,subscription)`

This data is fortunately low to medium in volume.  The risk here will
come from **model complexity** and **cross-realm concerns**.

From the top down, here are the dependencies:

- `Recipient` depends on `UserProfile`
- `Subscription` depends on `Recipient`
- `Stream` currently depends on `Realm` (but maybe it should be tied
  to `Subscription`)
- `Huddle` depends on `Subscription` and `UserProfile`

The biggest risk factor here is probably just the possibility that you
could introduce some bug in our code as you try to segment `Recipient`
into user, stream, and huddle components, especially if you try to
handle multiple users or realms.  I think this can be largely
mitigated by the new `Config` approach.

And there is also have some complicated `Huddle` logic that will be
customized regardless.  The fiddliest part of the `Huddle` logic is
creating the set of `unsafe_huddle_recipient_ids`.

Last but not least, if you go with some hybrid of bottom-up and
top-down, these tables are neither close to the bottom nor close to
the top, so they may have the most fiddly edge cases when it comes to
filtering and merging.

Recommendation: We probably want to get a backup of all this data that
is very simply bulk-exported from the entire DB, and we should
obviously put it in a secure place.

#### Cross Realm Data
- models: `Client`
- assets: `realm.json`, three bots (`notification`/`email`/`welcome`),
  `id_maps`

The good news here is that `Client` is a small table, and there are
only three special bots.

The bad news is that cross-realm data **complicates everything else**,
and we have to avoid **database ID conflicts**.

If we use bottom-up approaches to load small user populations at a
time, we may have **merging** issues here.  We will need to
consolidate IDs either by merging exports in `/tmp` or handle it at
import time.

For the three bots, they live in `zerver_userprofile_crossrealm`, and
we re-map their IDs on the new server.

Recommendation: Do not sweat the exports too much.  Deal with all the
messiness at import time, and rely on the tables being really small.
We already have logic to catch `Client.DoesNotExist` exceptions, for
example.  As for possibly missing messages that the welcome bot and
friends have sent in the past, I am not sure what our risk profile is
there, but I imagine it is relatively low.

#### Disjoint User Data
- models: `UserProfile/UserActivity/UserActivityInterval/UserPresence`
- assets: `realm.json`, `password`, `api_key`, `avatar salt`,
  `id_maps`

On the DB side this data should be fairly easy to deal with.  All of
these tables are basically disjoint by user profile ID.  Our biggest
risk is **remapped user ids** at import time, but this is mostly
covered in the section above.

We have code in place to exclude `password` and `api_key` from
`UserProfile` rows.  The import process calls
`set_unusable_password()`.

#### Public Realm Data

- models: `Realm/RealmDomain/RealmEmoji/RealmFilter/DefaultStream`
- asserts: `realm.json`

All of these tables are public (per-realm), and they are keyed by
realm ID.  There is not a ton to worry about here, except possibly
**merging** if we run multiple bottom-up jobs for a single realm.
