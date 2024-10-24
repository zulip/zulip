from zerver.lib.test_classes import WebhookTestCase


class NewRelicHookTests(WebhookTestCase):
    CHANNEL_NAME = "newrelic"
    URL_TEMPLATE = "/api/v1/external/newrelic?stream={stream}&api_key={api_key}"
    WEBHOOK_DIR_NAME = "newrelic"

    def test_incident_activated_new_default_payload(self) -> None:
        expected_topic_name = "zulip_app query result is > 1.0 for 1 minutes on 'Zulip S..."
        expected_message = """
```spoiler :red_circle: CRITICAL **priority [issue](https://radar-api.service.newrelic.com/accounts/4420147/issues/c5faa7e6-7b54-402d-af79-f99601e0278c?notifier=WEBHOOK) has been **UPDATED** at** **<time: 2024-04-22 07:08:28.699000+00:00 >**

**[zulip_app query result is > 1.0 for 1 minutes on 'Zulip Server Low Storage'](https://radar-api.service.newrelic.com/accounts/4420147/issues/c5faa7e6-7b54-402d-af79-f99601e0278c?notifier=WEBHOOK)**

|:file: **Incident details**|
|:--------|
|:checkbox: Alert policy: **`Golden Signals`**|
|:spiral_notepad: Conditions: **`Zulip Server Low Storage`**|
|:warning: Total incidents: **1**|
|:clock: Incident created at: <time: 2024-04-22 03:05:31.352000+00:00 >|

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
```spoiler :orange_circle: HIGH **priority [issue](https://radar-api.service.newrelic.com/accounts/4420147/issues/13bbcdca-f0b6-470d-b0be-b34583c58869?notifier=WEBHOOK) has been **UPDATED** at** **<time: 2024-04-22 07:12:29.494000+00:00 >**

**[PIETER-UBUNTU query result is > 1.0 for 5 minutes on 'Storage on Host Exceeded Threshold'](https://radar-api.service.newrelic.com/accounts/4420147/issues/13bbcdca-f0b6-470d-b0be-b34583c58869?notifier=WEBHOOK)**

|:file: **Incident details**|
|:--------|
|:checkbox: Alert policy: **`Golden Signals`**|
|:spiral_notepad: Conditions: **`Storage on Host Exceeded Threshold`**|
|:warning: Total incidents: **1**|
|:clock: Incident created at: <time: 2024-04-22 07:12:29.493000+00:00 >|
|:silhouette: Acknowledged by **N/A**|
|Your custom payload: **somedata123**|

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
```spoiler :red_circle: CRITICAL **priority [issue](https://radar-api.service.newrelic.com/accounts/1/issues/0ea2df1c-adab-45d2-aae0-042b609d2322?notifier=SLACK) has been **UPDATED** at** **<time: 2024-04-22 06:17:37.383000+00:00 >**

**[main_app-UBUNTU query result is > 2.0 for 1 minutes on 'High CPU'](https://radar-api.service.newrelic.com/accounts/1/issues/0ea2df1c-adab-45d2-aae0-042b609d2322?notifier=SLACK)**

|:file: **Incident details**|
|:--------|
|:checkbox: Alert policy: **`Golden Signals`**|
|:spiral_notepad: Conditions: **`High CPU`**|
|:warning: Total incidents: **1**|
|:clock: Incident created at: <time: 2024-04-22 06:16:30.228000+00:00 >|

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
```spoiler :orange_circle: HIGH **priority [issue](https://radar-api.service.newrelic.com/accounts/4420147/issues/13bbcdca-f0b6-470d-b0be-b34583c58869?notifier=WEBHOOK) has been **CLOSED** at** **<time: 2024-04-22 07:15:35.419000+00:00 >**

**[PIETER-UBUNTU query result is > 1.0 for 5 minutes on 'Storage on Host Exceeded Threshold'](https://radar-api.service.newrelic.com/accounts/4420147/issues/13bbcdca-f0b6-470d-b0be-b34583c58869?notifier=WEBHOOK)**

|:file: **Incident details**|
|:--------|
|:checkbox: Alert policy: **`Golden Signals`**|
|:spiral_notepad: Conditions: **`Storage on Host Exceeded Threshold`**|
|:warning: Total incidents: **1**|
|:clock: Incident created at: <time: 2024-04-22 07:12:29.493000+00:00 >|
|:silhouette: Acknowledged by **Pieter Cardillo Kwok**|
|Your custom payload: **somedata123**|

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
```spoiler :orange_circle: HIGH **priority [issue](https://radar-api.service.newrelic.com/accounts/4420147/issues/13bbcdca-f0b6-470d-b0be-b34583c58869?notifier=WEBHOOK) has been **UPDATED** at** **<time: 2024-04-22 07:14:37.412000+00:00 >**

**[PIETER-UBUNTU query result is > 1.0 for 5 minutes on 'Storage on Host Exceeded Threshold'](https://radar-api.service.newrelic.com/accounts/4420147/issues/13bbcdca-f0b6-470d-b0be-b34583c58869?notifier=WEBHOOK)**

|:file: **Incident details**|
|:--------|
|:checkbox: Alert policy: **`Golden Signals`**|
|:spiral_notepad: Conditions: **`Storage on Host Exceeded Threshold`**|
|:warning: Total incidents: **1**|
|:clock: Incident created at: <time: 2024-04-22 07:12:29.493000+00:00 >|

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
```spoiler :orange_circle: HIGH **priority [issue](https://radar-api.service.newrelic.com/accounts/4420147/issues/13bbcdca-f0b6-470d-b0be-b34583c58869?notifier=WEBHOOK) has been **ACKNOWLEDGED** at** **<time: 2024-04-22 07:14:37.412000+00:00 >**

**[PIETER-UBUNTU query result is > 1.0 for 5 minutes on 'Storage on Host Exceeded Threshold'](https://radar-api.service.newrelic.com/accounts/4420147/issues/13bbcdca-f0b6-470d-b0be-b34583c58869?notifier=WEBHOOK)**

|:file: **Incident details**|
|:--------|
|:checkbox: Alert policy: **`Golden Signals`**|
|:spiral_notepad: Conditions: **`Storage on Host Exceeded Threshold`**|
|:warning: Total incidents: **1**|
|:clock: Incident created at: <time: 2024-04-22 07:12:29.493000+00:00 >|
|:silhouette: Acknowledged by **Pieter Cardillo Kwok**|

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
```spoiler :red_circle: CRITICAL **priority [issue](https://radar-api.service.newrelic.com/accounts/1/issues/0ea2df1c-adab-45d2-aae0-042b609d2322?notifier=SLACK) has been **ACTIVATED** at** **<time: 2024-04-22 06:36:29.495000+00:00 >**

**[MAIN-APP-UBUNTU query result is > 2.0 for 1 minutes on 'High CPU'](https://radar-api.service.newrelic.com/accounts/1/issues/0ea2df1c-adab-45d2-aae0-042b609d2322?notifier=SLACK)**

|:file: **Incident details**|
|:--------|
|:checkbox: Alert policy: **`Golden Signals`**|
|:spiral_notepad: Conditions: **`High CPU`**|
|:warning: Total incidents: **1**|
|:clock: Incident created at: <time: 2024-04-22 06:36:29.495000+00:00 >|

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
```spoiler :red_circle: CRITICAL **priority [issue](https://radar-api.service.newrelic.com/accounts/1/issues/0ea2df1c-adab-45d2-aae0-042b609d2322?notifier=SLACK) has been **ACTIVATED** at** **<time: 2024-04-22 06:36:29.495000+00:00 >**

**[PIETER-UBUNTU query result is > 2.0 for 1 minutes on 'High CPU'](https://radar-api.service.newrelic.com/accounts/1/issues/0ea2df1c-adab-45d2-aae0-042b609d2322?notifier=SLACK)**

|:file: **Incident details**|
|:--------|
|:checkbox: Alert policy: **`Golden Signals`**|
|:spiral_notepad: Conditions: **`High CPU`**|
|:warning: Total incidents: **1**|
|:clock: Incident created at: <time: 2024-04-22 06:36:29.495000+00:00 >|
|:silhouette: Acknowledged by **John Doe**|

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
```spoiler :orange_circle: HIGH **priority [issue](https://radar-api.service.newrelic.com/accounts/4420147/issues/13bbcdca-f0b6-470d-b0be-b34583c58869?notifier=WEBHOOK) has been **UPDATED** at** **<time: 2024-04-22 07:12:29.494000+00:00 >**

**[PIETER-UBUNTU query result is > 1.0 for 5 minutes on 'Storage on Host Exceeded Threshold'](https://radar-api.service.newrelic.com/accounts/4420147/issues/13bbcdca-f0b6-470d-b0be-b34583c58869?notifier=WEBHOOK)**

|:file: **Incident details**|
|:--------|
|:checkbox: Alert policy: **`Golden Signals`**|
|:spiral_notepad: Conditions: **`Storage on Host Exceeded Threshold`**|
|:warning: Total incidents: **1**|
|:clock: Incident created at: <time: 2024-04-22 07:12:29.493000+00:00 >|
|:silhouette: Acknowledged by **N/A**|
|Your custom payload: **somedata123**|
|Custom status 1: **True**|
|Custom list 1: **`SSD`**, **`2000`**, **`False`**, **`None`**, **`13.33`**|
|Custom field 1: **None**|
|Custom field 2: **9000**|

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
```spoiler :red_circle: CRITICAL **priority [issue](https://radar-api.service.newrelic.com/accounts/1/issues/0ea2df1c-adab-45d2-aae0-042b609d2322?notifier=SLACK) has been **CLOSED** at** **<time: 2024-04-22 06:17:37.383000+00:00 >**

**[main_app-UBUNTU query result is > 2.0 for 1 minutes on 'High CPU'](https://radar-api.service.newrelic.com/accounts/1/issues/0ea2df1c-adab-45d2-aae0-042b609d2322?notifier=SLACK)**

|:file: **Incident details**|
|:--------|
|:checkbox: Alert policy: **`Golden Signals`**|
|:spiral_notepad: Conditions: **`High CPU`**|
|:warning: Total incidents: **1**|
|:clock: Incident created at: <time: 2024-04-22 06:16:30.228000+00:00 >|
|Your custom payload: **somedata123**|
|Custom status 1: **True**|
|Custom list 1: **`SSD`**, **`2000`**, **`False`**, **`None`**, **`13.33`**|
|Custom field 1: **None**|
|Custom field 2: **9000**|

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
```spoiler :orange_circle: HIGH **priority [issue](https://radar-api.service.newrelic.com/accounts/4420147/issues/13bbcdca-f0b6-470d-b0be-b34583c58869?notifier=WEBHOOK) has been **UPDATED** at** **<time: 2024-04-22 07:12:29.494000+00:00 >**

**[PIETER-UBUNTU query result is > 1.0 for 5 minutes on 'Storage on Host Exceeded Threshold'](https://radar-api.service.newrelic.com/accounts/4420147/issues/13bbcdca-f0b6-470d-b0be-b34583c58869?notifier=WEBHOOK)**

|:file: **Incident details**|
|:--------|
|:checkbox: Alert policy: **`Golden Signals`**|
|:spiral_notepad: Conditions: **`Storage on Host Exceeded Threshold`**|
|:warning: Total incidents: **1**|
|:clock: Incident created at: <time: 2024-04-22 07:12:29.493000+00:00 >|
|:silhouette: Acknowledged by **N/A**|
|The value of **Invalid fields 1** is not a supported data type.|
|The value of **Invalid field 2** is not a supported data type.|
|Is valid: **True**|

```
        """.strip()

        self.check_webhook(
            "incident_with_invalid_zulip_custom_fields",
            expected_topic_name,
            expected_message,
            content_type="application/json",
        )

    def test_missing_essential_fields_default_payload(self) -> None:
        expected_topic_name = "Incident alerts"
        expected_message = """
```spoiler :danger: An [incident](https://one.newrelic.com/alerts-ai) updated
**Warning**: Unable to use the default notification format because at least one expected field was missing from the incident payload. See [New Relic integration documentation](/integrations/doc/newrelic).

**Missing fields**: `issueUrl`, `title`, `priority`, `totalIncidents`, `state`, `createdAt`, `updatedAt`, `alertPolicyNames`, `alertConditionNames`
```
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

    def test_incident_empty_timestamp_payload(self) -> None:
        expected_message = """```spoiler :red_circle: CRITICAL **priority [issue](https://radar-api.service.newrelic.com/accounts/4420147/issues/c5faa7e6-7b54-402d-af79-f99601e0278c?notifier=WEBHOOK) has been **UPDATED** at** **N/A**

**[zulip_app query result is > 1.0 for 1 minutes on Zulip Server Low Storage](https://radar-api.service.newrelic.com/accounts/4420147/issues/c5faa7e6-7b54-402d-af79-f99601e0278c?notifier=WEBHOOK)**

|:file: **Incident details**|
|:--------|
|:checkbox: Alert policy: **`Golden Signals`**|
|:spiral_notepad: Conditions: **`Zulip Server Low Storage`**|
|:warning: Total incidents: **1**|
|:clock: Incident created at: N/A|

```"""
        self.check_webhook(
            "incident_empty_timestamp_payload",
            "zulip_app query result is > 1.0 for 1 minutes on Zulip Se...",
            expected_message,
            content_type="application/json",
        )
