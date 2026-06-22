import orjson

from zerver.lib.test_classes import WebhookTestCase
from zerver.lib.validator import wrap_wild_value
from zerver.webhooks.gong.view import duration_pretty, get_participants, get_topics, get_trackers


class GongHookTests(WebhookTestCase):
    MESSAGE_INTRO = "**[{title}](http://local.gong-it.net:8080/call?id=5599332235511222771)** started at <time:2019-10-18T14:03:37-07:00> and lasted for 36 mins."
    PARTICIPANTS_SECTION = (
        "**Participants**:\n"
        "* Deshon White: Sales Enablement Manager - Sales Development (deshon.white@acme.com)\n"
        "* Jennifer Band: Customer Success Manager (jennifer.band@fasttrail.com)"
    )
    TRACKERS_SECTION = (
        "**Top Trackers (by count)**:\n"
        "* Renewal (positive) (7)\n"
        "* CRM (3): Salesforce (3)\n"
        "* Products (1)"
    )
    TOPICS_SECTION = (
        "**Topics**: Integrations (9 mins), Differentiation (3 mins), Customer Success."
    )
    EXPECTED_CALL_MESSAGE = (
        f"{MESSAGE_INTRO}\n\n{PARTICIPANTS_SECTION}\n\n{TRACKERS_SECTION}\n\n{TOPICS_SECTION}"
    )

    def test_gong_normal_call_payload(self) -> None:
        self.check_webhook(
            "call_completed",
            "Gong Call: Ron/Speedman",
            self.EXPECTED_CALL_MESSAGE.format(title="Ron/Speedman"),
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
            content=f"Gong webhook has been successfully configured.\n\n{self.EXPECTED_CALL_MESSAGE.format(title='Ron/Speedman')}",
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
            topic_name="Untitled call 235511222779",
            content=self.EXPECTED_CALL_MESSAGE.format(title="Untitled call"),
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
        intro = self.MESSAGE_INTRO.format(title="Ron/Speedman")
        self.assert_channel_message(
            message=msg,
            channel_name=self.channel_name,
            topic_name="Gong Call: Ron/Speedman",
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
        intro = self.MESSAGE_INTRO.format(title="Ron/Speedman")
        self.assert_channel_message(
            message=msg,
            channel_name=self.channel_name,
            topic_name="Gong Call: Ron/Speedman",
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
        intro = self.MESSAGE_INTRO.format(title="Ron/Speedman")
        self.assert_channel_message(
            message=msg,
            channel_name=self.channel_name,
            topic_name="Gong Call: Ron/Speedman",
            content=f"{intro}\n\n{self.PARTICIPANTS_SECTION}\n\n{self.TRACKERS_SECTION}",
        )

    def test_call_with_top_trackers_disabled(self) -> None:
        self.url = self.build_webhook_url(include_trackers="false")
        intro = self.MESSAGE_INTRO.format(title="Ron/Speedman")
        self.check_webhook(
            "call_completed",
            "Gong Call: Ron/Speedman",
            f"{intro}\n\n{self.PARTICIPANTS_SECTION}\n\n{self.TOPICS_SECTION}",
            content_type="application/json",
        )

    def test_call_with_top_topics_disabled(self) -> None:
        self.url = self.build_webhook_url(include_topics="false")
        intro = self.MESSAGE_INTRO.format(title="Ron/Speedman")
        self.check_webhook(
            "call_completed",
            "Gong Call: Ron/Speedman",
            f"{intro}\n\n{self.PARTICIPANTS_SECTION}\n\n{self.TRACKERS_SECTION}",
            content_type="application/json",
        )

    def test_call_with_participants_disabled(self) -> None:
        self.url = self.build_webhook_url(include_participants="false")
        intro = self.MESSAGE_INTRO.format(title="Ron/Speedman")
        self.check_webhook(
            "call_completed",
            "Gong Call: Ron/Speedman",
            f"{intro}\n\n{self.TRACKERS_SECTION}\n\n{self.TOPICS_SECTION}",
            content_type="application/json",
        )

    def test_call_with_participant_contacts_disabled(self) -> None:
        self.url = self.build_webhook_url(include_participant_contacts="false")
        intro = self.MESSAGE_INTRO.format(title="Ron/Speedman")
        participants = (
            "**Participants**:\n"
            "* Deshon White: Sales Enablement Manager - Sales Development\n"
            "* Jennifer Band: Customer Success Manager"
        )
        self.check_webhook(
            "call_completed",
            "Gong Call: Ron/Speedman",
            f"{intro}\n\n{participants}\n\n{self.TRACKERS_SECTION}\n\n{self.TOPICS_SECTION}",
            content_type="application/json",
        )

    def test_call_with_participants_off_but_contacts_on(self) -> None:
        self.url = self.build_webhook_url(
            include_participants="false", include_participant_contacts="true"
        )
        intro = self.MESSAGE_INTRO.format(title="Ron/Speedman")
        self.check_webhook(
            "call_completed",
            "Gong Call: Ron/Speedman",
            f"{intro}\n\n{self.TRACKERS_SECTION}\n\n{self.TOPICS_SECTION}",
            content_type="application/json",
        )

    def test_get_participants(self) -> None:
        name = "Jennifer Band"
        title = "Customer Success Manager"
        email = "jennifer.band@fasttrail.com"
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
            ([{"affiliation": "External"}], "1 unidentified participant"),
            (
                [{"affiliation": "External"}] * 3,
                "3 unidentified participants",
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
                "* Alice\n* Bob\n* and 2 unidentified participants",
            ),
            (
                [{"name": f"Person {i}"} for i in range(6)] + [{"affiliation": "External"}] * 2,
                "* Person 0\n* Person 1\n* Person 2\n* Person 3\n* Person 4\n* and 1 more, 2 unidentified participants",
            ),
            (
                [{"name": f"Person {i}"} for i in range(6)] + [{"affiliation": "External"}],
                "* Person 0\n* Person 1\n* Person 2\n* Person 3\n* Person 4\n* and 1 more, 1 unidentified participants",
            ),
            (
                [{"name": "Alice"}, {"affiliation": "External"}],
                "* Alice\n* and 1 unidentified participant",
            ),
            ([], ""),
        ]

        for parties, expected_output in test_cases:
            with self.subTest(parties=parties):
                payload = wrap_wild_value("parties", parties)
                self.assertEqual(get_participants(payload, True), expected_output)

        no_contacts_cases = [
            ([{"name": name, "title": title, "emailAddress": email}], f"* {name}: {title}"),
            ([{"name": name, "emailAddress": email, "phoneNumber": phone}], f"* {name}"),
            ([{"emailAddress": email}], "1 unidentified participant"),
            (
                [{"name": "Alice"}, {"emailAddress": email}, {"phoneNumber": phone}],
                "* Alice\n* and 2 unidentified participants",
            ),
            ([{"title": title, "emailAddress": email}], "1 unidentified participant"),
        ]
        for parties, expected_output in no_contacts_cases:
            with self.subTest(parties=parties, include_participant_contacts=False):
                payload = wrap_wild_value("parties", parties)
                self.assertEqual(
                    get_participants(payload, False),
                    expected_output,
                )

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
        payload = wrap_wild_value(
            "topics",
            [
                {"name": "Small talk", "duration": 0},
                {"name": "Pricing", "duration": 180},
                {"name": "Next steps", "duration": 45},
                {"name": "Revenue", "duration": 0},
            ],
        )
        self.assertEqual(get_topics(payload), "Pricing (3 mins), Next steps (45 secs), Small talk.")

        self.assertEqual(get_topics(wrap_wild_value("topics", [])), "")

    def test_duration_pretty(self) -> None:
        test_cases = [
            (0, "0 secs"),
            (1, "1 sec"),
            (45, "45 secs"),
            (59, "59 secs"),
            (60, "1 min"),
            (3599, "1 hr"),
            (3600, "1 hr"),
            (3645, "1 hr 1 min"),
            (3661, "1 hr 1 min"),
            (7200, "2 hrs"),
            (7320, "2 hrs 2 mins"),
        ]

        for duration, expected_output in test_cases:
            with self.subTest(duration=duration):
                self.assertEqual(duration_pretty(duration), expected_output)
