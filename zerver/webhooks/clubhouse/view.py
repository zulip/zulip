from typing import Callable, Dict, Iterable, Iterator, List, Optional

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.partial import partial
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import (
    WildValue,
    check_bool,
    check_int,
    check_list,
    check_none_or,
    check_string,
    check_string_or_int,
)
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


def get_action_with_primary_id(payload: WildValue) -> WildValue:
    for action in payload["actions"]:
        if payload["primary_id"] == action["id"]:
            action_with_primary_id = action

    return action_with_primary_id


def get_event(payload: WildValue, action: WildValue) -> Optional[str]:
    event = "{}_{}".format(
        action["entity_type"].tame(check_string), action["action"].tame(check_string)
    )

    # We only consider the change to be a batch update only if there are multiple stories (thus there is no primary_id)
    if event == "story_update" and "primary_id" not in payload:
        return "{}_{}".format(event, "batch")

    if event in IGNORED_EVENTS:
        return None

    if "changes" in action:
        changes = action["changes"]
        if "description" in changes:
            event = "{}_{}".format(event, "description")
        elif "state" in changes:
            event = "{}_{}".format(event, "state")
        elif "workflow_state_id" in changes:
            event = "{}_{}".format(event, "state")
        elif "name" in changes:
            event = "{}_{}".format(event, "name")
        elif "archived" in changes:
            event = "{}_{}".format(event, "archived")
        elif "complete" in changes:
            event = "{}_{}".format(event, "complete")
        elif "epic_id" in changes:
            event = "{}_{}".format(event, "epic")
        elif "estimate" in changes:
            event = "{}_{}".format(event, "estimate")
        elif "file_ids" in changes:
            event = "{}_{}".format(event, "attachment")
        elif "label_ids" in changes:
            event = "{}_{}".format(event, "label")
        elif "project_id" in changes:
            event = "{}_{}".format(event, "project")
        elif "story_type" in changes:
            event = "{}_{}".format(event, "type")
        elif "owner_ids" in changes:
            event = "{}_{}".format(event, "owner")

    return event


def get_topic_function_based_on_type(
    payload: WildValue, action: WildValue
) -> Optional[Callable[[WildValue, WildValue], Optional[str]]]:
    entity_type = action["entity_type"].tame(check_string)
    return EVENT_TOPIC_FUNCTION_MAPPER.get(entity_type)


def get_delete_body(payload: WildValue, action: WildValue) -> str:
    return DELETE_TEMPLATE.format(
        entity_type=action["entity_type"].tame(check_string),
        name=action["name"].tame(check_string),
    )


def get_story_create_body(payload: WildValue, action: WildValue) -> str:
    if "epic_id" not in action:
        message = "New story [{name}]({app_url}) of type **{story_type}** was created."
        kwargs = {
            "name": action["name"].tame(check_string),
            "app_url": action["app_url"].tame(check_string),
            "story_type": action["story_type"].tame(check_string),
        }
    else:
        message = "New story [{name}]({app_url}) was created and added to the epic **{epic_name}**."
        kwargs = {
            "name": action["name"].tame(check_string),
            "app_url": action["app_url"].tame(check_string),
        }
        epic_id = action["epic_id"].tame(check_int)
        refs = payload["references"]
        for ref in refs:
            if ref["id"].tame(check_string_or_int) == epic_id:
                kwargs["epic_name"] = ref["name"].tame(check_string)

    return message.format(**kwargs)


def get_epic_create_body(payload: WildValue, action: WildValue) -> str:
    message = "New epic **{name}**({state}) was created."
    return message.format(
        name=action["name"].tame(check_string),
        state=action["state"].tame(check_string),
    )


def get_comment_added_body(entity: str, payload: WildValue, action: WildValue) -> str:
    actions = payload["actions"]
    kwargs = {"entity": entity}
    for action in actions:
        if action["id"] == payload["primary_id"]:
            kwargs["text"] = action["text"].tame(check_string)
        elif action["entity_type"] == entity:
            name_template = get_name_template(entity).format(
                name=action["name"].tame(check_string),
                app_url=action.get("app_url").tame(check_none_or(check_string)),
            )
            kwargs["name_template"] = name_template

    return COMMENT_ADDED_TEMPLATE.format(**kwargs)


def get_update_description_body(entity: str, payload: WildValue, action: WildValue) -> str:
    desc = action["changes"]["description"]

    kwargs = {
        "entity": entity,
        "new": desc["new"].tame(check_string),
        "old": desc["old"].tame(check_string),
        "name_template": get_name_template(entity).format(
            name=action["name"].tame(check_string),
            app_url=action.get("app_url").tame(check_none_or(check_string)),
        ),
    }

    if kwargs["new"] and kwargs["old"]:
        body = DESC_CHANGED_TEMPLATE.format(**kwargs)
    elif kwargs["new"]:
        body = NEW_DESC_ADDED_TEMPLATE.format(**kwargs)
    else:
        body = DESC_REMOVED_TEMPLATE.format(**kwargs)

    return body


def get_epic_update_state_body(payload: WildValue, action: WildValue) -> str:
    state = action["changes"]["state"]
    kwargs = {
        "entity": "epic",
        "new": state["new"].tame(check_string),
        "old": state["old"].tame(check_string),
        "name_template": EPIC_NAME_TEMPLATE.format(
            name=action["name"].tame(check_string),
        ),
    }

    return STATE_CHANGED_TEMPLATE.format(**kwargs)


def get_story_update_state_body(payload: WildValue, action: WildValue) -> str:
    workflow_state_id = action["changes"]["workflow_state_id"]
    references = payload["references"]

    state = {}
    for ref in references:
        if ref["id"].tame(check_string_or_int) == workflow_state_id["new"].tame(check_int):
            state["new"] = ref["name"].tame(check_string)
        if ref["id"].tame(check_string_or_int) == workflow_state_id["old"].tame(check_int):
            state["old"] = ref["name"].tame(check_string)

    kwargs = {
        "entity": "story",
        "new": state["new"],
        "old": state["old"],
        "name_template": STORY_NAME_TEMPLATE.format(
            name=action["name"].tame(check_string),
            app_url=action.get("app_url").tame(check_none_or(check_string)),
        ),
    }

    return STATE_CHANGED_TEMPLATE.format(**kwargs)


def get_update_name_body(entity: str, payload: WildValue, action: WildValue) -> str:
    name = action["changes"]["name"]
    kwargs = {
        "entity": entity,
        "new": name["new"].tame(check_string),
        "old": name["old"].tame(check_string),
        "name_template": get_name_template(entity).format(
            name=action["name"].tame(check_string),
            app_url=action.get("app_url").tame(check_none_or(check_string)),
        ),
    }

    return NAME_CHANGED_TEMPLATE.format(**kwargs)


def get_update_archived_body(entity: str, payload: WildValue, action: WildValue) -> str:
    archived = action["changes"]["archived"]
    if archived["new"]:
        operation = "archived"
    else:
        operation = "unarchived"

    kwargs = {
        "entity": entity,
        "name_template": get_name_template(entity).format(
            name=action["name"].tame(check_string),
            app_url=action.get("app_url").tame(check_none_or(check_string)),
        ),
        "operation": operation,
    }

    return ARCHIVED_TEMPLATE.format(**kwargs)


def get_story_task_body(operation: str, payload: WildValue, action: WildValue) -> str:
    kwargs = {
        "task_description": action["description"].tame(check_string),
        "operation": operation,
    }

    for a in payload["actions"]:
        if a["entity_type"].tame(check_string) == "story":
            kwargs["name_template"] = STORY_NAME_TEMPLATE.format(
                name=a["name"].tame(check_string),
                app_url=a["app_url"].tame(check_string),
            )

    return STORY_TASK_TEMPLATE.format(**kwargs)


def get_story_task_completed_body(payload: WildValue, action: WildValue) -> Optional[str]:
    kwargs = {
        "task_description": action["description"].tame(check_string),
    }

    story_id = action["story_id"].tame(check_int)
    for ref in payload["references"]:
        if ref["id"].tame(check_string_or_int) == story_id:
            kwargs["name_template"] = STORY_NAME_TEMPLATE.format(
                name=ref["name"].tame(check_string),
                app_url=ref["app_url"].tame(check_string),
            )

    if action["changes"]["complete"]["new"].tame(check_bool):
        return STORY_TASK_COMPLETED_TEMPLATE.format(**kwargs)
    else:
        return None


def get_story_update_epic_body(payload: WildValue, action: WildValue) -> str:
    kwargs = {
        "story_name_template": STORY_NAME_TEMPLATE.format(
            name=action["name"].tame(check_string),
            app_url=action["app_url"].tame(check_string),
        ),
    }

    epic_id = action["changes"]["epic_id"]
    new_id = epic_id.get("new").tame(check_none_or(check_int))
    old_id = epic_id.get("old").tame(check_none_or(check_int))

    for ref in payload["references"]:
        if ref["id"].tame(check_string_or_int) == new_id:
            kwargs["new_epic_name_template"] = EPIC_NAME_TEMPLATE.format(
                name=ref["name"].tame(check_string),
            )

        if ref["id"].tame(check_string_or_int) == old_id:
            kwargs["old_epic_name_template"] = EPIC_NAME_TEMPLATE.format(
                name=ref["name"].tame(check_string),
            )

    if new_id and old_id:
        return STORY_EPIC_CHANGED_TEMPLATE.format(**kwargs)
    elif new_id:
        kwargs["epic_name_template"] = kwargs["new_epic_name_template"]
        kwargs["operation"] = "added to"
    else:
        kwargs["epic_name_template"] = kwargs["old_epic_name_template"]
        kwargs["operation"] = "removed from"

    return STORY_ADDED_REMOVED_EPIC_TEMPLATE.format(**kwargs)


def get_story_update_estimate_body(payload: WildValue, action: WildValue) -> str:
    kwargs = {
        "story_name_template": STORY_NAME_TEMPLATE.format(
            name=action["name"].tame(check_string),
            app_url=action["app_url"].tame(check_string),
        ),
    }

    estimate = action["changes"]["estimate"]
    if "new" in estimate:
        new = estimate["new"].tame(check_int)
        kwargs["estimate"] = f"{new} points"
    else:
        kwargs["estimate"] = "*Unestimated*"

    return STORY_ESTIMATE_TEMPLATE.format(**kwargs)


def get_reference_by_id(payload: WildValue, ref_id: Optional[int]) -> Optional[WildValue]:
    ref = None
    for reference in payload["references"]:
        if reference["id"].tame(check_string_or_int) == ref_id:
            ref = reference

    return ref


def get_secondary_actions_with_param(
    entity: str, changed_attr: str, payload: WildValue
) -> Iterator[WildValue]:
    # This function is a generator for secondary actions that have the required changed attributes,
    # i.e.: "story" that has "pull-request_ids" changed.
    for action in payload["actions"]:
        if action["entity_type"].tame(check_string) == entity and changed_attr in action["changes"]:
            yield action


def get_story_create_github_entity_body(entity: str, payload: WildValue, action: WildValue) -> str:
    pull_request_action: WildValue = get_action_with_primary_id(payload)

    kwargs = {
        "name_template": STORY_NAME_TEMPLATE.format(
            name=action["name"].tame(check_string),
            app_url=action["app_url"].tame(check_string),
        ),
        "name": (
            pull_request_action["number"].tame(check_int)
            if entity in ("pull-request", "pull-request-comment")
            else pull_request_action["name"].tame(check_string)
        ),
        "url": pull_request_action["url"].tame(check_string),
        "workflow_state_template": "",
    }

    # Sometimes the workflow state of the story will not be changed when linking to a PR.
    if "workflow_state_id" in action["changes"]:
        workflow_state_id = action["changes"]["workflow_state_id"]
        new_state_id = workflow_state_id["new"].tame(check_int)
        old_state_id = workflow_state_id["old"].tame(check_int)
        new_reference = get_reference_by_id(payload, new_state_id)
        assert new_reference is not None
        new_state = new_reference["name"].tame(check_string)
        old_reference = get_reference_by_id(payload, old_state_id)
        assert old_reference is not None
        old_state = old_reference["name"].tame(check_string)
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


def get_story_update_attachment_body(payload: WildValue, action: WildValue) -> Optional[str]:
    kwargs = {
        "name_template": STORY_NAME_TEMPLATE.format(
            name=action["name"].tame(check_string),
            app_url=action["app_url"].tame(check_string),
        ),
    }
    file_ids = action["changes"]["file_ids"]

    # If this is a payload for when an attachment is removed, ignore it
    if "adds" not in file_ids:
        return None

    file_ids_added = file_ids["adds"].tame(check_list(check_int))
    file_id = file_ids_added[0]
    for ref in payload["references"]:
        if ref["id"].tame(check_string_or_int) == file_id:
            kwargs.update(
                type=ref["entity_type"].tame(check_string),
                file_name=ref["name"].tame(check_string),
            )

    return FILE_ATTACHMENT_TEMPLATE.format(**kwargs)


def get_story_joined_label_list(
    payload: WildValue, action: WildValue, label_ids_added: List[int]
) -> str:
    labels = []

    for label_id in label_ids_added:
        label_name = ""

        for action in payload["actions"]:
            if action["id"].tame(check_int) == label_id:
                label_name = action.get("name", "").tame(check_string)

        if label_name == "":
            reference = get_reference_by_id(payload, label_id)
            label_name = "" if reference is None else reference["name"].tame(check_string)

        labels.append(LABEL_TEMPLATE.format(name=label_name))

    return ", ".join(labels)


def get_story_label_body(payload: WildValue, action: WildValue) -> Optional[str]:
    kwargs = {
        "name_template": STORY_NAME_TEMPLATE.format(
            name=action["name"].tame(check_string),
            app_url=action["app_url"].tame(check_string),
        ),
    }
    label_ids = action["changes"]["label_ids"]

    # If this is a payload for when no label is added, ignore it
    if "adds" not in label_ids:
        return None

    label_ids_added = label_ids["adds"].tame(check_list(check_int))
    kwargs.update(labels=get_story_joined_label_list(payload, action, label_ids_added))

    return (
        STORY_LABEL_TEMPLATE.format(**kwargs)
        if len(label_ids_added) == 1
        else STORY_LABEL_PLURAL_TEMPLATE.format(**kwargs)
    )


def get_story_update_project_body(payload: WildValue, action: WildValue) -> str:
    kwargs = {
        "name_template": STORY_NAME_TEMPLATE.format(
            name=action["name"].tame(check_string),
            app_url=action["app_url"].tame(check_string),
        ),
    }

    project_id = action["changes"]["project_id"]
    new_project_id = project_id["new"].tame(check_int)
    old_project_id = project_id["old"].tame(check_int)
    for ref in payload["references"]:
        if ref["id"].tame(check_string_or_int) == new_project_id:
            kwargs.update(new=ref["name"].tame(check_string))
        if ref["id"].tame(check_string_or_int) == old_project_id:
            kwargs.update(old=ref["name"].tame(check_string))

    return STORY_UPDATE_PROJECT_TEMPLATE.format(**kwargs)


def get_story_update_type_body(payload: WildValue, action: WildValue) -> str:
    story_type = action["changes"]["story_type"]
    kwargs = {
        "name_template": STORY_NAME_TEMPLATE.format(
            name=action["name"].tame(check_string),
            app_url=action["app_url"].tame(check_string),
        ),
        "new_type": story_type["new"].tame(check_string),
        "old_type": story_type["old"].tame(check_string),
    }

    return STORY_UPDATE_TYPE_TEMPLATE.format(**kwargs)


def get_story_update_owner_body(payload: WildValue, action: WildValue) -> str:
    kwargs = {
        "name_template": STORY_NAME_TEMPLATE.format(
            name=action["name"].tame(check_string),
            app_url=action["app_url"].tame(check_string),
        ),
    }

    return STORY_UPDATE_OWNER_TEMPLATE.format(**kwargs)


