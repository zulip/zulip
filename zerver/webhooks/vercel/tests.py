import orjson

from zerver.lib.test_classes import WebhookTestCase

PROJECT_URL = "https://vercel.com/ki3anis-projects/portfolio-site"
COMMIT_URL = "https://github.com/ki3ani/portfolio-site/commit"


class VercelHookTests(WebhookTestCase):
    def test_deployment_created(self) -> None:
        expected_message = (
            f"[Production deployment]({PROJECT_URL}/EZAx66repwwATmJz4AKGrExy5Ei8) by **ki3ani** was created:\n"
            f"> Add more about me ([90989efc089]({COMMIT_URL}/90989efc089edf7ecab0acb0f5c826f0ae7d52be))"
        )
        self.check_webhook("deployment_created", "portfolio-site", expected_message)

    def test_deployment_succeeded(self) -> None:
        expected_message = (
            f"[Production deployment]({PROJECT_URL}/EZAx66repwwATmJz4AKGrExy5Ei8) by **ki3ani** succeeded:\n"
            f"> Add more about me ([90989efc089]({COMMIT_URL}/90989efc089edf7ecab0acb0f5c826f0ae7d52be))"
        )
        self.check_webhook("deployment_succeeded", "portfolio-site", expected_message)

    def test_deployment_promoted(self) -> None:
        expected_message = (
            f"[Deployment]({PROJECT_URL}/EZAx66repwwATmJz4AKGrExy5Ei8) by **ki3ani** was promoted to production:\n"
            f"> Add more about me ([90989efc089]({COMMIT_URL}/90989efc089edf7ecab0acb0f5c826f0ae7d52be))"
        )
        self.check_webhook("deployment_promoted", "portfolio-site", expected_message)

    def test_deployment_error(self) -> None:
        expected_message = (
            f"[Production deployment]({PROJECT_URL}/2evS7Amj7rASb7RN4dpWz5sVeKeD) by **ki3ani** failed:\n"
            f"> Add contact section ([4bd9710e08b]({COMMIT_URL}/4bd9710e08b05213fce39dd4127ffe1263bde3e8))"
        )
        self.check_webhook("deployment_error", "portfolio-site", expected_message)

    def test_deployment_canceled(self) -> None:
        expected_message = (
            f"[Production deployment]({PROJECT_URL}/6Ld3uyijRj9u69vowbiYbDtkD19p) by **ki3ani** was canceled:\n"
            f"> Fix contact section markup ([9de6537e7cb]({COMMIT_URL}/9de6537e7cbaeff384c45c7dd76186dae5e1ac10))"
        )
        self.check_webhook("deployment_canceled", "portfolio-site", expected_message)

    def test_preview_deployment_created(self) -> None:
        expected_message = (
            f"[Preview deployment]({PROJECT_URL}/374SqY9sTvPBUcqKCSaV4WWmf9Yn) by **ki3ani** was created:\n"
            f"> Reword homepage tagline ([0ead78914f6]({COMMIT_URL}/0ead78914f61475c13d6a005f8b719e2e1cd0ef8))"
        )
        self.check_webhook("deployment_created_preview", "portfolio-site", expected_message)

    def test_deployment_created_from_cli(self) -> None:
        expected_message = (
            f"[Preview deployment]({PROJECT_URL}/Hew77EesRN8JczesyhLtt2pykXhS) by **ki3ani** was created:\n"
            f"> Fix contacts ([15a05e3cfa7]({COMMIT_URL}/15a05e3cfa789875b5a3a216770f862f640fc78f))"
        )
        self.check_webhook("deployment_created_cli", "portfolio-site", expected_message)

    def test_deployment_created_without_git(self) -> None:
        expected_message = (
            f"[Preview deployment]({PROJECT_URL}/GbDhYEUefugozfMjuBh12ocU12Vo) was created."
        )
        self.check_webhook("deployment_created_without_git", "portfolio-site", expected_message)

    def test_deployment_created_with_multiline_commit_message(self) -> None:
        payload = orjson.loads(self.get_body("deployment_created"))
        payload["payload"]["deployment"]["meta"]["githubCommitMessage"] = (
            "Add more about me\n\nExpand the introduction on the homepage."
        )
        expected_message = (
            f"[Production deployment]({PROJECT_URL}/EZAx66repwwATmJz4AKGrExy5Ei8) by **ki3ani** was created:\n"
            f"> Add more about me ([90989efc089]({COMMIT_URL}/90989efc089edf7ecab0acb0f5c826f0ae7d52be))"
        )
        self.check_webhook(
            "deployment_created",
            "portfolio-site",
            expected_message,
            custom_payload=orjson.dumps(payload).decode(),
        )

    def test_deployment_created_with_custom_topic(self) -> None:
        self.url = self.build_webhook_url(topic="Deployments")
        expected_message = (
            f"[Production deployment]({PROJECT_URL}/EZAx66repwwATmJz4AKGrExy5Ei8) by **ki3ani** "
            f"in [portfolio-site]({PROJECT_URL}) was created:\n"
            f"> Add more about me ([90989efc089]({COMMIT_URL}/90989efc089edf7ecab0acb0f5c826f0ae7d52be))"
        )
        self.check_webhook("deployment_created", "Deployments", expected_message)

    def test_deployment_rollback_ignored(self) -> None:
        self.check_webhook("deployment_rollback", expect_noop=True)

    def test_integration_configuration_removed_ignored(self) -> None:
        self.check_webhook("integration_configuration_removed", expect_noop=True)

    def test_unsupported_event(self) -> None:
        payload = orjson.loads(self.get_body("deployment_created"))
        payload["type"] = "deployment.blocked"
        result = self.client_post(
            self.url, orjson.dumps(payload).decode(), content_type="application/json"
        )
        self.assert_json_success(result)
        self.assert_in_response(
            "The 'deployment.blocked' event isn't currently supported by the Vercel webhook; ignoring",
            result,
        )
