from sqlalchemy.sql import ColumnElement, and_, column, func, literal, literal_column, select, table
from sqlalchemy.types import Boolean, Text

from zerver.lib.topic import RESOLVED_TOPIC_PREFIX
from zerver.models import UserTopic


def topic_match_sa(topic_name: str) -> ColumnElement[Boolean]:
    # _sa is short for SQLAlchemy, which we use mostly for
    # queries that search messages
    topic_cond = and_(
        func.upper(column("subject", Text)) == func.upper(literal(topic_name)),
        column("is_channel_message", Boolean),
    )
    return topic_cond


def get_resolved_topic_condition_sa() -> ColumnElement[Boolean]:
    resolved_topic_cond = and_(
        column("subject", Text).startswith(RESOLVED_TOPIC_PREFIX),
        column("is_channel_message", Boolean),
    )
    return resolved_topic_cond


def topic_column_sa() -> ColumnElement[Text]:
    return column("subject", Text)


def get_followed_topic_condition_sa(user_id: int) -> ColumnElement[Boolean]:
    follow_topic_cond = (
        select(1)
        .select_from(table("zerver_usertopic"))
        .where(
            and_(
                literal_column("zerver_usertopic.user_profile_id") == literal(user_id),
                literal_column("zerver_usertopic.visibility_policy")
                == literal(UserTopic.VisibilityPolicy.FOLLOWED),
                func.upper(literal_column("zerver_usertopic.topic_name"))
                == func.upper(literal_column("zerver_message.subject")),
                literal_column("zerver_message.is_channel_message", Boolean),
                literal_column("zerver_usertopic.recipient_id")
                == literal_column("zerver_message.recipient_id"),
            )
        )
    ).exists()
    return follow_topic_cond
