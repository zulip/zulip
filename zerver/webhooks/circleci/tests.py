from zerver.lib.test_classes import WebhookTestCase


class CircleCiHookTests(WebhookTestCase):
    STREAM_NAME = "circleci"
    URL_TEMPLATE = "/api/v1/external/circleci?stream={stream}&api_key={api_key}"
    FIXTURE_DIR_NAME = "circleci"

    def test_private_repo_with_pull_request_off_bitbucket(self) -> None:
        expected_topic = "circleci-test"
        expected_message = """
Build [#5](https://circleci.com/bb/Hypro999/circleci-test/5) of `build`/`workflow` on branch `unstable` has failed.
- **Commits (3):** [6b5361c166](https://bitbucket.org/Hypro999/circleci-test/commits/6b5361c1661581d975e84b68904ae9bfba75d5e5) ... [eaa88f9eac](https://bitbucket.org/Hypro999/circleci-test/commits/eaa88f9eac0fad86c46a8fe35462fe2c904d84b1)
- **Pull Request:** https://bitbucket.org/Hypro999/circleci-test/pull-requests/1
- **Author:** Hemanth V. Alluri
""".strip()
        self.check_webhook(
            "bitbucket_private_repo_pull_request_failure", expected_topic, expected_message
        )

    def test_for_failed_build_off_github(self) -> None:
        expected_topic = "zulip"
        expected_message = """
Build [#1429](https://circleci.com/gh/Hypro999/zulip/1429) of `bionic-backend-frontend`/`Ubuntu 18.04 Bionic (Python 3.6, backend+frontend)` on branch `circleci` has failed.
- **Commits (2):** [73900eeb69 ... 5326f9ea40](https://github.com/Hypro999/zulip/compare/73900eeb69adbf0b83dc487e8eda90661b524eff...5326f9ea4084a01cc2bf1a461b9ad819b4ffdd14)

- **Author:** Hemanth V. Alluri (Hypro999)
- **Committer:** Hemanth V. Alluri (Hypro999)
""".strip()
        self.check_webhook(
            "github_bionic_backend_frontend_failure", expected_topic, expected_message
        )

    def test_for_success_build_off_github_with_multiple_parties(self) -> None:
        expected_topic = "zulip"
        expected_message = """
Build [#1431](https://circleci.com/gh/Hypro999/zulip/1431) of `bionic-production-build`/`Production` on branch `circleci` has succeeded.
- **Commits (2):** [73900eeb69 ... 5326f9ea40](https://github.com/Hypro999/zulip/compare/73900eeb69adbf0b83dc487e8eda90661b524eff...5326f9ea4084a01cc2bf1a461b9ad819b4ffdd14)

- **Authors:** Gintoki Sakata (ShiroYasha999), Hemanth V. Alluri (Hypro999)
- **Committers:** Hemanth V. Alluri (Hypro999), Sadaharu
""".strip()
        self.check_webhook(
            "github_bionic_production_build_success_multiple_parties",
            expected_topic,
            expected_message,
        )

    def test_for_cancelled_build_off_github(self) -> None:
        expected_topic = "zulip"
        expected_message = """
Build [#1420](https://circleci.com/gh/Hypro999/zulip/1420) of `bionic-production-install`/`Production` on branch `circleci` was canceled.
- **Commit:** [b0d6197fb4](https://github.com/Hypro999/zulip/commit/b0d6197fb4cacaf917adca77f77354882ee80621)

- **Author:** Hemanth V. Alluri (Hypro999)
- **Committer:** Hemanth V. Alluri (Hypro999)
""".strip()
        self.check_webhook(
            "github_bionic_production_install_cancelled", expected_topic, expected_message
        )

    def test_super_minimal_payload(self) -> None:
        expected_topic = "zulip"
        expected_message = "[Build](https://circleci.com/gh/zulip/zulip/48056) triggered by timabbott on branch `master` has failed."
        self.check_webhook("super_minimal_payload", expected_topic, expected_message)
