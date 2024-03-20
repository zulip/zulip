from enum import Enum
from typing import List


class ConstantVariable(Enum):
    @classmethod
    def as_list(cls) -> List[str]:
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


class SimpleFields(ConstantVariable):
    # Events with identical payload format
    PRIORITY: str = "priority"
    STATUS: str = "status"


class SpecialFields(ConstantVariable):
    # Event with unique payload
    NAME: str = "name"
    ASSIGNEE: str = "assignee_add"
    COMMENT: str = "comment"
    DUE_DATE: str = "due_date"
    MOVED: str = "section_moved"
    TIME_ESTIMATE: str = "time_estimate"
    TIME_SPENT: str = "time_spent"


class SpammyFields(ConstantVariable):
    TAG: str = "tag"
    TAG_REMOVED: str = "tag_removed"
    UNASSIGN: str = "assignee_rem"
