from functools import partial
from typing import Any, Callable, Dict, Generator, List, Optional

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventType
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

EPIC_NAME_TEMPLATE = "**{name}**"
STORY_NAME_TEMPLATE = "[{name}]({app_url})"
COMMENT_ADDED_TEMPLATE = (
    "New comment added to the {entity} {name_template}:\n``` quote\n{text}\n```"
)
NEW_DESC_ADDED_TEMPLATE = (
    "New description added to the {entity} {name_template}:\n``` quote\n{new}\n```"
)
DESC_CHANGED_TEMPLATE = (
    "Description for the {entity} {name_template} was changed from:\n"
    "``` quote\n{old}\n```\nto\n``` quote\n{new}\n```"
)
DESC_REMOVED_TEMPLATE = "Description for the {entity} {name_template} was removed."
STATE_CHANGED_TEMPLATE = (
    "State of the {entity} {name_template} was changed from **{old}** to **{new}**."
)
NAME_CHANGED_TEMPLATE = (
    "The name of the {entity} {name_template} was changed from:\n"
    "``` quote\n{old}\n```\nto\n``` quote\n{new}\n```"
)
ARCHIVED_TEMPLATE = "The {entity} {name_template} was {operation}."
STORY_TASK_TEMPLATE = "Task **{task_description}** was {operation} the story {name_template}."
STORY_TASK_COMPLETED_TEMPLATE = (
    "Task **{task_description}** ({name_template}) was completed. :tada:"
)
STORY_ADDED_REMOVED_EPIC_TEMPLATE = (
    "The story {story_name_template} was {operation} the epic {epic_name_template}."
)
STORY_EPIC_CHANGED_TEMPLATE = "The story {story_name_template} was moved from {old_epic_name_template} to {new_epic_name_template}."
STORY_ESTIMATE_TEMPLATE = "The estimate for the story {story_name_template} was set to {estimate}."
FILE_ATTACHMENT_TEMPLATE = (
    "A {type} attachment `{file_name}` was added to the story {name_template}."
)
LABEL_TEMPLATE = "**{name}**"
STORY_LABEL_TEMPLATE = "The label {labels} was added to the story {name_template}."
STORY_LABEL_PLURAL_TEMPLATE = "The labels {labels} were added to the story {name_template}."
STORY_UPDATE_PROJECT_TEMPLATE = (
    "The story {name_template} was moved from the **{old}** project to **{new}**."
)
STORY_UPDATE_TYPE_TEMPLATE = (
    "The type of the story {name_template} was changed from **{old_type}** to **{new_type}**."
)
DELETE_TEMPLATE = "The {entity_type} **{name}** was deleted."
STORY_UPDATE_OWNER_TEMPLATE = "New owner added to the story {name_template}."
TRAILING_WORKFLOW_STATE_CHANGE_TEMPLATE = " ({old} -> {new})"
STORY_GITHUB_PR_TEMPLATE = (
    "New GitHub PR [#{name}]({url}) opened for story {name_template}{workflow_state_template}."
)
STORY_GITHUB_COMMENT_PR_TEMPLATE = "Existing GitHub PR [#{name}]({url}) associated with story {name_template}{workflow_state_template}."
STORY_GITHUB_BRANCH_TEMPLATE = "New GitHub branch [{name}]({url}) associated with story {name_template}{workflow_state_template}."
STORY_UPDATE_BATCH_TEMPLATE = "The story {name_template} {templates}{workflow_state_template}."
STORY_UPDATE_BATCH_CHANGED_TEMPLATE = "{operation} from {sub_templates}"
STORY_UPDATE_BATCH_CHANGED_SUB_TEMPLATE = "{entity_type} **{old}** to **{new}**"
STORY_UPDATE_BATCH_ADD_REMOVE_TEMPLATE = "{operation} with {entity}"


def get_action_with_primary_id(payload: Dict[str, Any]) -> Dict[str, Any]:
    for action in payload["actions"]:
        if payload["primary_id"] == action["id"]:
            action_with_primary_id = action

    return action_with_primary_id


