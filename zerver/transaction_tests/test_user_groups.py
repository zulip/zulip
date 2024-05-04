import threading
from typing import Any, List, Optional
from unittest import mock

import orjson
from django.db import OperationalError, connections, transaction
from django.http import HttpRequest
from typing_extensions import override

from zerver.actions.user_groups import add_subgroups_to_user_group, check_add_user_group
from zerver.lib.exceptions import JsonableError
from zerver.lib.test_classes import ZulipTransactionTestCase
from zerver.lib.test_helpers import HostRequestMock
from zerver.lib.user_groups import access_user_group_by_id
from zerver.models import NamedUserGroup, Realm, UserGroup, UserProfile
from zerver.models.realms import get_realm
from zerver.views.user_groups import update_subgroups_of_user_group

BARRIER: Optional[threading.Barrier] = None


def dev_update_subgroups(
    request: HttpRequest,
    user_profile: UserProfile,
    user_group_id: int,
) -> Optional[str]:
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
            return "Deadlock detected"
        else:
            assert "could not obtain lock" in msg
            # This error is possible when nowait is set the True, which only
            # applies to the recursive query on the subgroups. Because the
            # recursive query fails, this thread must have not waited on the
            # barrier yet.
            BARRIER.wait()
            return "Busy lock detected"
    except (
        threading.BrokenBarrierError
    ):  # nocoverage # This is only possible when timeout happens or there is a programming error
        raise JsonableError(
            "Broken barrier. The tester should make sure that the exact number of parties have waited on the barrier set by the previous immediate set_sync_after_first_lock call"
        )

    return None


class UserGroupRaceConditionTestCase(ZulipTransactionTestCase):
    created_user_groups: List[UserGroup] = []
    counter = 0
    CHAIN_LENGTH = 3

    @override
    def tearDown(self) -> None:
        # Clean up the user groups created to minimize leakage
        with transaction.atomic():
            for group in self.created_user_groups:
                group.delete()
            transaction.on_commit(self.created_user_groups.clear)

        super().tearDown()

    def create_user_group_chain(self, realm: Realm) -> List[NamedUserGroup]:
        """Build a user groups forming a chain through group-group memberships
        returning a list where each group is the supergroup of its subsequent group.
        """
        groups = [
            check_add_user_group(realm, f"chain #{self.counter + i}", [], acting_user=None)
            for i in range(self.CHAIN_LENGTH)
        ]
        self.counter += self.CHAIN_LENGTH
        self.created_user_groups.extend(groups)
        prev_group = groups[0]
        for group in groups[1:]:
            add_subgroups_to_user_group(prev_group, [group], acting_user=None)
            prev_group = group
        return groups

    def test_lock_subgroups_with_respect_to_supergroup(self) -> None:
        realm = get_realm("zulip")
        self.login("iago")
        iago = self.example_user("iago")

        class RacingThread(threading.Thread):
            def __init__(
                self,
                subgroup_ids: List[int],
                supergroup_id: int,
            ) -> None:
                threading.Thread.__init__(self)
                self.response: Optional[str] = None
                self.subgroup_ids = subgroup_ids
                self.supergroup_id = supergroup_id

            @override
            def run(self) -> None:
                try:
                    self.response = dev_update_subgroups(
                        HostRequestMock({"add": orjson.dumps(self.subgroup_ids).decode()}),
                        iago,
                        user_group_id=self.supergroup_id,
                    )
                finally:
                    # Close all thread-local database connections
                    connections.close_all()

        def assert_thread_success_count(
            t1: RacingThread,
            t2: RacingThread,
            *,
            success_count: int,
            error_message: str = "",
        ) -> None:
            help_msg = """We access the test endpoint that wraps around the
real subgroup update endpoint by synchronizing them after the acquisition of the
first lock in the critical region. Though unlikely, this test might fail as we
have no control over the scheduler when the barrier timeouts.
""".strip()
            global BARRIER
            BARRIER = threading.Barrier(parties=2, timeout=3)
            t1.start()
            t2.start()

            succeeded = 0
            for t in [t1, t2]:
                t.join()
                response = t.response
                if response is None:
                    succeeded += 1
                    continue

                self.assertEqual(response, error_message)
            # Race condition resolution should only allow one thread to succeed
            self.assertEqual(
                succeeded,
                success_count,
                f"Exactly {success_count} thread(s) should succeed.\n{help_msg}",
            )

        foo_chain = self.create_user_group_chain(realm)
        bar_chain = self.create_user_group_chain(realm)
        # These two threads are conflicting because a cycle would be formed if
        # both of them succeed. There is a deadlock in such circular dependency.
        assert_thread_success_count(
            RacingThread(
                subgroup_ids=[foo_chain[0].id],
                supergroup_id=bar_chain[-1].id,
            ),
            RacingThread(
                subgroup_ids=[bar_chain[-1].id],
                supergroup_id=foo_chain[0].id,
            ),
            success_count=1,
            error_message="Deadlock detected",
        )

        foo_chain = self.create_user_group_chain(realm)
        bar_chain = self.create_user_group_chain(realm)
        # These two requests would succeed if they didn't race with each other.
        # However, both threads will attempt to grab a lock on overlapping rows
        # when they first do the recursive query for subgroups. In this case, we
        # expect that one of the threads fails due to nowait=True for the
        # .select_for_update() call.
        assert_thread_success_count(
            RacingThread(
                subgroup_ids=[foo_chain[0].id],
                supergroup_id=bar_chain[-1].id,
            ),
            RacingThread(
                subgroup_ids=[foo_chain[1].id],
                supergroup_id=bar_chain[-1].id,
            ),
            success_count=1,
            error_message="Busy lock detected",
        )

        foo_chain = self.create_user_group_chain(realm)
        bar_chain = self.create_user_group_chain(realm)
        baz_chain = self.create_user_group_chain(realm)
        # Adding non-conflicting subgroups should succeed.
        assert_thread_success_count(
            RacingThread(
                subgroup_ids=[foo_chain[1].id, foo_chain[2].id, baz_chain[2].id],
                supergroup_id=baz_chain[0].id,
            ),
            RacingThread(
                subgroup_ids=[bar_chain[1].id, bar_chain[2].id],
                supergroup_id=baz_chain[0].id,
            ),
            success_count=2,
        )
