import orjson

from zerver.lib.test_classes import WebhookTestCase
from zerver.lib.validator import wrap_wild_value
from zerver.webhooks.fixtureless_integrations import BO_EMAIL, BO_NAME, KEVIN_EMAIL, KEVIN_NAME
from zerver.webhooks.gong.view import (
    format_duration_to_string,
    get_participants,
    get_topics,
    get_trackers,
)


class GongHookTests(WebhookTestCase):
    CALL_TITLE = "Sales team meeting"
    EXPECTED_TOPIC = f"Gong call: {CALL_TITLE}"
    MESSAGE_INTRO = "**[{title}](http://local.gong-it.net:8080/call?id=5599332235511222771)** started at <time:2019-10-18T14:03:37-07:00> and lasted for 36 minutes."
    PARTICIPANTS_SECTION = (
        "**Participants**:\n"
        f"* {BO_NAME}: Sales Enablement Manager - Sales Development ({BO_EMAIL})\n"
        f"* {KEVIN_NAME}: Customer Success Manager ({KEVIN_EMAIL})"
    )
    TRACKERS_SECTION = (
        "**Top Trackers (by count)**:\n"
        "* Renewal (positive) (7)\n"
        "* CRM (3): Salesforce (3)\n"
        "* Products (1)"
    )
    TOPICS_SECTION = (
        "**Topics**: Integrations (9 minutes), Differentiation (3 minutes), Customer Success."
    )
    EXPECTED_CALL_MESSAGE = (
        f"{MESSAGE_INTRO}\n\n{PARTICIPANTS_SECTION}\n\n{TRACKERS_SECTION}\n\n{TOPICS_SECTION}"
    )

    def test_gong_normal_call_payload(self) -> None:
        self.check_webhook(
            "call_completed",
            self.EXPECTED_TOPIC,
            self.EXPECTED_CALL_MESSAGE.format(title=self.CALL_TITLE),
            content_type="application/json",
        )

    def test_gong_test_call(self) -> None:
        self.subscribe(self.test_user, self.channel_name)
        payload = orjson.loads(self.get_body("call_completed"))
        payload["isTest"] = True
        msg = self.send_webhook_payload(
            self.test_user,
            self.url,
            orjson.dumps(payload).decode(),
            content_type="application/json",
        )
        self.assert_channel_message(
            message=msg,
            channel_name=self.channel_name,
            topic_name="Gong Test",
            content=f"Gong webhook has been successfully configured.\n\n{self.EXPECTED_CALL_MESSAGE.format(title=self.CALL_TITLE)}",
        )

    def test_call_without_title(self) -> None:
        self.subscribe(self.test_user, self.channel_name)
        payload = orjson.loads(self.get_body("call_completed"))
        payload["callData"]["metaData"].pop("title")
        msg = self.send_webhook_payload(
            self.test_user,
            self.url,
            orjson.dumps(payload).decode(),
            content_type="application/json",
        )
        self.assert_channel_message(
            message=msg,
            channel_name=self.channel_name,
            topic_name="Gong call (ID: 5599332235511222779)",
            content=self.EXPECTED_CALL_MESSAGE.format(title="Gong call"),
        )

    def test_call_without_participants(self) -> None:
        self.subscribe(self.test_user, self.channel_name)
        payload = orjson.loads(self.get_body("call_completed"))
        payload["callData"]["parties"] = []
        msg = self.send_webhook_payload(
            self.test_user,
            self.url,
            orjson.dumps(payload).decode(),
            content_type="application/json",
        )
        intro = self.MESSAGE_INTRO.format(title=self.CALL_TITLE)
        self.assert_channel_message(
            message=msg,
            channel_name=self.channel_name,
            topic_name=self.EXPECTED_TOPIC,
            content=f"{intro}\n\n{self.TRACKERS_SECTION}\n\n{self.TOPICS_SECTION}",
        )

    def test_call_without_trackers(self) -> None:
        self.subscribe(self.test_user, self.channel_name)
        payload = orjson.loads(self.get_body("call_completed"))
        payload["callData"]["content"].pop("trackers")
        msg = self.send_webhook_payload(
            self.test_user,
            self.url,
            orjson.dumps(payload).decode(),
            content_type="application/json",
        )
        intro = self.MESSAGE_INTRO.format(title=self.CALL_TITLE)
        self.assert_channel_message(
            message=msg,
            channel_name=self.channel_name,
            topic_name=self.EXPECTED_TOPIC,
            content=f"{intro}\n\n{self.PARTICIPANTS_SECTION}\n\n{self.TOPICS_SECTION}",
        )

    def test_call_without_topics(self) -> None:
        self.subscribe(self.test_user, self.channel_name)
        payload = orjson.loads(self.get_body("call_completed"))
        payload["callData"]["content"].pop("topics")
        msg = self.send_webhook_payload(
            self.test_user,
            self.url,
            orjson.dumps(payload).decode(),
            content_type="application/json",
        )
        intro = self.MESSAGE_INTRO.format(title=self.CALL_TITLE)
        self.assert_channel_message(
            message=msg,
            channel_name=self.channel_name,
            topic_name=self.EXPECTED_TOPIC,
            content=f"{intro}\n\n{self.PARTICIPANTS_SECTION}\n\n{self.TRACKERS_SECTION}",
        )

    def test_call_with_top_trackers_disabled(self) -> None:
        self.url = self.build_webhook_url(include_trackers="false")
        intro = self.MESSAGE_INTRO.format(title=self.CALL_TITLE)
        self.check_webhook(
            "call_completed",
            self.EXPECTED_TOPIC,
            f"{intro}\n\n{self.PARTICIPANTS_SECTION}\n\n{self.TOPICS_SECTION}",
            content_type="application/json",
        )

    def test_get_participants(self) -> None:
        name = KEVIN_NAME
        title = "Customer Success Manager"
        email = KEVIN_EMAIL
        phone = "5556543210"
        test_cases = [
            ([{"name": name}], f"* {name}"),
            ([{"name": name, "title": title}], f"* {name}: {title}"),
            ([{"name": name, "emailAddress": email}], f"* {name} ({email})"),
            ([{"name": name, "phoneNumber": phone}], f"* {name} ({phone})"),
            (
                [{"name": name, "title": title, "emailAddress": email}],
                f"* {name}: {title} ({email})",
            ),
            (
                [{"name": name, "title": title, "phoneNumber": phone}],
                f"* {name}: {title} ({phone})",
            ),
            (
                [{"name": name, "emailAddress": email, "phoneNumber": phone}],
                f"* {name} ({email}, {phone})",
            ),
            (
                [{"name": name, "title": title, "emailAddress": email, "phoneNumber": phone}],
                f"* {name}: {title} ({email}, {phone})",
            ),
            ([{"emailAddress": email}], f"* {email}"),
            ([{"phoneNumber": phone}], f"* {phone}"),
            ([{"emailAddress": email, "phoneNumber": phone}], f"* {email} ({phone})"),
            (
                [{"title": title, "emailAddress": email, "phoneNumber": phone}],
                f"* {email}: {title} ({phone})",
            ),
            ([{"affiliation": "External"}], "* 1 participant"),
            (
                [{"affiliation": "External"}] * 3,
                "* 3 participants",
            ),
            (
                [{"name": f"Person {i}"} for i in range(6)],
                "* Person 0\n* Person 1\n* Person 2\n* Person 3\n* Person 4\n* and 1 more participant",
            ),
            (
                [{"name": f"Person {i}"} for i in range(7)],
                "* Person 0\n* Person 1\n* Person 2\n* Person 3\n* Person 4\n* and 2 more participants",
            ),
            (
                [{"name": "Alice"}, {"name": "Bob"}] + [{"affiliation": "External"}] * 2,
                "* Alice\n* Bob\n* and 2 more participants",
            ),
            (
                [{"name": f"Person {i}"} for i in range(6)] + [{"affiliation": "External"}] * 2,
                "* Person 0\n* Person 1\n* Person 2\n* Person 3\n* Person 4\n* and 3 more participants",
            ),
            ([], ""),
        ]

        for parties, expected_output in test_cases:
            with self.subTest(parties=parties):
                payload = wrap_wild_value("parties", parties)
                self.assertEqual(get_participants(payload), expected_output)

    def test_get_trackers(self) -> None:
        payload = wrap_wild_value(
            "trackers",
            [
                {"name": "Products", "count": 1},
                {"name": "Renewal (positive)", "count": 7},
                {"name": "ERP", "count": 0},
                {
                    "name": "Pricing",
                    "count": 5,
                    "phrases": [
                        {"count": 2, "phrase": "budget"},
                        {"count": 3, "phrase": "discount"},
                    ],
                },
                {"name": "CRM", "count": 3, "phrases": [{"count": 3, "phrase": "Salesforce"}]},
            ],
        )
        self.assertEqual(
            get_trackers(payload),
            "* Renewal (positive) (7)\n"
            "* Pricing (5): discount (3), budget (2)\n"
            "* CRM (3): Salesforce (3)",
        )

        self.assertEqual(get_trackers(wrap_wild_value("trackers", [])), "")

    def test_get_topics(self) -> None:
        topics = [
            {"name": "Small talk", "duration": 0},
            {"name": "Pricing", "duration": 180},
            {"name": "Next steps", "duration": 45},
            {"name": "Revenue", "duration": 0},
        ]
        self.assertEqual(
            get_topics(wrap_wild_value("topics", topics)),
            "Pricing (3 minutes), Next steps (45 seconds), Small talk and 1 more topic.",
        )

        topics.append({"name": "Wrap-up", "duration": 0})
        self.assertEqual(
            get_topics(wrap_wild_value("topics", topics)),
            "Pricing (3 minutes), Next steps (45 seconds), Small talk and 2 more topics.",
        )

        self.assertEqual(get_topics(wrap_wild_value("topics", [])), "")

    def test_format_duration_to_string(self) -> None:
        test_cases = [
            (0, "0 seconds"),
            (1, "1 second"),
            (45, "45 seconds"),
            (59, "59 seconds"),
            (60, "1 minute"),
            (3599, "1 hour"),
            (3600, "1 hour"),
            (3645, "1 hour 1 minute"),
            (3661, "1 hour 1 minute"),
            (7200, "2 hours"),
            (7320, "2 hours 2 minutes"),
        ]

        for duration, expected_output in test_cases:
            with self.subTest(duration=duration):
                self.assertEqual(format_duration_to_string(duration), expected_output)