def get_event(payload: Dict[str, Any], action: Dict[str, Any]) -> Optional[str]:
    event = "{}_{}".format(action["entity_type"], action["action"])

    # We only consider the change to be a batch update only if there are multiple stories (thus there is no primary_id)
    if event == "story_update" and payload.get("primary_id") is None:
        return "{}_{}".format(event, "batch")

    if event in IGNORED_EVENTS:
        return None

    changes = action.get("changes")
    if changes is not None:
        if changes.get("description") is not None:
            event = "{}_{}".format(event, "description")
        elif changes.get("state") is not None:
            event = "{}_{}".format(event, "state")
        elif changes.get("workflow_state_id") is not None:
            event = "{}_{}".format(event, "state")
        elif changes.get("name") is not None:
            event = "{}_{}".format(event, "name")
        elif changes.get("archived") is not None:
            event = "{}_{}".format(event, "archived")
        elif changes.get("complete") is not None:
            event = "{}_{}".format(event, "complete")
        elif changes.get("epic_id") is not None:
            event = "{}_{}".format(event, "epic")
        elif changes.get("estimate") is not None:
            event = "{}_{}".format(event, "estimate")
        elif changes.get("file_ids") is not None:
            event = "{}_{}".format(event, "attachment")
        elif changes.get("label_ids") is not None:
            event = "{}_{}".format(event, "label")
        elif changes.get("project_id") is not None:
            event = "{}_{}".format(event, "project")
        elif changes.get("story_type") is not None:
            event = "{}_{}".format(event, "type")
        elif changes.get("owner_ids") is not None:
            event = "{}_{}".format(event, "owner")

    return event


def get_topic_function_based_on_type(payload: Dict[str, Any], action: Dict[str, Any]) -> Any:
    entity_type = action["entity_type"]
    return EVENT_TOPIC_FUNCTION_MAPPER.get(entity_type)


def get_delete_body(payload: Dict[str, Any], action: Dict[str, Any]) -> str:
    return DELETE_TEMPLATE.format(**action)


def get_story_create_body(payload: Dict[str, Any], action: Dict[str, Any]) -> str:
    if action.get("epic_id") is None:
        message = "New story [{name}]({app_url}) of type **{story_type}** was created."
        kwargs = action
    else:
        message = "New story [{name}]({app_url}) was created and added to the epic **{epic_name}**."
        kwargs = {
            "name": action["name"],
            "app_url": action["app_url"],
        }
        epic_id = action["epic_id"]
        refs = payload["references"]
        for ref in refs:
            if ref["id"] == epic_id:
                kwargs["epic_name"] = ref["name"]

    return message.format(**kwargs)


def get_epic_create_body(payload: Dict[str, Any], action: Dict[str, Any]) -> str:
    message = "New epic **{name}**({state}) was created."
    return message.format(**action)


def get_comment_added_body(payload: Dict[str, Any], action: Dict[str, Any], entity: str) -> str:
    actions = payload["actions"]
    kwargs = {"entity": entity}
    for action in actions:
        if action["id"] == payload["primary_id"]:
            kwargs["text"] = action["text"]
        elif action["entity_type"] == entity:
            name_template = get_name_template(entity).format(
                name=action["name"],
                app_url=action.get("app_url"),
            )
            kwargs["name_template"] = name_template

    return COMMENT_ADDED_TEMPLATE.format(**kwargs)


def get_update_description_body(
    payload: Dict[str, Any], action: Dict[str, Any], entity: str
) -> str:
    desc = action["changes"]["description"]

    kwargs = {
        "entity": entity,
        "new": desc["new"],
        "old": desc["old"],
        "name_template": get_name_template(entity).format(
            name=action["name"],
            app_url=action.get("app_url"),
        ),
    }

    if kwargs["new"] and kwargs["old"]:
        body = DESC_CHANGED_TEMPLATE.format(**kwargs)
    elif kwargs["new"]:
        body = NEW_DESC_ADDED_TEMPLATE.format(**kwargs)
    else:
        body = DESC_REMOVED_TEMPLATE.format(**kwargs)

    return body


