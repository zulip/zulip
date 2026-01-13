from zerver.lib.test_classes import WebhookTestCase


class DropboxHookTests(WebhookTestCase):
    def test_file_updated(self) -> None:
        expected_topic_name = "Dropbox"
        expected_message = "File has been updated on Dropbox!"

        self.check_webhook(
            "file_updated",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_verification_request(self) -> None:
        self.subscribe(self.test_user, self.channel_name)
        get_params = {"stream_name": self.channel_name, "api_key": self.test_user.api_key}
        result = self.client_get(self.url, get_params)
        self.assert_json_error(result, "Missing 'challenge' argument", 400)

        get_params["challenge"] = "9B2SVL4orbt5DxLMqJHI6pOTipTqingt2YFMIO0g06E"
        result = self.client_get(self.url, get_params)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result["Content-Type"], "text/plain; charset=UTF-8")
        self.assert_in_response("9B2SVL4orbt5DxLMqJHI6pOTipTqingt2YFMIO0g06E", result)
