from sqlalchemy.sql import ColumnElement, column, func, literal
from sqlalchemy.types import Boolean, Text

from zerver.lib.topic import RESOLVED_TOPIC_PREFIX


def topic_match_sa(topic_name: str) -> ColumnElement[Boolean]:
    # _sa is short for SQLAlchemy, which we use mostly for
    # queries that search messages
    topic_cond = func.upper(column("subject", Text)) == func.upper(literal(topic_name))
    return topic_cond


def get_resolved_topic_condition_sa() -> ColumnElement[Boolean]:
    resolved_topic_cond = column("subject", Text).startswith(RESOLVED_TOPIC_PREFIX)
    return resolved_topic_cond


def topic_column_sa() -> ColumnElement[Text]:
    return column("subject", Text)