def get_epic_update_state_body(payload: Dict[str, Any], action: Dict[str, Any]) -> str:
    state = action["changes"]["state"]
    kwargs = {
        "entity": "epic",
        "new": state["new"],
        "old": state["old"],
        "name_template": EPIC_NAME_TEMPLATE.format(name=action["name"]),
    }

    return STATE_CHANGED_TEMPLATE.format(**kwargs)


def get_story_update_state_body(payload: Dict[str, Any], action: Dict[str, Any]) -> str:
    workflow_state_id = action["changes"]["workflow_state_id"]
    references = payload["references"]

    state = {}
    for ref in references:
        if ref["id"] == workflow_state_id["new"]:
            state["new"] = ref["name"]
        if ref["id"] == workflow_state_id["old"]:
            state["old"] = ref["name"]

    kwargs = {
        "entity": "story",
        "new": state["new"],
        "old": state["old"],
        "name_template": STORY_NAME_TEMPLATE.format(
            name=action["name"],
            app_url=action.get("app_url"),
        ),
    }

    return STATE_CHANGED_TEMPLATE.format(**kwargs)


def get_update_name_body(payload: Dict[str, Any], action: Dict[str, Any], entity: str) -> str:
    name = action["changes"]["name"]
    kwargs = {
        "entity": entity,
        "new": name["new"],
        "old": name["old"],
        "name_template": get_name_template(entity).format(
            name=action["name"],
            app_url=action.get("app_url"),
        ),
    }

    return NAME_CHANGED_TEMPLATE.format(**kwargs)


def get_update_archived_body(payload: Dict[str, Any], action: Dict[str, Any], entity: str) -> str:
    archived = action["changes"]["archived"]
    if archived["new"]:
        operation = "archived"
    else:
        operation = "unarchived"

    kwargs = {
        "entity": entity,
        "name_template": get_name_template(entity).format(
            name=action["name"],
            app_url=action.get("app_url"),
        ),
        "operation": operation,
    }

    return ARCHIVED_TEMPLATE.format(**kwargs)


def get_story_task_body(payload: Dict[str, Any], action: Dict[str, Any], operation: str) -> str:
    kwargs = {
        "task_description": action["description"],
        "operation": operation,
    }

    for a in payload["actions"]:
        if a["entity_type"] == "story":
            kwargs["name_template"] = STORY_NAME_TEMPLATE.format(
                name=a["name"],
                app_url=a["app_url"],
            )

    return STORY_TASK_TEMPLATE.format(**kwargs)


def get_story_task_completed_body(payload: Dict[str, Any], action: Dict[str, Any]) -> Optional[str]:
    kwargs = {
        "task_description": action["description"],
    }

    story_id = action["story_id"]
    for ref in payload["references"]:
        if ref["id"] == story_id:
            kwargs["name_template"] = STORY_NAME_TEMPLATE.format(
                name=ref["name"],
                app_url=ref["app_url"],
            )

    if action["changes"]["complete"]["new"]:
        return STORY_TASK_COMPLETED_TEMPLATE.format(**kwargs)
    else:
        return None


