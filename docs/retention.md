# Retention policy


## Overview

This document describes Retention policy feature. This policy provides
tools with help of which one can move expired messages and attachments
to archive tables, if the retention period is set in realm organization
settings. And remove archived messages from archive tables after
expiring of archive retention period if is not necessary to restore
these messages.

Zulip contains console commands `management/commands/archive_messages.py`
to move expired messages to archive tables and
`management/commands/remove_old_archived_data.py` to remove archived
messages and archived attachments permanently.


## Archive django models

Archiving tables were created to save removed data temporarily
for restoring:

  `zerver.models.ArchivedMessage`
  `zerver.models.ArchivedUserMessage`
  `zerver.models.ArchivedAttachment`

These models are inherited from abstract model classes which are common
for real and archive records.

Archiving tables are cleaned when `ARCHIVED_DATA_RETENTION_DAYS` from
project settings is expired for table record by launching
`management/commands/remove_old_archived_data.py` management command.


## Retention tools

Retention tools are located in `zerver/lib/retention.py`.

### Moving expired messages and attachments to archive

Retention tools methods:


  `zerver.lib.retention.move_expired_messages_to_archive`
  `zerver.lib.retention.move_expired_user_messages_to_archive`
  `zerver.lib.retention.move_expired_attachments_to_archive`
  `zerver.lib.retention.move_expired_attachments_message_rows_to_archive`
  `zerver.lib.retention.archive_messages`

As Django ORM is not so flexible as raw SQL language queries are, we had
to use sql queries and db connector directly in tools for moving data
to archive. This decision allows to move the data in one query.

Messages and attachments are moved to archive when all `user_messages`
related to them are moved to archive.

Method `archive_messages` is used as result method which contains
archiving and removing methods in a correct order.


### Deleting expired messages and attachments

Retention tools methods:


  `zerver.lib.retention.delete_expired_messages`
  `zerver.lib.retention.delete_expired_user_messages`
  `zerver.lib.retention.delete_expired_attachments`

Records are removed from the actual tables when they don't have related
objects. There shouldn't be any related `user_messages` records for
messages and there shouldn't be any related`messages` for attachments.

### Deleting expired archive data

Retention tools methods:


  `zerver.lib.retention.delete_expired_archived_attachments`
  `zerver.lib.retention.delete_expired_archived_data`

If the restoring of archive messages and attachments is not required for
`ARCHIVED_DATA_RETENTION_DAYS` period, the archived data should be
removed. To remove this data `delete_expired_archived_data`
method is used, which includes `delete_expired_archived_attachments`
method to remove attachments.


## Cron jobs

Cron file:

  `puppet/zulip/files/cron.d/archive-messages`

This file contains two cron jobs. The first one is used to launch the
archiving manage console command and the other one to remove expired
archived data.

The order of launching jobs is important, as the archiving job
should clean all the related objects at this moment. In other case,
it will be done next time.

## Front-end admin settings

To enable realm retention policy you should add value to the
`Retention period for messages in days` form field in
`Organization settings` form from administration part. To disable this
feature leave this field empty.


## Tests

Test cases are descibed in `zerver/tests/test_retention.py`.
