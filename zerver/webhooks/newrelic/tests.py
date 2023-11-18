from zerver.lib.test_classes import WebhookTestCase


class NewRelicHookTests(WebhookTestCase):
    CHANNEL_NAME = "newrelic"
    URL_TEMPLATE = "/api/v1/external/newrelic?stream={stream}&api_key={api_key}"
    WEBHOOK_DIR_NAME = "newrelic"

    def test_incident_activated_new_default_payload(self) -> None:
        expected_topic_name = "zulip_app query result is > 1.0 for 1 minutes on 'Zulip S..."
        expected_message = """
:red_circle: **[zulip_app query result is > 1.0 for 1 minutes on 'Zulip Server Low Storage'](https://radar-api.service.newrelic.com/accounts/4420147/issues/c5faa7e6-7b54-402d-af79-f99601e0278c?notifier=WEBHOOK)**

```quote
**Priority**: CRITICAL
**State**: ACTIVATED
**Updated at**: <time: 2024-04-22 07:08:28.699000+00:00 >

```

```spoiler :file: Incident details

- **Alert policies**: `Golden Signals`
- **Conditions**: `Zulip Server Low Storage`
- **Total incidents**: 1
- **Incident created at**: <time: 2024-04-22 03:05:31.352000+00:00 >

```
""".strip()

        self.check_webhook(
            "incident_activated_new_default_payload",
            expected_topic_name,
            expected_message,
            content_type="application/json",
        )

    def test_incident_activated_new_provided_base_payload(self) -> None:
        expected_topic_name = "PIETER-UBUNTU query result is > 1.0 for 5 minutes on 'Sto..."
        expected_message = """
:orange_circle: **[PIETER-UBUNTU query result is > 1.0 for 5 minutes on 'Storage on Host Exceeded Threshold'](https://radar-api.service.newrelic.com/accounts/4420147/issues/13bbcdca-f0b6-470d-b0be-b34583c58869?notifier=WEBHOOK)**

```quote
**Priority**: HIGH
**State**: ACTIVATED
**Updated at**: <time: 2024-04-22 07:12:29.494000+00:00 >

```

```spoiler :file: Incident details

- **Alert policies**: `Golden Signals`
- **Conditions**: `Storage on Host Exceeded Threshold`
- **Total incidents**: 1
- **Incident created at**: <time: 2024-04-22 07:12:29.493000+00:00 >
- **Your custom payload**: somedata123

```
""".strip()

        self.check_webhook(
            "incident_activated_new_provided_base_payload",
            expected_topic_name,
            expected_message,
            content_type="application/json",
        )

    def test_incident_closed_default_payload(self) -> None:
        expected_topic_name = "main_app-UBUNTU query result is > 2.0 for 1 minutes on 'H..."
        expected_message = """
:red_circle: **[main_app-UBUNTU query result is > 2.0 for 1 minutes on 'High CPU'](https://radar-api.service.newrelic.com/accounts/1/issues/0ea2df1c-adab-45d2-aae0-042b609d2322?notifier=SLACK)**

```quote
**Priority**: CRITICAL
**State**: CLOSED
**Updated at**: <time: 2024-04-22 06:17:37.383000+00:00 >

```

```spoiler :file: Incident details

- **Alert policies**: `Golden Signals`
- **Conditions**: `High CPU`
- **Total incidents**: 1
- **Incident created at**: <time: 2024-04-22 06:16:30.228000+00:00 >

```
""".strip()

        self.check_webhook(
            "incident_closed_default_payload",
            expected_topic_name,
            expected_message,
            content_type="application/json",
        )

    def test_incident_closed_provided_base_payload(self) -> None:
        expected_topic_name = "PIETER-UBUNTU query result is > 1.0 for 5 minutes on 'Sto..."
        expected_message = """
:orange_circle: **[PIETER-UBUNTU query result is > 1.0 for 5 minutes on 'Storage on Host Exceeded Threshold'](https://radar-api.service.newrelic.com/accounts/4420147/issues/13bbcdca-f0b6-470d-b0be-b34583c58869?notifier=WEBHOOK)**

```quote
**Priority**: HIGH
**State**: CLOSED
**Updated at**: <time: 2024-04-22 07:15:35.419000+00:00 >
**Acknowledged by**: Pieter Cardillo Kwok
```

```spoiler :file: Incident details

- **Alert policies**: `Golden Signals`
- **Conditions**: `Storage on Host Exceeded Threshold`
- **Total incidents**: 1
- **Incident created at**: <time: 2024-04-22 07:12:29.493000+00:00 >
- **Your custom payload**: somedata123

```
""".strip()

        self.check_webhook(
            "incident_closed_provided_base_payload",
            expected_topic_name,
            expected_message,
            content_type="application/json",
        )

    def test_incident_acknowledged_default_payload(self) -> None:
        expected_topic_name = "PIETER-UBUNTU query result is > 1.0 for 5 minutes on 'Sto..."
        expected_message = """
:orange_circle: **[PIETER-UBUNTU query result is > 1.0 for 5 minutes on 'Storage on Host Exceeded Threshold'](https://radar-api.service.newrelic.com/accounts/4420147/issues/13bbcdca-f0b6-470d-b0be-b34583c58869?notifier=WEBHOOK)**

```quote
**Priority**: HIGH
**State**: ACTIVATED
**Updated at**: <time: 2024-04-22 07:14:37.412000+00:00 >

```

```spoiler :file: Incident details

- **Alert policies**: `Golden Signals`
- **Conditions**: `Storage on Host Exceeded Threshold`
- **Total incidents**: 1
- **Incident created at**: <time: 2024-04-22 07:12:29.493000+00:00 >

```
""".strip()

        self.check_webhook(
            "incident_acknowledged_default_payload",
            expected_topic_name,
            expected_message,
            content_type="application/json",
        )

    def test_incident_acknowledged_provided_base_payload(self) -> None:
        expected_topic_name = "PIETER-UBUNTU query result is > 1.0 for 5 minutes on 'Sto..."
        expected_message = """
:orange_circle: **[PIETER-UBUNTU query result is > 1.0 for 5 minutes on 'Storage on Host Exceeded Threshold'](https://radar-api.service.newrelic.com/accounts/4420147/issues/13bbcdca-f0b6-470d-b0be-b34583c58869?notifier=WEBHOOK)**

```quote
**Priority**: HIGH
**State**: ACTIVATED
**Updated at**: <time: 2024-04-22 07:14:37.412000+00:00 >
**Acknowledged by**: Pieter Cardillo Kwok
```

```spoiler :file: Incident details

- **Alert policies**: `Golden Signals`
- **Conditions**: `Storage on Host Exceeded Threshold`
- **Total incidents**: 1
- **Incident created at**: <time: 2024-04-22 07:12:29.493000+00:00 >

```
""".strip()

        self.check_webhook(
            "incident_acknowledged_provided_base_payload",
            expected_topic_name,
            expected_message,
            content_type="application/json",
        )

    def test_incident_created_default_payload(self) -> None:
        expected_topic_name = "MAIN-APP-UBUNTU query result is > 2.0 for 1 minutes on 'H..."
        expected_message = """
:red_circle: **[MAIN-APP-UBUNTU query result is > 2.0 for 1 minutes on 'High CPU'](https://radar-api.service.newrelic.com/accounts/1/issues/0ea2df1c-adab-45d2-aae0-042b609d2322?notifier=SLACK)**

```quote
**Priority**: CRITICAL
**State**: CREATED
**Updated at**: <time: 2024-04-22 06:36:29.495000+00:00 >

```

```spoiler :file: Incident details

- **Alert policies**: `Golden Signals`
- **Conditions**: `High CPU`
- **Total incidents**: 1
- **Incident created at**: <time: 2024-04-22 06:36:29.495000+00:00 >

```
""".strip()

        self.check_webhook(
            "incident_created_default_payload",
            expected_topic_name,
            expected_message,
            content_type="application/json",
        )

    def test_incident_created_provided_base_payload(self) -> None:
        expected_topic_name = "PIETER-UBUNTU query result is > 2.0 for 1 minutes on 'Hig..."
        expected_message = """
:red_circle: **[PIETER-UBUNTU query result is > 2.0 for 1 minutes on 'High CPU'](https://radar-api.service.newrelic.com/accounts/1/issues/0ea2df1c-adab-45d2-aae0-042b609d2322?notifier=SLACK)**

```quote
**Priority**: CRITICAL
**State**: CREATED
**Updated at**: <time: 2024-04-22 06:36:29.495000+00:00 >
**Acknowledged by**: John Doe
```

```spoiler :file: Incident details

- **Alert policies**: `Golden Signals`
- **Conditions**: `High CPU`
- **Total incidents**: 1
- **Incident created at**: <time: 2024-04-22 06:36:29.495000+00:00 >

```
""".strip()

        self.check_webhook(
            "incident_created_provided_base_payload",
            expected_topic_name,
            expected_message,
            content_type="application/json",
        )

    def test_incident_default_base_with_zulip_custom_fields(self) -> None:
        expected_topic_name = "PIETER-UBUNTU query result is > 1.0 for 5 minutes on 'Sto..."
        expected_message = """
:orange_circle: **[PIETER-UBUNTU query result is > 1.0 for 5 minutes on 'Storage on Host Exceeded Threshold'](https://radar-api.service.newrelic.com/accounts/4420147/issues/13bbcdca-f0b6-470d-b0be-b34583c58869?notifier=WEBHOOK)**

```quote
**Priority**: HIGH
**State**: ACTIVATED
**Updated at**: <time: 2024-04-22 07:12:29.494000+00:00 >

```

```spoiler :file: Incident details

- **Alert policies**: `Golden Signals`
- **Conditions**: `Storage on Host Exceeded Threshold`
- **Total incidents**: 1
- **Incident created at**: <time: 2024-04-22 07:12:29.493000+00:00 >
- **Your custom payload**: somedata123
- **Custom status 1**: True
- **Custom list 1**: SSD, 2000, False, None, 13.33
- **Custom field 1**: None
- **Custom field 2**: 9000

```
""".strip()

        self.check_webhook(
            "incident_default_base_with_zulip_custom_fields",
            expected_topic_name,
            expected_message,
            content_type="application/json",
        )

    def test_incident_provided_base_with_zulip_custom_fields(self) -> None:
        expected_topic_name = "main_app-UBUNTU query result is > 2.0 for 1 minutes on 'H..."
        expected_message = """
:red_circle: **[main_app-UBUNTU query result is > 2.0 for 1 minutes on 'High CPU'](https://radar-api.service.newrelic.com/accounts/1/issues/0ea2df1c-adab-45d2-aae0-042b609d2322?notifier=SLACK)**

```quote
**Priority**: CRITICAL
**State**: CLOSED
**Updated at**: <time: 2024-04-22 06:17:37.383000+00:00 >

```

```spoiler :file: Incident details

- **Alert policies**: `Golden Signals`
- **Conditions**: `High CPU`
- **Total incidents**: 1
- **Incident created at**: <time: 2024-04-22 06:16:30.228000+00:00 >
- **Your custom payload**: somedata123
- **Custom status 1**: True
- **Custom list 1**: SSD, 2000, False, None, 13.33
- **Custom field 1**: None
- **Custom field 2**: 9000

```
""".strip()

        self.check_webhook(
            "incident_provided_base_with_zulip_custom_fields",
            expected_topic_name,
            expected_message,
            content_type="application/json",
        )

    def test_incident_with_invalid_zulip_custom_fields(self) -> None:
        expected_topic_name = "PIETER-UBUNTU query result is > 1.0 for 5 minutes on 'Sto..."
        expected_message = """
:orange_circle: **[PIETER-UBUNTU query result is > 1.0 for 5 minutes on 'Storage on Host Exceeded Threshold'](https://radar-api.service.newrelic.com/accounts/4420147/issues/13bbcdca-f0b6-470d-b0be-b34583c58869?notifier=WEBHOOK)**

```quote
**Priority**: HIGH
**State**: ACTIVATED
**Updated at**: <time: 2024-04-22 07:12:29.494000+00:00 >

```

```spoiler :file: Incident details

- **Alert policies**: `Golden Signals`
- **Conditions**: `Storage on Host Exceeded Threshold`
- **Total incidents**: 1
- **Incident created at**: <time: 2024-04-22 07:12:29.493000+00:00 >
- **Invalid fields 1**: *Value is not a supported data type*
- **Invalid field 2**: *Value is not a supported data type*
- **Is valid**: True

```
""".strip()

        self.check_webhook(
            "incident_with_invalid_zulip_custom_fields",
            expected_topic_name,
            expected_message,
            content_type="application/json",
        )

    def test_missing_essential_fields_default_payload(self) -> None:
        expected_topic_name = "New Relic incident alerts"
        expected_message = """
:danger: A New Relic [incident](https://one.newrelic.com/alerts-ai) updated

**Warning**: Unable to use the default notification format because at least one expected field was missing from the incident payload. See [New Relic integration documentation](/integrations/doc/newrelic).

**Missing fields**: `issueUrl`, `title`, `priority`, `totalIncidents`, `state`, `createdAt`, `updatedAt`, `alertPolicyNames`, `alertConditionNames`
""".strip()

        self.check_webhook(
            "missing_essential_fields_default_payload",
            expected_topic_name,
            expected_message,
            content_type="application/json",
        )

    def test_malformatted_time(self) -> None:
        with self.assertRaises(AssertionError) as e:
            self.check_webhook(
                "incident_malformed_timestamp",
                "",
                "",
                content_type="application/json",
            )
        self.assertIn("The newrelic webhook expects time in milliseconds.", e.exception.args[0])

    def test_time_too_large(self) -> None:
        with self.assertRaises(AssertionError) as e:
            self.check_webhook(
                "incident_time_too_large",
                "",
                "",
                content_type="application/json",
            )
        self.assertIn("The newrelic webhook expects time in milliseconds.", e.exception.args[0])