def get_story_update_epic_body(payload: Dict[str, Any], action: Dict[str, Any]) -> str:
    kwargs = {
        "story_name_template": STORY_NAME_TEMPLATE.format(
            name=action["name"],
            app_url=action["app_url"],
        ),
    }

    new_id = action["changes"]["epic_id"].get("new")
    old_id = action["changes"]["epic_id"].get("old")

    for ref in payload["references"]:
        if ref["id"] == new_id:
            kwargs["new_epic_name_template"] = EPIC_NAME_TEMPLATE.format(name=ref["name"])

        if ref["id"] == old_id:
            kwargs["old_epic_name_template"] = EPIC_NAME_TEMPLATE.format(name=ref["name"])

    if new_id and old_id:
        return STORY_EPIC_CHANGED_TEMPLATE.format(**kwargs)
    elif new_id:
        kwargs["epic_name_template"] = kwargs["new_epic_name_template"]
        kwargs["operation"] = "added to"
    else:
        kwargs["epic_name_template"] = kwargs["old_epic_name_template"]
        kwargs["operation"] = "removed from"

    return STORY_ADDED_REMOVED_EPIC_TEMPLATE.format(**kwargs)


def get_story_update_estimate_body(payload: Dict[str, Any], action: Dict[str, Any]) -> str:
    kwargs = {
        "story_name_template": STORY_NAME_TEMPLATE.format(
            name=action["name"],
            app_url=action["app_url"],
        ),
    }

    new = action["changes"]["estimate"].get("new")
    if new:
        kwargs["estimate"] = f"{new} points"
    else:
        kwargs["estimate"] = "*Unestimated*"

    return STORY_ESTIMATE_TEMPLATE.format(**kwargs)


def get_reference_by_id(payload: Dict[str, Any], ref_id: int) -> Dict[str, Any]:
    ref: Dict[str, Any] = {}
    for reference in payload["references"]:
        if reference["id"] == ref_id:
            ref = reference

    return ref


def get_secondary_actions_with_param(
    payload: Dict[str, Any], entity: str, changed_attr: str
) -> Generator[Dict[str, Any], None, None]:
    # This function is a generator for secondary actions that have the required changed attributes,
    # i.e.: "story" that has "pull-request_ids" changed.
    for action in payload["actions"]:
        if action["entity_type"] == entity and action["changes"].get(changed_attr) is not None:
            yield action


def get_story_create_github_entity_body(
    payload: Dict[str, Any], action: Dict[str, Any], entity: str
) -> str:
    pull_request_action: Dict[str, Any] = get_action_with_primary_id(payload)

    kwargs = {
        "name_template": STORY_NAME_TEMPLATE.format(**action),
        "name": pull_request_action.get("number")
        if entity == "pull-request" or entity == "pull-request-comment"
        else pull_request_action.get("name"),
        "url": pull_request_action["url"],
        "workflow_state_template": "",
    }

    # Sometimes the workflow state of the story will not be changed when linking to a PR.
    if action["changes"].get("workflow_state_id") is not None:
        new_state_id = action["changes"]["workflow_state_id"]["new"]
        old_state_id = action["changes"]["workflow_state_id"]["old"]
        new_state = get_reference_by_id(payload, new_state_id)["name"]
        old_state = get_reference_by_id(payload, old_state_id)["name"]
        kwargs["workflow_state_template"] = TRAILING_WORKFLOW_STATE_CHANGE_TEMPLATE.format(
            new=new_state, old=old_state
        )

    if entity == "pull-request":
        template = STORY_GITHUB_PR_TEMPLATE
    elif entity == "pull-request-comment":
        template = STORY_GITHUB_COMMENT_PR_TEMPLATE
    else:
        template = STORY_GITHUB_BRANCH_TEMPLATE
    return template.format(**kwargs)


def get_story_update_attachment_body(
    payload: Dict[str, Any], action: Dict[str, Any]
) -> Optional[str]:
    kwargs = {
        "name_template": STORY_NAME_TEMPLATE.format(
            name=action["name"],
            app_url=action["app_url"],
        ),
    }
    file_ids_added = action["changes"]["file_ids"].get("adds")

    # If this is a payload for when an attachment is removed, ignore it
    if not file_ids_added:
        return None

    file_id = file_ids_added[0]
    for ref in payload["references"]:
        if ref["id"] == file_id:
            kwargs.update(
                type=ref["entity_type"],
                file_name=ref["name"],
            )

    return FILE_ATTACHMENT_TEMPLATE.format(**kwargs)


