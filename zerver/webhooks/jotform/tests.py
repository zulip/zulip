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

* **Report Cards**: [Report_card_11th.docx](https://www.jotform.com/uploads/kolanuvarun739/243490485676065/6103648469563941191/Report_card_11th.docx), [Report Card 12th.pdf](https://www.jotform.com/uploads/kolanuvarun739/243490485676065/6103648469563941191/Report%20Card%2012th.pdf)

* **Identity Proof**: [Student_ID.png](https://www.jotform.com/uploads/kolanuvarun739/243490485676065/6103648469563941191/Student_ID.png), [Driver License.png](https://www.jotform.com/uploads/kolanuvarun739/243490485676065/6103648469563941191/Driver%20License.png)

* **Income Proof**: [Parent Salary Slip.png](https://www.jotform.com/uploads/kolanuvarun739/243490485676065/6103648469563941191/Parent%20Salary%20Slip.png), [Income_certificate.pdf](https://www.jotform.com/uploads/kolanuvarun739/243490485676065/6103648469563941191/Income_certificate.pdf)""".strip()

        self.check_webhook(
            "response",
            expected_title,
            expected_message,
            content_type="multipart/form-data",
        )

    def test_screenshot_response(self) -> None:
        expected_title = "Tutor Appointment Form"
        expected_message = """
* **Student's Name**: Niloth P
* **Type of Tutoring**: Online Tutoring
* **Subject for Tutoring**: Math
* **Grade**: 12
* **Prior Tutoring?** No

* **Report Cards**: [Report_card_11th.docx](https://www.jotform.com/uploads/kolanuvarun739/243490485676065/6103648469563941191/Report_card_11th.docx), [Report Card 12th.pdf](https://www.jotform.com/uploads/kolanuvarun739/243490485676065/6103648469563941191/Report%20Card%2012th.pdf)

* **Identity Proof**: [Student_ID.png](https://www.jotform.com/uploads/kolanuvarun739/243490485676065/6103648469563941191/Student_ID.png), [Driver License.png](https://www.jotform.com/uploads/kolanuvarun739/243490485676065/6103648469563941191/Driver%20License.png)

* **Income Proof**: [Parent Salary Slip.png](https://www.jotform.com/uploads/kolanuvarun739/243490485676065/6103648469563941191/Parent%20Salary%20Slip.png), [Income_certificate.pdf](https://www.jotform.com/uploads/kolanuvarun739/243490485676065/6103648469563941191/Income_certificate.pdf)""".strip()

        self.check_webhook(
            "screenshot_response",
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
