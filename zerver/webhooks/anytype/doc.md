# Zulip Anytype integration

Get Anytype object notifications in Zulip! This integration supports notifications for object creation, updates, deletion, archiving, and restoration across your Anytype spaces.

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. [Generate the integration URL](/help/generate-integration-url) for the stream where you'd like to receive Anytype notifications.

1. **Configure your webhook source**: Since Anytype doesn't currently provide native webhooks, you can use this integration with:
   - **Custom webhook bridges** that monitor Anytype API changes
   - **Third-party automation tools** like Zapier or Make.com
   - **Future native Anytype webhooks** (when available)

1. **Set up your webhook source** to send POST requests to the generated URL with the following payload format:

   ```json
   {
     "event": "object.created",
     "timestamp": "2024-01-15T10:30:00Z",
     "object": {
       "id": "obj_abc123",
       "type": "note",
       "title": "Meeting Notes",
       "description": "Optional description"
     },
     "space": {
       "id": "space_xyz789",
       "name": "Personal Notes"
     },
     "user": {
       "id": "user_alice123",
       "name": "Alice Johnson"
     }
   }
   ```

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/anytype/001.png)

## Supported events

This integration supports the following Anytype object events:

- **object.created** - New object (note, page, task, etc.) created
- **object.updated** - Object content or properties updated  
- **object.deleted** - Object deleted
- **object.archived** - Object archived
- **object.restored** - Object restored from archive

## Payload format

### Required fields

- `event`: The event type (must start with "object.")

### Optional fields

- `object`: Object details
  - `id`: Unique object identifier
  - `type`: Object type (note, page, task, project, etc.)
  - `title` or `name`: Object title/name (defaults to "Untitled")
  - `description`: Object description (shown for created objects)
- `space`: Space information
  - `id`: Space identifier
  - `name`: Space name (used as topic if not specified)
- `user`: User who performed the action
  - `id`: User identifier
  - `name`: User display name
- `timestamp`: ISO 8601 timestamp of the event

## Message formatting

The integration automatically formats messages with:
- **Emoji indicators** for different object types (📝 for notes, 📄 for pages, ✅ for tasks, etc.)
- **Action descriptions** (created, updated, deleted, archived, restored)
- **Object titles** and types
- **Space and user context** when available
- **Descriptions** for newly created objects (truncated to 200 characters)

## Topic naming

Messages are organized by topic using this priority:
1. User-specified topic (via URL parameter)
2. Space name (from payload)
3. Object type (capitalized)

## Example integrations

### Using Zapier

1. Create a Zap that triggers on Anytype events (when available)
2. Add a "Webhooks by Zapier" action
3. Set the method to POST and URL to your generated Zulip webhook URL
4. Format the payload according to the schema above

### Custom webhook bridge

Build a service that:
1. Polls the Anytype API for changes
2. Formats detected changes into the webhook payload format
3. Sends POST requests to your Zulip webhook URL

{!webhooks-url-specification.md!}