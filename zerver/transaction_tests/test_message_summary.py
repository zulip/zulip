import threading
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

import orjson
from django.db import connections
from django.db.models import QuerySet
from openai.resources.chat.completions import Completions
from openai.types.chat import ChatCompletion

from analytics.lib.counts import COUNT_STATS
from analytics.models import UserCount
from zerver.actions.message_summary import get_topic_summary_completion
from zerver.lib.exceptions import JsonableError
from zerver.lib.test_classes import ZulipTransactionTestCase
from zerver.models import UserProfile


class MessageSummaryRaceConditionTestCase(ZulipTransactionTestCase):
    def test_concurrent_requests_recheck_committed_usage(self) -> None:
        user = self.example_user("iago")
        usage = UserCount.objects.filter(user=user, property="ai_credit_usage::day")
        self.assertFalse(usage.exists())

        try:
            with open("zerver/tests/fixtures/llm/summary.json", "rb") as f:
                fake_response = ChatCompletion.model_validate(orjson.loads(f.read())["response"])
            assert fake_response.usage is not None
            credits_used = fake_response.usage.total_tokens
            provider_started = threading.Event()
            release_provider = threading.Event()
            second_lock_attempted = threading.Event()

            def complete_request() -> ChatCompletion:
                provider_started.set()
                self.assertTrue(release_provider.wait(timeout=10))
                return fake_response

            original_get = QuerySet.get

            def get_user(queryset: QuerySet[UserProfile], *, id: int) -> UserProfile:
                second_lock_attempted.set()
                return original_get(queryset, id=id)

            def request_completion(*, second_request: bool = False) -> str:
                try:
                    if second_request:
                        with mock.patch.object(QuerySet, "get", get_user):
                            get_topic_summary_completion(user, "test-model", [])
                    else:
                        get_topic_summary_completion(user, "test-model", [])
                except JsonableError as error:
                    return error.msg
                finally:
                    connections.close_all()
                return "success"

            with (
                self.settings(
                    MAX_PER_USER_MONTHLY_AI_COST=credits_used / 1_000_000_000,
                    TOPIC_SUMMARIZATION_API_KEY="test",
                    INPUT_COST_PER_GIGATOKEN=1,
                    OUTPUT_COST_PER_GIGATOKEN=1,
                ),
                mock.patch.object(Completions, "create", side_effect=complete_request) as create,
                ThreadPoolExecutor(max_workers=2) as pool,
            ):
                first = pool.submit(request_completion)
                try:
                    self.assertTrue(provider_started.wait(timeout=10))
                    second = pool.submit(request_completion, second_request=True)
                    self.assertTrue(second_lock_attempted.wait(timeout=10))
                finally:
                    release_provider.set()
                self.assertEqual(first.result(timeout=10), "success")
                self.assertEqual(second.result(timeout=10), "Reached monthly limit for AI credits.")
                create.assert_called_once()

            self.assertEqual(
                COUNT_STATS["ai_credit_usage::day"].current_month_accumulated_count_for_user(user),
                credits_used,
            )
        finally:
            usage.delete()
