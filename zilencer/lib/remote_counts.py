from datetime import timedelta

from django.db import connection
from django.utils.timezone import now as timezone_now
from psycopg2.sql import SQL, Literal

from zilencer.models import RemoteInstallationCount, RemoteZulipServer


class MissingDataError(Exception):
    pass


def compute_max_monthly_messages(remote_server: RemoteZulipServer) -> int:
    # Calculate the maximum amount of messages that the server had within a month.
    # out of the last 3 months.

    # We would like to just check whether we have current data for the
    # actual property we care about
    # ('messages_sent:message_type:day'). But because our analytics
    # tables have implicit zeros, that can't distinguish missing data
    # from days with no messages. So we filter on `active_users_audit`
    # instead, which will never be zero for an initialized server.
    if not RemoteInstallationCount.objects.filter(
        server=remote_server,
        property="active_users_audit:is_bot:day",
        end_time__lte=timezone_now() - timedelta(days=3),
    ).exists():
        raise MissingDataError

    query = SQL(
        """
    WITH server_message_stats_daily AS -- Up to 4 rows per day for different subgroups
    (
        SELECT
            r.end_time,
            r.value AS message_count
        FROM
            zilencer_remoteinstallationcount r
        WHERE
            r.property = 'messages_sent:message_type:day'
            AND end_time >= CURRENT_TIMESTAMP(0) - INTERVAL '90 days'
            AND r.server_id = {server_id}
    ),
    server_message_stats_monthly AS (
        SELECT
            CASE
                WHEN current_timestamp(0) - end_time <= INTERVAL '30 days' THEN 0
                WHEN current_timestamp(0) - end_time <= INTERVAL '60 days' THEN 1
                WHEN current_timestamp(0) - end_time <= INTERVAL '90 days' THEN 2
            END AS billing_month,
            SUM(message_count) AS message_count
        FROM
            server_message_stats_daily
        GROUP BY
            1
    ),
    server_max_monthly_messages AS (
        SELECT
            MAX(message_count) AS message_count
        FROM
            server_message_stats_monthly
        WHERE
            billing_month IS NOT NULL
    )
    SELECT
        -- Return zeros, rather than nulls,
        -- for reporting servers with zero messages.
        COALESCE(server_max_monthly_messages.message_count, 0) AS message_count
    FROM
        server_max_monthly_messages;
        """
    ).format(server_id=Literal(remote_server.id))
    with connection.cursor() as cursor:
        cursor.execute(query)
        result = cursor.fetchone()[0]
    return int(result)
