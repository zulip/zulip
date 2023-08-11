from unittest import mock

from django.utils.timezone import now as timezone_now

from zerver.lib.test_classes import ZulipTestCase
from zerver.models import Client, UserActivity, UserProfile


class ActivityTest(ZulipTestCase):
    @mock.patch("stripe.Customer.list", return_value=[])
    def test_activity(self, unused_mock: mock.Mock) -> None:
        self.login("hamlet")
        client, _ = Client.objects.get_or_create(name="website")
        query = "/json/messages/flags"
        last_visit = timezone_now()
        count = 150
        for activity_user_profile in UserProfile.objects.all():
            UserActivity.objects.get_or_create(
                user_profile=activity_user_profile,
                client=client,
                query=query,
                count=count,
                last_visit=last_visit,
            )

        # Fails when not staff
        result = self.client_get("/activity")
        self.assertEqual(result.status_code, 302)

        user_profile = self.example_user("hamlet")
        user_profile.is_staff = True
        user_profile.save(update_fields=["is_staff"])

        with self.assert_database_query_count(18):
            result = self.client_get("/activity")
            self.assertEqual(result.status_code, 200)

        with self.assert_database_query_count(8):
            result = self.client_get("/realm_activity/zulip/")
            self.assertEqual(result.status_code, 200)

        iago = self.example_user("iago")
        with self.assert_database_query_count(5):
            result = self.client_get(f"/user_activity/{iago.id}/")
            self.assertEqual(result.status_code, 200)