def get_story_joined_label_list(
    payload: Dict[str, Any], action: Dict[str, Any], label_ids_added: List[int]
) -> str:
    labels = []

    for label_id in label_ids_added:
        label_name = ""

        for action in payload["actions"]:
            if action.get("id") == label_id:
                label_name = action.get("name", "")

        if label_name == "":
            label_name = get_reference_by_id(payload, label_id).get("name", "")

        labels.append(LABEL_TEMPLATE.format(name=label_name))

    return ", ".join(labels)


def get_story_label_body(payload: Dict[str, Any], action: Dict[str, Any]) -> Optional[str]:
    kwargs = {
        "name_template": STORY_NAME_TEMPLATE.format(
            name=action["name"],
            app_url=action["app_url"],
        ),
    }
    label_ids_added = action["changes"]["label_ids"].get("adds")

    # If this is a payload for when no label is added, ignore it
    if not label_ids_added:
        return None

    kwargs.update(labels=get_story_joined_label_list(payload, action, label_ids_added))

    return (
        STORY_LABEL_TEMPLATE.format(**kwargs)
        if len(label_ids_added) == 1
        else STORY_LABEL_PLURAL_TEMPLATE.format(**kwargs)
    )


def get_story_update_project_body(payload: Dict[str, Any], action: Dict[str, Any]) -> str:
    kwargs = {
        "name_template": STORY_NAME_TEMPLATE.format(
            name=action["name"],
            app_url=action["app_url"],
        ),
    }

    new_project_id = action["changes"]["project_id"]["new"]
    old_project_id = action["changes"]["project_id"]["old"]
    for ref in payload["references"]:
        if ref["id"] == new_project_id:
            kwargs.update(new=ref["name"])
        if ref["id"] == old_project_id:
            kwargs.update(old=ref["name"])

    return STORY_UPDATE_PROJECT_TEMPLATE.format(**kwargs)


def get_story_update_type_body(payload: Dict[str, Any], action: Dict[str, Any]) -> str:
    kwargs = {
        "name_template": STORY_NAME_TEMPLATE.format(
            name=action["name"],
            app_url=action["app_url"],
        ),
        "new_type": action["changes"]["story_type"]["new"],
        "old_type": action["changes"]["story_type"]["old"],
    }

    return STORY_UPDATE_TYPE_TEMPLATE.format(**kwargs)


def get_story_update_owner_body(payload: Dict[str, Any], action: Dict[str, Any]) -> str:
    kwargs = {
        "name_template": STORY_NAME_TEMPLATE.format(
            name=action["name"],
            app_url=action["app_url"],
        ),
    }

    return STORY_UPDATE_OWNER_TEMPLATE.format(**kwargs)


