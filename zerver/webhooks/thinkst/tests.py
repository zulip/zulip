from zerver.lib.test_classes import WebhookTestCase


class ThinkstHookTests(WebhookTestCase):
    CHANNEL_NAME = "thinkst"
    URL_TEMPLATE = "/api/v1/external/thinkst?stream={stream}&api_key={api_key}"
    WEBHOOK_DIR_NAME = "thinkst"

    def test_canary_dummy(self) -> None:
        expected_message = (
            "**:alert: Canary *0000000testnode* has been triggered!**\n\n"
            "This is a dummy incident.\n\n"
            "**Incident ID:** `aa875f255f94e3ffe40dc85cf1a8b1e0`\n"
            "**Kind:** Dummy Incident\n"
            "**Timestamp:** 2020-06-09 13:59:38 (UTC)\n"
            "**Canary IP:** `1.1.1.1`\n"
            "**Source IP:** `2.2.2.2`\n"
            "**Reverse DNS:** `attacker-ip.local`\n"
            "**Field1:** VALUE1\n"
            "**Field2:** VALUE2\n"
            "**Field3:** VALUE3"
        )

        self.check_webhook(
            "canary_dummy",
            "canary alert - 0000000testnode",
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_canary_consolidated_port_scan(self) -> None:
        expected_message = (
            "**:alert: Canary *foo-bar* has been triggered!**\n\n"
            "A portscan has been done on several of your canaries by the host "
            "1.1.1.1.\n\n"
            "**Incident ID:** `3f25fec9e18c7673dcc468800b7af0a6`\n"
            "**Kind:** Consolidated Network Port Scan\n"
            "**Timestamp:** 2020-07-20 16:18:40 (UTC)\n"
            "**Canary IP:** `1.1.1.1`\n"
            "**Canary location:** dining room\n"
            "**Source IP:** `1.1.1.1`\n"
            "**Reverse DNS:** `attacker.local`\n"
            "**Incident:** Consolidated Network Port Scan\n"
            "**Source:** 1.1.1.1\n"
            "**Targets:** 1.0.0.1, 1.0.0.2\n"
            "**Background Context:** You have had 8 incidents from 1.0.0.1 previously."
        )

        self.check_webhook(
            "canary_consolidated_port_scan",
            "canary alert - foo-bar",
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_canary_file_access(self) -> None:
        expected_message = (
            "**:alert: Canary *bar-foo* has been triggered!**\n\n"
            "Shared File (Re)Opened has been detected against one of your Canaries "
            "(bar-foo) at 1.1.1.1.\n\n"
            "**Incident ID:** `a7bb317ba2072415462233cef3bc615a`\n"
            "**Kind:** Shared File (Re)Opened\n"
            "**Timestamp:** 2020-07-20 16:27:20 (UTC)\n"
            "**Canary IP:** `1.1.1.1`\n"
            "**Canary location:** dining room\n"
            "**Source IP:** `1.1.1.1`\n"
            "**User:** guest\n"
            "**Filename:** secret/bar.doc\n"
            "**Additional Information:** This file 'secret/bar.doc' was "
            "previously opened by the host 'zulip-dev' on 2020-07-20 16:18:56.\n\n"
            "It was also opened 2 times before by the same host, on 2020-06-10 "
            "14:33:50, 2020-06-18 19:02:33.\n"
            "**Background Context:** You have had 20 incidents from 1.1.1.1 previously."
        )

        self.check_webhook(
            "canary_file_access",
            "canary alert - bar-foo",
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_canary_host_port_scan(self) -> None:
        expected_message = (
            "**:alert: Canary *foo-bar* has been triggered!**\n\n"
            "Host Port Scan has been detected against one of your Canaries "
            "(foo-bar) at 1.1.1.1.\n\n"
            "**Incident ID:** `9060473d2da98afe494adad648495620`\n"
            "**Kind:** Host Port Scan\n"
            "**Timestamp:** 2020-07-20 16:26:30 (UTC)\n"
            "**Canary IP:** `1.1.1.1`\n"
            "**Canary location:** dining room\n"
            "**Source IP:** `1.1.1.1`\n"
            "**Reverse DNS:** `attacker.local`\n"
            "**Partial Ports:** 443, 554, 80, 1723, 22"
        )

        self.check_webhook(
            "canary_host_port_scan",
            "canary alert - foo-bar",
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_canary_http_login(self) -> None:
        expected_message = (
            "**:alert: Canary *foo-bar* has been triggered!**\n\n"
            "HTTP Login Attempt has been detected against one of your Canaries "
            "(foo-bar) at 1.1.1.1.\n\n"
            "**Incident ID:** `1ef86f5cf4090a5252c6f453c5cd46bd`\n"
            "**Kind:** HTTP Login Attempt\n"
            "**Timestamp:** 2020-07-20 14:55:45 (UTC)\n"
            "**Canary IP:** `1.1.1.1`\n"
            "**Canary location:** dining room\n"
            "**Source IP:** `1.1.1.1`\n"
            "**Username:** regular\n"
            "**Password:** `*******`\n"
            "**User-Agent:** Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.1.1 Safari/605.1.15\n"
            "**Background Context:** You have had 14 incidents from 1.1.1.1 previously."
        )

        self.check_webhook(
            "canary_http_login",
            "canary alert - foo-bar",
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_canary_ssh_login(self) -> None:
        expected_message = (
            "**:alert: Canary *foo-bar* has been triggered!**\n\n"
            "SSH Login Attempt has been detected against one of your Canaries "
            "(foo-bar) at 1.1.1.1.\n\n"
            "**Incident ID:** `4ef51a936d05e0a6b4846378c8c38d2c`\n"
            "**Kind:** SSH Login Attempt\n"
            "**Timestamp:** 2020-07-20 16:26:22 (UTC)\n"
            "**Canary IP:** `1.1.1.1`\n"
            "**Canary location:** dining room\n"
            "**Source IP:** `1.1.1.1`\n"
            "**Reverse DNS:** `attacker.local`\n"
            "**Username:** foo\n"
            "**Key:** `*******`\n"
            "**Background Context:** You have had 9 incidents from 1.1.1.1 previously."
        )

        self.check_webhook(
            "canary_ssh_login",
            "canary alert - foo-bar",
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_canary_with_specific_topic(self) -> None:
        self.url = self.build_webhook_url(topic="foo")
        expected_message = (
            "**:alert: Canary *0000000testnode* has been triggered!**\n\n"
            "This is a dummy incident.\n\n"
            "**Incident ID:** `aa875f255f94e3ffe40dc85cf1a8b1e0`\n"
            "**Kind:** Dummy Incident\n"
            "**Timestamp:** 2020-06-09 13:59:38 (UTC)\n"
            "**Canary IP:** `1.1.1.1`\n"
            "**Source IP:** `2.2.2.2`\n"
            "**Reverse DNS:** `attacker-ip.local`\n"
            "**Field1:** VALUE1\n"
            "**Field2:** VALUE2\n"
            "**Field3:** VALUE3"
        )

        self.check_webhook(
            "canary_dummy",
            "foo",
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_canarytoken_msword(self) -> None:
        expected_message = (
            "**:alert: Canarytoken *test document* has been triggered!**\n\n"
            "A MS Word .docx Document Canarytoken has been triggered over doc-msword "
            "by the source IP 1.1.1.1.\n\n"
            "**Incident ID:** `db6f9b5528c6c6c385cb3bb63f5949c8`\n"
            "**Token:** `dbwx4d68flwh2u5zku56nogu6`\n"
            "**Kind:** MS Word .docx Document\n"
            "**Timestamp:** 2020-07-20 14:40:15 (UTC)\n"
            "**Triggered:** 5 times\n"
            "**Accept:** `*/*`\n"
            "**Accept-Encoding:** gzip, deflate\n"
            "**Accept-Language:** en-gb\n"
            "**Background Context:** You have had 21 incidents from 1.1.1.1 "
            "previously.\n"
            "**Connection:** keep-alive\n"
            "**Dst Port:** 80\n"
            "**User-Agent:** Mozilla/4.0 (compatible; ms-office; MSOffice 16)"
        )

        self.check_webhook(
            "canarytoken_msword",
            "canarytoken alert - test document",
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_canarytoken_remote_image(self) -> None:
        expected_message = (
            "**:alert: Canarytoken *test image* has been triggered!**\n\n"
            "A Remote Web Image Canarytoken has been triggered over web-image by the "
            "source IP 1.1.1.1.\n\n"
            "**Incident ID:** `533395067f6d655cd19384bc6991cc0f`\n"
            "**Token:** `ew5n8gqtb82m4uegrttarn2zu`\n"
            "**Kind:** Remote Web Image\n"
            "**Timestamp:** 2020-07-20 16:33:12 (UTC)\n"
            "**Triggered:** 37 times\n"
            "**Accept:** `image/webp,*/*`\n"
            "**Accept-Encoding:** gzip, deflate\n"
            "**Accept-Language:** en-US,en;q=0.5\n"
            "**Background Context:** You have had 12 incidents from 1.1.1.1 "
            "previously.\n"
            "**Cache-Control:** max-age=0\n"
            "**Connection:** keep-alive\n"
            "**Dnt:** 1\n"
            "**Dst Port:** 80\n"
            "**User-Agent:** Mozilla/5.0 (X11; Linux x86_64; rv:78.0) Gecko/20100101 "
            "Firefox/78.0"
        )

        self.check_webhook(
            "canarytoken_remote_image",
            "canarytoken alert - test image",
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_canarytoken_with_specific_topic(self) -> None:
        self.url = self.build_webhook_url(topic="foo")
        expected_message = (
            "**:alert: Canarytoken *test document* has been triggered!**\n\n"
            "A MS Word .docx Document Canarytoken has been triggered over doc-msword "
            "by the source IP 1.1.1.1.\n\n"
            "**Incident ID:** `db6f9b5528c6c6c385cb3bb63f5949c8`\n"
            "**Token:** `dbwx4d68flwh2u5zku56nogu6`\n"
            "**Kind:** MS Word .docx Document\n"
            "**Timestamp:** 2020-07-20 14:40:15 (UTC)\n"
            "**Triggered:** 5 times\n"
            "**Accept:** `*/*`\n"
            "**Accept-Encoding:** gzip, deflate\n"
            "**Accept-Language:** en-gb\n"
            "**Background Context:** You have had 21 incidents from 1.1.1.1 "
            "previously.\n"
            "**Connection:** keep-alive\n"
            "**Dst Port:** 80\n"
            "**User-Agent:** Mozilla/4.0 (compatible; ms-office; MSOffice 16)"
        )

        self.check_webhook(
            "canarytoken_msword",
            "foo",
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )
