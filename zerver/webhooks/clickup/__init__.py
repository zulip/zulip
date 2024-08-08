from enum import Enum


class ConstantVariable(Enum):
    @classmethod
    def as_list(cls) -> list[str]:
        return [item.value for item in cls]


class EventItemType(ConstantVariable):
    TASK: str = "task"
    LIST: str = "list"
    FOLDER: str = "folder"
    GOAL: str = "goal"
    SPACE: str = "space"


class EventAcion(ConstantVariable):
    CREATED: str = "Created"
    UPDATED: str = "Updated"
    DELETED: str = "Deleted"


SIMPLE_FIELDS = ["priority", "status"]


class SpecialFields(ConstantVariable):
    # Event with unique payload
    NAME: str = "name"
    ASSIGNEE: str = "assignee_add"
    COMMENT: str = "comment"
    DUE_DATE: str = "due_date"
    MOVED: str = "section_moved"
    TIME_ESTIMATE: str = "time_estimate"
    TIME_SPENT: str = "time_spent"


SPAMMY_FIELDS = ["tag", "tag_removed", "assignee_rem"]