def get_story_update_batch_body(payload: Dict[str, Any], action: Dict[str, Any]) -> Optional[str]:
    # When the user selects one or more stories with the checkbox, they can perform
    # a batch update on multiple stories while changing multiple attribtues at the
    # same time.
    changes = action["changes"]
    kwargs = {
        "name_template": STORY_NAME_TEMPLATE.format(
            name=action["name"],
            app_url=action["app_url"],
        ),
        "workflow_state_template": "",
    }

    templates = []
    last_change = "other"

    move_sub_templates = []
    if "epic_id" in changes:
        last_change = "epic"
        move_sub_templates.append(
            STORY_UPDATE_BATCH_CHANGED_SUB_TEMPLATE.format(
                entity_type="Epic",
                old=get_reference_by_id(payload, changes["epic_id"].get("old")).get("name"),
                new=get_reference_by_id(payload, changes["epic_id"].get("new")).get("name"),
            )
        )
    if "project_id" in changes:
        last_change = "project"
        move_sub_templates.append(
            STORY_UPDATE_BATCH_CHANGED_SUB_TEMPLATE.format(
                entity_type="Project",
                old=get_reference_by_id(payload, changes["project_id"].get("old")).get("name"),
                new=get_reference_by_id(payload, changes["project_id"].get("new")).get("name"),
            )
        )
    if len(move_sub_templates) > 0:
        templates.append(
            STORY_UPDATE_BATCH_CHANGED_TEMPLATE.format(
                operation="was moved",
                sub_templates=", ".join(move_sub_templates),
            )
        )

    if "story_type" in changes:
        last_change = "type"
        templates.append(
            STORY_UPDATE_BATCH_CHANGED_TEMPLATE.format(
                operation="{} changed".format("was" if len(templates) == 0 else "and"),
                sub_templates=STORY_UPDATE_BATCH_CHANGED_SUB_TEMPLATE.format(
                    entity_type="type",
                    old=changes["story_type"].get("old"),
                    new=changes["story_type"].get("new"),
                ),
            )
        )

    if "label_ids" in changes:
        label_ids_added = changes["label_ids"].get("adds")
        # If this is a payload for when no label is added, ignore it
        if label_ids_added is not None:
            last_change = "label"
            labels = get_story_joined_label_list(payload, action, label_ids_added)
            templates.append(
                STORY_UPDATE_BATCH_ADD_REMOVE_TEMPLATE.format(
                    operation="{} added".format("was" if len(templates) == 0 else "and"),
                    entity="the new label{plural} {labels}".format(
                        plural="s" if len(changes["label_ids"]) > 1 else "", labels=labels
                    ),
                )
            )

    if "workflow_state_id" in changes:
        last_change = "state"
        kwargs.update(
            workflow_state_template=TRAILING_WORKFLOW_STATE_CHANGE_TEMPLATE.format(
                old=get_reference_by_id(payload, changes["workflow_state_id"].get("old")).get(
                    "name"
                ),
                new=get_reference_by_id(payload, changes["workflow_state_id"].get("new")).get(
                    "name"
                ),
            )
        )

    # Use the default template for state change if it is the only one change.
    if len(templates) <= 1 or (len(templates) == 0 and last_change == "state"):
        event: str = "{}_{}".format("story_update", last_change)
        alternative_body_func = EVENT_BODY_FUNCTION_MAPPER.get(event)
        # If last_change is not one of "epic", "project", "type", "label" and "state"
        # we should ignore the action as there is no way for us to render the changes.
        if alternative_body_func is None:
            return None
        return alternative_body_func(payload, action)

    kwargs.update(templates=", ".join(templates))
    return STORY_UPDATE_BATCH_TEMPLATE.format(**kwargs)


def get_entity_name(
    payload: Dict[str, Any], action: Dict[str, Any], entity: Optional[str] = None
) -> Optional[str]:
    name = action.get("name")

    if name is None or action["entity_type"] == "branch":
        for action in payload["actions"]:
            if action["entity_type"] == entity:
                name = action["name"]

    if name is None:
        for ref in payload["references"]:
            if ref["entity_type"] == entity:
                name = ref["name"]

    return name


def get_name_template(entity: str) -> str:
    if entity == "story":
        return STORY_NAME_TEMPLATE
    return EPIC_NAME_TEMPLATE


def send_stream_messages_for_actions(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: Dict[str, Any],
    action: Dict[str, Any],
    event: str,
) -> None:
    body_func = EVENT_BODY_FUNCTION_MAPPER.get(event)
    topic_func = get_topic_function_based_on_type(payload, action)
    if body_func is None or topic_func is None:
        raise UnsupportedWebhookEventType(event)

    topic = topic_func(payload, action)
    body = body_func(payload, action)

    if topic and body:
        check_send_webhook_message(request, user_profile, topic, body, event)


