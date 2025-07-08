from typing_extensions import override

from zerver.lib.test_classes import WebhookTestCase
from zerver.lib.webhooks.common import parse_multipart_string


class JotformHookTests(WebhookTestCase):
    CHANNEL_NAME = "test"
    URL_TEMPLATE = "/api/v1/external/jotform?stream={stream}&api_key={api_key}"
    WEBHOOK_DIR_NAME = "jotform"

    def test_response(self) -> None:
        expected_title = "Tutor Appointment Form"
        expected_message = """
* **Student's Name**: Niloth P
* **Type of Tutoring**: Online Tutoring
* **Subject for Tutoring**: Math
* **Grade**: 12
* **Prior Tutoring?** No

* **Identity Proof**: [Student_ID_!_$&'()_,-.;=@[]^_`{}~ .png](https://www.jotform.com/uploads/UserNiloth/243231271343446/6111139644845227683/Student_ID_%21_%24%26%27%28%29_%2C-.%3B%3D%40%5B%5D%5E_%60%7B%7D~%20.png), [Driving.license.png](https://www.jotform.com/uploads/UserNiloth/243231271343446/6111139644845227684/Driving.license.png)

* **Reports**: [Report Card.pdf](https://www.jotform.com/uploads/UserNiloth/243231271343446/6111139644845227685/Report%20Card.pdf)""".strip()

        self.check_webhook(
            "response",
            expected_title,
            expected_message,
            content_type="multipart/form-data",
        )

    def test_screenshot_response(self) -> None:
        expected_title = "Feedback Form"
        expected_message = """
* **How often do you use the application?** Daily
* **How likely are you to recommend it to a friend on a scale of 0-10?** 9
* **Feedback**: The new personalized recommendations feature is great!

* **Upload images of your customized setup to get featured!**: [frontend setup.jpg](https://www.jotform.com/uploads/kolanuvarun739/243615086540051/6114090137116205381/frontend%20setup.jpg), [workflow.png](https://www.jotform.com/uploads/kolanuvarun739/243615086540051/6114090137116205381/workflow.png)""".strip()

        self.check_webhook(
            "screenshot_response",
            expected_title,
            expected_message,
            content_type="multipart/form-data",
        )

    def test_response_with_colon_comma_characters(self) -> None:
        expected_title = "Sample testing"
        expected_message = """
* **Key1 with colon: and comma, end**: Value1 with colon: and comma, end
* **Same Key**: Value 1
* **Same Key**: Value 2
* **Same Key-Value**: Same Key-Value
* **Value 2**: Value 3
* **Multiple Choice Question, options:**: Option; 1 Option2

* **File Upload with colon : and comma , end**: [error; frontend, UI.png](https://www.jotform.com/uploads/kolanuvarun739/243490908500051/6197916587414311452/error%3B%20frontend%2C%20UI.png), [Screenshot_20250331_201054.png](https://www.jotform.com/uploads/kolanuvarun739/243490908500051/6197916587414311452/Screenshot_20250331_201054.png)""".strip()

        self.check_webhook(
            "response_with_colon_comma_characters",
            expected_title,
            expected_message,
            content_type="multipart/form-data",
        )

    def test_bad_payload(self) -> None:
        with self.assertRaisesRegex(AssertionError, "Unable to handle Jotform payload"):
            self.check_webhook("response")

    @override
    def get_payload(self, fixture_name: str) -> dict[str, str]:
        body = self.webhook_fixture_data("jotform", fixture_name, file_type="multipart")
        return parse_multipart_string(body)
