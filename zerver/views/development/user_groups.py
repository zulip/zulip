import threading
from typing import Any, Optional
from unittest import mock

from django.db import OperationalError, transaction
from django.http import HttpRequest, HttpResponse

from zerver.lib.exceptions import JsonableError
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.user_groups import access_user_group_by_id
from zerver.lib.validator import check_int
from zerver.models import UserGroup, UserProfile
from zerver.views.user_groups import update_subgroups_of_user_group

BARRIER: Optional[threading.Barrier] = None


def set_sync_after_recursive_query(barrier: Optional[threading.Barrier]) -> None:
    global BARRIER
    BARRIER = barrier


@has_request_variables
def dev_update_subgroups(
    request: HttpRequest,
    user_profile: UserProfile,
    user_group_id: int = REQ(json_validator=check_int, path_only=True),
) -> HttpResponse:
    # The test is expected to set up the barrier before accessing this endpoint.
    assert BARRIER is not None
    try:
        with transaction.atomic(), mock.patch(
            "zerver.lib.user_groups.access_user_group_by_id"
        ) as m:

            def wait_after_recursive_query(*args: Any, **kwargs: Any) -> UserGroup:
                # When updating the subgroups, we access the supergroup group
                # only after finishing the recursive query.
                BARRIER.wait()
                return access_user_group_by_id(*args, **kwargs)

            m.side_effect = wait_after_recursive_query

            update_subgroups_of_user_group(request, user_profile, user_group_id=user_group_id)
    except OperationalError as err:
        msg = str(err)
        if "deadlock detected" in msg:
            raise JsonableError("Deadlock detected")
        else:
            assert "could not obtain lock" in msg
            # This error is possible when nowait is set the True, which only
            # applies to the recursive query on the subgroups. Because the
            # recursive query fails, this thread must have not waited on the
            # barrier yet.
            BARRIER.wait()
            raise JsonableError("Busy lock detected")
    except (
        threading.BrokenBarrierError
    ):  # nocoverage # This is only possible when timeout happens or there is a programming error
        raise JsonableError(
            "Broken barrier. The tester should make sure that the exact number of parties have waited on the barrier set by the previous immediate set_sync_after_first_lock call"
        )

    return json_success(request)
