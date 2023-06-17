import threading
from typing import TYPE_CHECKING, List, Optional

import orjson
from django.db import connections, transaction

from zerver.actions.user_groups import add_subgroups_to_user_group, check_add_user_group
from zerver.lib.test_classes import ZulipTransactionTestCase
from zerver.models import Realm, UserGroup, get_realm
from zerver.views.development import user_groups as user_group_view

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse


class UserGroupRaceConditionTestCase(ZulipTransactionTestCase):
    created_user_groups: List[UserGroup] = []
    counter = 0
    CHAIN_LENGTH = 3

    def tearDown(self) -> None:
        # Clean up the user groups created to minimize leakage
        with transaction.atomic():
            for group in self.created_user_groups:
                group.delete()
            transaction.on_commit(lambda: self.created_user_groups.clear())

        super().tearDown()

    def create_user_group_chain(self, realm: Realm) -> List[UserGroup]:
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
        test_case = self

        class RacingThread(threading.Thread):
            def __init__(
                self,
                subgroup_ids: List[int],
                supergroup_id: int,
            ) -> None:
                threading.Thread.__init__(self)
                self.response: Optional["TestHttpResponse"] = None
                self.subgroup_ids = subgroup_ids
                self.supergroup_id = supergroup_id

            def run(self) -> None:
                try:
                    self.response = test_case.client_post(
                        url=f"/testing/user_groups/{self.supergroup_id}/subgroups",
                        info={"add": orjson.dumps(self.subgroup_ids).decode()},
                    )
                finally:
                    # Close all thread-local database connections
                    connections.close_all()

        def assert_thread_success_count(
            t1: RacingThread,
            t2: RacingThread,
            *,
            success_count: int,
            error_messsage: str = "",
        ) -> None:
            help_msg = """We access the test endpoint that wraps around the
real subgroup update endpoint by synchronizing them after the acquisition of the
first lock in the critical region. Though unlikely, this test might fail as we
have no control over the scheduler when the barrier timeouts.
""".strip()
            barrier = threading.Barrier(parties=2, timeout=3)

            user_group_view.set_sync_after_recursive_query(barrier)
            t1.start()
            t2.start()

            succeeded = 0
            for t in [t1, t2]:
                t.join()
                response = t.response
                if response is not None and response.status_code == 200:
                    succeeded += 1
                    continue

                assert response is not None
                self.assert_json_error(response, error_messsage)
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
            error_messsage="Deadlock detected",
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
            error_messsage="Busy lock detected",
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
