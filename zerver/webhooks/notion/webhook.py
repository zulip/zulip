from zerver.lib.validator import WildValue, check_dict, check_string

PAGE_EVENT_MESSAGES = {
    "page.created": "New page created",
    "page.properties_updated": "Page properties updated",
    "page.content_updated": "Page content updated",
    "page.moved": "Page moved",
    "page.deleted": "Page moved to trash",
    "page.undeleted": "Page restored",
    "page.locked": "Page locked",
    "page.unlocked": "Page unlocked",
}

DATABASE_EVENT_MESSAGES = {
    "database.created": "Database created",
    "database.content_updated": "Database content updated",
    "database.schema_updated": "Database schema updated",
    "database.moved": "Database moved",
    "database.deleted": "Database deleted",
    "database.undeleted": "Database restored",
}

COMMENT_EVENT_MESSAGES = {
    "comment.created": "Comment added",
    "comment.updated": "Comment updated",
    "comment.deleted": "Comment deleted",
}

PAGE_EVENTS = list(PAGE_EVENT_MESSAGES.keys())
DATABASE_EVENTS = list(DATABASE_EVENT_MESSAGES.keys())
COMMENT_EVENTS = list(COMMENT_EVENT_MESSAGES.keys())


def handle_page_event(payload: WildValue) -> tuple[str, str]:
    event_type = payload["type"].tame(check_string)
    workspace = payload["workspace_name"].tame(check_string)
    entity = payload["entity"].tame(check_dict)
    page_id = entity["id"].tame(check_string)
    action = PAGE_EVENT_MESSAGES.get(event_type)
    assert action is not None
    topic = "Notion Pages"

    body = f"**{action}**\n\nWorkspace: **{workspace}**\nPage ID: `{page_id}`"

    return topic, body


def handle_database_event(payload: WildValue) -> tuple[str, str]:
    event_type = payload["type"].tame(check_string)
    entity = payload["entity"].tame(check_dict)
    db_id = entity["id"].tame(check_string)
    action = DATABASE_EVENT_MESSAGES.get(event_type)
    assert action is not None
    topic = "Notion Databases"
    body = f"**{action}**\n\nDatabase ID: `{db_id}`"
    return topic, body


def handle_comment_event(payload: WildValue) -> tuple[str, str]:
    event_type = payload["type"].tame(check_string)
    action = COMMENT_EVENT_MESSAGES.get(event_type)
    assert action is not None
    topic = "Notion Comments"
    body = f"**{action}** in Notion."
    return topic, body
