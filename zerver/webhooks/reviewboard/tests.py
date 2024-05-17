from zerver.lib.test_classes import WebhookTestCase


class ReviewBoardHookTests(WebhookTestCase):
    CHANNEL_NAME = "reviewboard"
    URL_TEMPLATE = "/api/v1/external/reviewboard?&api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "reviewboard"

    def test_review_request_published(self) -> None:
        expected_topic_name = "Scheduler"
        expected_message = "**eeshangarg** opened [#2: Initial commit](https://rbcommons.com/s/zulip/r/2/):\n\n``` quote\n**Description**: Initial commit\n**Status**: pending\n**Target people**: **drsbgarg**\n**Branch**: master\n```"
        self.check_webhook("review_request_published", expected_topic_name, expected_message)

    def test_review_request_published_with_multiple_target_people(self) -> None:
        expected_topic_name = "Scheduler"
        expected_message = "**eeshangarg** opened [#2: Initial commit](https://rbcommons.com/s/zulip/r/2/):\n\n``` quote\n**Description**: Initial commit\n**Status**: pending\n**Target people**: **drsbgarg**, **johndoe**, and **janedoe**\n**Branch**: master\n```"
        self.check_webhook(
            "review_request_published__with_multiple_target_people",
            expected_topic_name,
            expected_message,
        )

    def test_review_request_reopened(self) -> None:
        expected_topic_name = "Scheduler"
        expected_message = "**eeshangarg** reopened [#1: Initial commit (first iteration)](https://rbcommons.com/s/zulip/r/1/):\n\n``` quote\n**Description**: Initial commit (first iteration)\n**Status**: pending\n**Target people**: **drsbgarg**\n**Branch**: master\n```"
        self.check_webhook("review_request_reopened", expected_topic_name, expected_message)

    def test_review_request_closed(self) -> None:
        expected_topic_name = "Scheduler"
        expected_message = "**eeshangarg** closed [#1: Initial commit (first iteration)](https://rbcommons.com/s/zulip/r/1/):\n\n``` quote\n**Description**: Initial commit (first iteration)\n**Status**: submitted\n**Target people**: **drsbgarg**\n**Close type**: submitted\n**Branch**: master\n```"
        self.check_webhook("review_request_closed", expected_topic_name, expected_message)

    def test_review_published(self) -> None:
        expected_topic_name = "Scheduler"
        expected_message = "**eeshangarg** [reviewed](https://rbcommons.com/s/zulip/r/1/#review651728) [#1: Initial commit (first iteration)](https://rbcommons.com/s/zulip/r/1/):\n\n**Review**:\n``` quote\nLeft some minor comments, thanks!\n```"
        self.check_webhook("review_published", expected_topic_name, expected_message)

    def test_reply_published(self) -> None:
        expected_topic_name = "Scheduler"
        expected_message = "**drsbgarg** [replied](https://rbcommons.com/s/zulip/api/review-requests/1/reviews/651728/replies/651732/) to [#1: Initial commit (first iteration)](https://rbcommons.com/s/zulip/api/review-requests/1/):\n\n**Reply**:\n``` quote\n\n```"
        self.check_webhook("reply_published", expected_topic_name, expected_message)
