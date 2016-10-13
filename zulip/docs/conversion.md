# Exporting data

## Overview

Occasionally Zulip administrators will need to move data from one
server to another.

There are many major operational aspects to doing a conversion. I will
list them here, noting that several are not within the scope of this
document:

- Get new servers running.
- Export data from the old DB.
- Export files from S3.
- Import files into new storage.
- Import data into new DB.
- Restart new servers.
- Decommission old server.

This document focuses almost entirely on the **export** piece.  Issues
with getting Zulip itself running are totally out of scope here.  For the
import side of things, I only touch on it implicity.  (My reasoning is
that we *have* to get the export piece right in a timely fashion, even
if it means we have to sort out some straggling issues on the import side
later.)

## Export

We have tools that essentially export Zulip data to the file system.

A good overview of the process is here:
[management/export.py](https://github.com/zulip/zulip/blob/master/zerver/management/commands/export.py)

This document supplements that explanation, but here we focus more
on the logistics of a big conversion.  For some historical perspective,
this document was originally drafted as part of a big Zulip cut-over.

The main exporting tools in place as of summer 2016 are below:

- We can export single realms (but not yet limit users within the realm).
- We can export single users (but then we get no realm-wide data in the process).
- We can run exports simultaneously (but have to navigate a bunch of /tmp directories).

Things that we still may need:
- We may want to export multiple realms simultaneously.
- We may want to export multiple single users simultaneously.
- We may want to limit users within realm exports.
- We may want more operational robustness/convenience while doing several exports simultaenously.
- We may want to merge multiple export files to remove duplicates.

We have a few major classes of data.  They are listed below in the order
that we process them in `do_export_realm()`:

#### Public Realm Data

Realm/RealmAlias/RealmEmoji/RealmFilter/DefaultStream.

#### Cross Realm Data

Client/zerver_userprofile_cross_realm

This includes Client and three bots.

Client is unique in being a fairly core table that is
not tied to UserProfile or Realm (unless you somewhat painfully tie
it back to users in a bottom-up fashion though other tables).

#### Disjoint User Data

UserProfile/UserActivity/UserActivityInterval/UserPresence.

#### Recipient Data

Recipient/Stream/Subscription/Huddle.

These tables are tied back to users, but they introduce complications
when you try to deal with multi-user subsets.

#### File-related Data

Attachment

This includes Attachment, and it referencs the avatar_source field of
UserProfile.  Most importantly, of course, it requires us to grab files
from S3.  Finally, Attachment's m2m relationship ties to Message.

#### Message Data

Message/UserMessage

### Summary

Here are the same classes of data, listed in roughly
decreasing order of riskiness:

- Message Data (sheer volume/lack of time/security)
- File-Related Data (S3/security/lots of moving parts)
- Recipient Data (complexity/security/cross-realm considerations)
- Cross Realm Data (duplicate ids)
- Disjoint User Data
- Public Realm Data

(Note the above list is essentially in reverse order of how we
process the data, which isn't surprising for a top-down approach.)

The next section of the document talks about risk factors.

# Risk Mitigation

## Generic considerations

We have two major mechanisms for getting data:

##### Top Down

Get realm data, then all users in realm, then all recipients, then all messages, etc.

The problem with the top down approach will be **filtering**.  Also, if
errors arise during top-down passes, it may be time consuming to re-run
the processes.

##### Bottom Up

Start with users, get their recipient data, etc.

The problems with the bottom up approach will be **merging**.  Also, if
we run multiple bottom-up passes, there is the danger of duplicating some
work, particularly on the message side of things.

### Approved Transfers

We have not yet integrated the approved-transfer model, which tells us
which users can be moved.

## Risk factors broken out by data categories

### Message Data

- models: Message/UserMessage.
- assets: messages-*.json, subprocesses, partial files

Rows in the Message model depend on Recipient/UserProfile.

Rows in the UserMessage model depend on UserProfile/Message.

The biggest concern here is the **sheer volume** of data, with
security being a close second.  (They are interrelated, as without
security concerns, we could just bulk-export everything one time.)

We currently have these measures in place for top-down processing:
- chunking
- multi-processing
- messages are filtered by both sender and recipient


### File Related Data

- models: Attachment
- assets: S3, attachment.json, uploads-temp/, image files in avatars/, assorted files in uploads/, avatars/records.json, uploads/records.json, zerver_attachment_messages

When it comes to exporting attachment data, we have some minor volume issues, but the
main concern is just that there are **lots of moving parts**:

- S3 needs to be up, and we get some metadata from it as well as files.
- We have security concerns about copying over only files that belong to users who approved the transfer.
- This piece is just different in how we store data from all the other DB-centric pieces.
- At import time we have to populate the m2m table (but fortunately, this is pretty low
  risk in terms of breaking anything.)

### Recipient Data
- models: Recipient/Stream/Subscription/Huddle
- assets: realm.json, (user,stream,huddle)_(recipient,subscription)

This data is fortunately low to medium in volume.  The risk here will come
from **model complexity** and **cross-realm concerns**.

From the top down, here are the dependencies:

- Recipient depends on UserProfile
- Subscription depends on Recipient
- Stream currently depends on Realm (but maybe it should be tied to Subscription)
- Huddle depends on Subscription and UserProfile

The biggest risk factor here is probably just the possibility that we could introduce
some bug in our code as we try to segment Recipient into user, stream, and huddle components,
especially if we try to handle multiple users or realms.
I think this can be largely mitigated by the new Config approach.

And then we also have some complicated Huddle logic that will be customized
regardless.  The fiddliest part
of the Huddle logic is creating the set of unsafe_huddle_recipient_ids.

Last but not least, if we go with some hybrid of bottom-up and top-down, these tables
are neither close to the bottom nor close to the top, so they may have the most
fiddly edge cases when it comes to filtering and merging.

Recommendation: We probably want to get a backup of all this data that is very simply
bulk-exported from the entire DB, and we should obviously put it in a secure place.

### Cross Realm Data
- models: Client
- assets: realm.json, three bots (notification/email/welcome), id_maps

The good news here is that Client is a small table, and there are
only three special bots.

The bad news is that cross-realm data **complicates everything else**,
and we have to avoid **database id conflicts**.

If we use bottom-up approaches to load small user populations at a time, we may
have **merging** issues here.  We will need to consolidate ids either by merging
exports in /tmp or handle it import time.

For the three bots, they live in zerver_userprofile_crossrealm, and we re-map
their ids on the new server.

Recommendation: Do not sweat the exports too much.  Deal with all the messiness at
import time, and rely on the tables being really small.  We already have logic
to catch Client.DoesNotExist exceptions, for example.  As for possibly missing
messages that the welcome bot and friends have sent in the past, I am not sure
what our risk profile is there, but I imagine it is relatively low.

### Disjoint User Data
- models: UserProfile/UserActivity/UserActivityInterval/UserPresence
- assets: realm.json, password, api_key, avatar salt, id_maps

On the DB side this data should be fairly easy to deal with.  All of these
tables are basically disjoint by user profile id.  Our biggest
risk is **remapped user ids** at import time, but this is mostly covered
in the section above.

We have code in place to exclude password and api_key from UserProfile
rows.  The import process calls set_unusable_password().

### Public Realm Data

- models: Realm/RealmAlias/RealmEmoji/RealmFilter/DefaultStream
- asserts: realm.json

All of these tables are public (per-realm), and they are keyed by
realm id.  There is not a ton to worry about here, except possibly
**merging** if we run multiple bottom-up jobs for a single realm.