def get_story_update_batch_body(payload: WildValue, action: WildValue) -> Optional[str]:
    # When the user selects one or more stories with the checkbox, they can perform
    # a batch update on multiple stories while changing multiple attributes at the
    # same time.
    changes = action["changes"]
    kwargs = {
        "name_template": STORY_NAME_TEMPLATE.format(
            name=action["name"].tame(check_string),
            app_url=action["app_url"].tame(check_string),
        ),
        "workflow_state_template": "",
    }

    templates = []
    last_change = "other"

    move_sub_templates = []
    if "epic_id" in changes:
        last_change = "epic"
        epic_id = changes["epic_id"]
        old_reference = get_reference_by_id(
            payload, epic_id.get("old").tame(check_none_or(check_int))
        )
        new_reference = get_reference_by_id(
            payload, epic_id.get("new").tame(check_none_or(check_int))
        )
        move_sub_templates.append(
            STORY_UPDATE_BATCH_CHANGED_SUB_TEMPLATE.format(
                entity_type="Epic",
                old=None if old_reference is None else old_reference["name"].tame(check_string),
                new=None if new_reference is None else new_reference["name"].tame(check_string),
            )
        )
    if "project_id" in changes:
        last_change = "project"
        project_id = changes["project_id"]
        old_reference = get_reference_by_id(
            payload, project_id.get("old").tame(check_none_or(check_int))
        )
        new_reference = get_reference_by_id(
            payload, project_id.get("new").tame(check_none_or(check_int))
        )
        move_sub_templates.append(
            STORY_UPDATE_BATCH_CHANGED_SUB_TEMPLATE.format(
                entity_type="Project",
                old=None if old_reference is None else old_reference["name"].tame(check_string),
                new=None if new_reference is None else new_reference["name"].tame(check_string),
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
        story_type = changes["story_type"]
        templates.append(
            STORY_UPDATE_BATCH_CHANGED_TEMPLATE.format(
                operation="{} changed".format("was" if len(templates) == 0 else "and"),
                sub_templates=STORY_UPDATE_BATCH_CHANGED_SUB_TEMPLATE.format(
                    entity_type="type",
                    old=story_type.get("old").tame(check_none_or(check_string)),
                    new=story_type.get("new").tame(check_none_or(check_string)),
                ),
            )
        )

    if "label_ids" in changes:
        label_ids = changes["label_ids"]
        # If this is a payload for when no label is added, ignore it
        if "adds" in label_ids:
            label_ids_added = label_ids["adds"].tame(check_list(check_int))
            last_change = "label"
            labels = get_story_joined_label_list(payload, action, label_ids_added)
            templates.append(
                STORY_UPDATE_BATCH_ADD_REMOVE_TEMPLATE.format(
                    operation="{} added".format("was" if len(templates) == 0 else "and"),
                    entity="the new label{plural} {labels}".format(
                        plural="s" if len(label_ids) > 1 else "", labels=labels
                    ),
                )
            )

    if "workflow_state_id" in changes:
        last_change = "state"
        workflow_state_id = changes["workflow_state_id"]
        old_reference = get_reference_by_id(
            payload, workflow_state_id.get("old").tame(check_none_or(check_int))
        )
        new_reference = get_reference_by_id(
            payload, workflow_state_id.get("new").tame(check_none_or(check_int))
        )
        kwargs.update(
            workflow_state_template=TRAILING_WORKFLOW_STATE_CHANGE_TEMPLATE.format(
                old=None if old_reference is None else old_reference["name"].tame(check_string),
                new=None if new_reference is None else new_reference["name"].tame(check_string),
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


def get_entity_name(entity: str, payload: WildValue, action: WildValue) -> Optional[str]:
    name = action["name"].tame(check_string) if "name" in action else None

    if name is None or action["entity_type"] == "branch":
        for action in payload["actions"]:
            if action["entity_type"].tame(check_string) == entity:
                name = action["name"].tame(check_string)

    if name is None:
        for ref in payload["references"]:
            if ref["entity_type"].tame(check_string) == entity:
                name = ref["name"].tame(check_string)

    return name


def get_name_template(entity: str) -> str:
    if entity == "story":
        return STORY_NAME_TEMPLATE
    return EPIC_NAME_TEMPLATE


def send_channel_messages_for_actions(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: WildValue,
    action: WildValue,
    event: str,
) -> None:
    body_func = EVENT_BODY_FUNCTION_MAPPER.get(event)
    topic_func = get_topic_function_based_on_type(payload, action)
    if body_func is None or topic_func is None:
        raise UnsupportedWebhookEventTypeError(event)

    topic_name = topic_func(payload, action)
    body = body_func(payload, action)

    if topic_name and body:
        check_send_webhook_message(request, user_profile, topic_name, body, event)


EVENT_BODY_FUNCTION_MAPPER: Dict[str, Callable[[WildValue, WildValue], Optional[str]]] = {
    "story_update_archived": partial(get_update_archived_body, "story"),
    "epic_update_archived": partial(get_update_archived_body, "epic"),
    "story_create": get_story_create_body,
    "pull-request_create": partial(get_story_create_github_entity_body, "pull-request"),
    "pull-request_comment": partial(get_story_create_github_entity_body, "pull-request-comment"),
    "branch_create": partial(get_story_create_github_entity_body, "branch"),
    "story_delete": get_delete_body,
    "epic_delete": get_delete_body,
    "story-task_create": partial(get_story_task_body, "added to"),
    "story-task_delete": partial(get_story_task_body, "removed from"),
    "story-task_update_complete": get_story_task_completed_body,
    "story_update_epic": get_story_update_epic_body,
    "story_update_estimate": get_story_update_estimate_body,
    "story_update_attachment": get_story_update_attachment_body,
    "story_update_label": get_story_label_body,
    "story_update_owner": get_story_update_owner_body,
    "story_update_project": get_story_update_project_body,
    "story_update_type": get_story_update_type_body,
    "epic_create": get_epic_create_body,
    "epic-comment_create": partial(get_comment_added_body, "epic"),
    "story-comment_create": partial(get_comment_added_body, "story"),
    "epic_update_description": partial(get_update_description_body, "epic"),
    "story_update_description": partial(get_update_description_body, "story"),
    "epic_update_state": get_epic_update_state_body,
    "story_update_state": get_story_update_state_body,
    "epic_update_name": partial(get_update_name_body, "epic"),
    "story_update_name": partial(get_update_name_body, "story"),
    "story_update_batch": get_story_update_batch_body,
}

ALL_EVENT_TYPES = list(EVENT_BODY_FUNCTION_MAPPER.keys())

EVENT_TOPIC_FUNCTION_MAPPER: Dict[str, Callable[[WildValue, WildValue], Optional[str]]] = {
    "story": partial(get_entity_name, "story"),
    "pull-request": partial(get_entity_name, "story"),
    "branch": partial(get_entity_name, "story"),
    "story-comment": partial(get_entity_name, "story"),
    "story-task": partial(get_entity_name, "story"),
    "epic": partial(get_entity_name, "epic"),
    "epic-comment": partial(get_entity_name, "epic"),
}

IGNORED_EVENTS = {
    "story-comment_update",
}

EVENTS_SECONDARY_ACTIONS_FUNCTION_MAPPER: Dict[str, Callable[[WildValue], Iterator[WildValue]]] = {
    "pull-request_create": partial(get_secondary_actions_with_param, "story", "pull_request_ids"),
    "branch_create": partial(get_secondary_actions_with_param, "story", "branch_ids"),
    "pull-request_comment": partial(get_secondary_actions_with_param, "story", "pull_request_ids"),
}


@webhook_view("Clubhouse", all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_clubhouse_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
) -> HttpResponse:
    # Clubhouse has a tendency to send empty POST requests to
    # third-party endpoints. It is unclear as to which event type
    # such requests correspond to. So, it is best to ignore such
    # requests for now.
    if payload.value is None:
        return json_success(request)

    if "primary_id" in payload:
        action = get_action_with_primary_id(payload)
        primary_actions: Iterable[WildValue] = [action]
    else:
        primary_actions = payload["actions"]

    for primary_action in primary_actions:
        event = get_event(payload, primary_action)
        if event is None:
            continue

        if event in EVENTS_SECONDARY_ACTIONS_FUNCTION_MAPPER:
            sec_actions_func = EVENTS_SECONDARY_ACTIONS_FUNCTION_MAPPER[event]
            for sec_action in sec_actions_func(payload):
                send_channel_messages_for_actions(request, user_profile, payload, sec_action, event)
        else:
            send_channel_messages_for_actions(request, user_profile, payload, primary_action, event)

    return json_success(request)