EVENT_BODY_FUNCTION_MAPPER: Dict[str, Callable[[Dict[str, Any], Dict[str, Any]], Optional[str]]] = {
    "story_update_archived": partial(get_update_archived_body, entity="story"),
    "epic_update_archived": partial(get_update_archived_body, entity="epic"),
    "story_create": get_story_create_body,
    "pull-request_create": partial(get_story_create_github_entity_body, entity="pull-request"),
    "pull-request_comment": partial(
        get_story_create_github_entity_body, entity="pull-request-comment"
    ),
    "branch_create": partial(get_story_create_github_entity_body, entity="branch"),
    "story_delete": get_delete_body,
    "epic_delete": get_delete_body,
    "story-task_create": partial(get_story_task_body, operation="added to"),
    "story-task_delete": partial(get_story_task_body, operation="removed from"),
    "story-task_update_complete": get_story_task_completed_body,
    "story_update_epic": get_story_update_epic_body,
    "story_update_estimate": get_story_update_estimate_body,
    "story_update_attachment": get_story_update_attachment_body,
    "story_update_label": get_story_label_body,
    "story_update_owner": get_story_update_owner_body,
    "story_update_project": get_story_update_project_body,
    "story_update_type": get_story_update_type_body,
    "epic_create": get_epic_create_body,
    "epic-comment_create": partial(get_comment_added_body, entity="epic"),
    "story-comment_create": partial(get_comment_added_body, entity="story"),
    "epic_update_description": partial(get_update_description_body, entity="epic"),
    "story_update_description": partial(get_update_description_body, entity="story"),
    "epic_update_state": get_epic_update_state_body,
    "story_update_state": get_story_update_state_body,
    "epic_update_name": partial(get_update_name_body, entity="epic"),
    "story_update_name": partial(get_update_name_body, entity="story"),
    "story_update_batch": get_story_update_batch_body,
}

ALL_EVENT_TYPES = list(EVENT_BODY_FUNCTION_MAPPER.keys())

EVENT_TOPIC_FUNCTION_MAPPER = {
    "story": partial(get_entity_name, entity="story"),
    "pull-request": partial(get_entity_name, entity="story"),
    "branch": partial(get_entity_name, entity="story"),
    "story-comment": partial(get_entity_name, entity="story"),
    "story-task": partial(get_entity_name, entity="story"),
    "epic": partial(get_entity_name, entity="epic"),
    "epic-comment": partial(get_entity_name, entity="epic"),
}

IGNORED_EVENTS = {
    "story-comment_update",
}

EVENTS_SECONDARY_ACTIONS_FUNCTION_MAPPER: Dict[
    str, Callable[[Dict[str, Any]], Generator[Dict[str, Any], None, None]]
] = {
    "pull-request_create": partial(
        get_secondary_actions_with_param, entity="story", changed_attr="pull_request_ids"
    ),
    "branch_create": partial(
        get_secondary_actions_with_param, entity="story", changed_attr="branch_ids"
    ),
    "pull-request_comment": partial(
        get_secondary_actions_with_param, entity="story", changed_attr="pull_request_ids"
    ),
}


@webhook_view("Clubhouse", all_event_types=ALL_EVENT_TYPES)
@has_request_variables
def api_clubhouse_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: Optional[Dict[str, Any]] = REQ(argument_type="body"),
) -> HttpResponse:

    # Clubhouse has a tendency to send empty POST requests to
    # third-party endpoints. It is unclear as to which event type
    # such requests correspond to. So, it is best to ignore such
    # requests for now.
    if payload is None:
        return json_success()

    if payload.get("primary_id") is not None:
        action = get_action_with_primary_id(payload)
        primary_actions = [action]
    else:
        primary_actions = payload["actions"]

    for primary_action in primary_actions:
        event = get_event(payload, primary_action)
        if event is None:
            continue

        if event in EVENTS_SECONDARY_ACTIONS_FUNCTION_MAPPER:
            sec_actions_func = EVENTS_SECONDARY_ACTIONS_FUNCTION_MAPPER[event]
            for sec_action in sec_actions_func(payload):
                send_stream_messages_for_actions(request, user_profile, payload, sec_action, event)
        else:
            send_stream_messages_for_actions(request, user_profile, payload, primary_action, event)

    return json_success()
