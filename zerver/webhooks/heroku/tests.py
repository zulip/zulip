from zerver.lib.test_classes import WebhookTestCase


class HerokuHookTests(WebhookTestCase):
    WEBHOOK_DIR_NAME = "heroku"
    CHANNEL_NAME = "Heroku"
    URL_TEMPLATE = "/api/v1/external/heroku?stream={stream}&api_key={api_key}"

    def test_addon_attachment_create(self) -> None:
        expected_topic = "sample-app-0084"
        expected_message = """Addon Attachment - **[DATABASE](https://postgres.localhost/discover?hid=resource17@localhost)** was created by **user-0165@example.com**:
* Addon: **my-resource-0003**"""
        self.check_webhook(
            "addon_attachment_create",
            expected_topic,
            expected_message,
        )

    def test_addon_attachment_destroy(self) -> None:
        expected_topic = "sample-app-0273"
        expected_message = """Addon Attachment - **SLOWDB** was destroyed by **slowdb@addons.heroku.com**:
* Addon: **slowdb-infinite-52190**"""
        self.check_webhook(
            "addon_attachment_destroy",
            expected_topic,
            expected_message,
        )

    def test_addon_create(self) -> None:
        expected_topic = "sample-app-0036"
        expected_message = """Addon - **[cloudcounter-encircled-31432](https://addons-sso.localhost/apps/7c9e1f74-ad2c-4daf-91e5-f07bb7cafe90/addons/ac7eaeaf-cac3-43f2-8854-7c823e7bf755)** was created by **user-0043@example.com**:
* Service: cloudcounter
* Plan: cloudcounter:basic"""
        self.check_webhook(
            "addon_create",
            expected_topic,
            expected_message,
        )

    def test_addon_update(self) -> None:
        expected_topic = "sample-app-0272"
        expected_message = """Addon - **slowdb-contoured-29490** was updated by **slowdb@addons.heroku.com**:
* Service: slowdb
* Plan: slowdb:basic"""
        self.check_webhook(
            "addon_update",
            expected_topic,
            expected_message,
        )

    def test_addon_destroy(self) -> None:
        expected_topic = "sample-app-0273"
        expected_message = """Addon - **slowdb-infinite-52190** was destroyed by **slowdb@addons.heroku.com**:
* Service: slowdb
* Plan: slowdb:basic"""
        self.check_webhook(
            "addon_destroy",
            expected_topic,
            expected_message,
        )

    def test_app_create(self) -> None:
        expected_topic = "polar-wildwood-81034"
        expected_message = """App - **[polar-wildwood-81034](https://polar-wildwood-81034.herokuapp.com/)** was created by **user-0278@example.com**:
* Build Stack: cedar-14
* Region: us
* Organization: org-0058
* Git url: https://git.heroku.com/polar-wildwood-81034.git"""
        self.check_webhook(
            "app_create",
            expected_topic,
            expected_message,
        )

    def test_app_update(self) -> None:
        expected_topic = "sample-app-0301"
        expected_message = """App - **[sample-app-0301](https://sample-app-0301.herokuapp.com/)** was updated by **user-0436@example.com**:
* Build Stack: cedar-14
* Region: us
* Git url: https://git.heroku.com/sample-app-0301.git"""
        self.check_webhook(
            "app_update",
            expected_topic,
            expected_message,
        )

    def test_app_destroy(self) -> None:
        expected_topic = "sample-app-0191"
        expected_message = """App - **[sample-app-0191](https://sample-app-0191.herokuapp.com/)** was destroyed by **user-0291@example.com**:
* Build Stack: cedar-14
* Region: us
* Git url: https://git.heroku.com/sample-app-0191.git"""
        self.check_webhook(
            "app_destroy",
            expected_topic,
            expected_message,
        )

    def test_build_create(self) -> None:
        expected_topic = "example-app"
        expected_message = """Build was created by **username@example.com**:
* Status: pending
* Build Stack: heroku-16"""
        self.check_webhook(
            "build_create",
            expected_topic,
            expected_message,
        )

    def test_build_update(self) -> None:
        expected_topic = "example-app"
        expected_message = """Build was updated by **username@example.com**:
* Status: succeeded
* Build Stack: heroku-16"""
        self.check_webhook(
            "build_update",
            expected_topic,
            expected_message,
        )

    def test_collaborator_create(self) -> None:
        expected_topic = "sample-app-0270"
        expected_message = """Collaborator **user-0386@example.com** was created by **user-0386@example.com**:
* Role: owner"""
        self.check_webhook(
            "collaborator_create",
            expected_topic,
            expected_message,
        )

    def test_collaborator_update(self) -> None:
        expected_topic = "sample-app-0270"
        expected_message = (
            "Collaborator **user-0387@example.com** was updated by **user-0386@example.com**"
        )
        self.check_webhook(
            "collaborator_update",
            expected_topic,
            expected_message,
        )

    def test_collaborator_destroy(self) -> None:
        expected_topic = "sample-app-0182"
        expected_message = (
            "Collaborator **org-0059@herokumanager.com** was destroyed by **user-0282@example.com**"
        )
        self.check_webhook(
            "collaborator_destroy",
            expected_topic,
            expected_message,
        )

    def test_domain_create(self) -> None:
        expected_topic = "polar-wildwood-81034"
        expected_message = """Domain was created by **org-0058@herokumanager.com**:
* Hostname: polar-wildwood-81034.herokuapp.com
* Kind: heroku
* Status: none"""
        self.check_webhook(
            "domain_create",
            expected_topic,
            expected_message,
        )

    def test_domain_destroy(self) -> None:
        expected_topic = "new-app-name"
        expected_message = """Domain was destroyed by **user-0220@example.com**:
* Hostname: sample-app-0125.herokuapp.com
* Kind: heroku
* Status: none"""
        self.check_webhook(
            "domain_destroy",
            expected_topic,
            expected_message,
        )

    def test_dyno_create(self) -> None:
        expected_topic = "sample-app-0146"
        expected_message = """Dyno - **run.1** was created by **user-0243@example.com**:
* Size: 1X
* Type: run
* State: up"""
        self.check_webhook(
            "dyno_create",
            expected_topic,
            expected_message,
        )

    def test_formation_destroy(self) -> None:
        expected_topic = "sample-app-2263"
        expected_message = """Formation was destroyed by **user-4451@example.com**:
* Command: ruby server.rb
* Size: 1X
* Type: web
* Quantity: 0"""
        self.check_webhook(
            "formation_destroy",
            expected_topic,
            expected_message,
        )

    def test_formation_update(self) -> None:
        expected_topic = "sample-app-0197"
        expected_message = """Formation was updated by **user-0297@example.com**:
* Command: ruby server.rb
* Size: 1X
* Type: web
* Quantity: 0"""
        self.check_webhook(
            "formation_update",
            expected_topic,
            expected_message,
        )

    def test_release_create(self) -> None:
        expected_topic = "sample-app-0339"
        expected_message = """Release was created by **heroku-postgresql@addons.heroku.com**:
* Current: True
* Status: succeeded
* Version: 3
* Description: Update DATABASE by heroku-postgresql"""
        self.check_webhook(
            "release_create",
            expected_topic,
            expected_message,
        )

    def test_release_update(self) -> None:
        expected_topic = "sample-app-0008"
        expected_message = """Release was updated by **user-0008@example.com**:
* Status: failed
* Version: 1"""
        self.check_webhook(
            "release_update",
            expected_topic,
            expected_message,
        )

    def test_sni_endpoint_create(self) -> None:
        expected_topic = "sample-app-0224"
        expected_message = (
            "SNI Endpoint - **carnotaurus-30180** was created by **user-0015@example.com**."
        )
        self.check_webhook(
            "sni_endpoint_create",
            expected_topic,
            expected_message,
        )

    def test_sni_endpoint_update(self) -> None:
        expected_topic = "sample-app-0224"
        expected_message = "SNI Endpoint - **tokyo-0012** was updated by **user-0025@example.com**."
        self.check_webhook(
            "sni_endpoint_update",
            expected_topic,
            expected_message,
        )

    def test_sni_endpoint_destroy(self) -> None:
        expected_topic = "sample-app-0224"
        expected_message = (
            "SNI Endpoint - **tokyo-0007** was destroyed by **user-0007@example.com**."
        )
        self.check_webhook(
            "sni_endpoint_destroy",
            expected_topic,
            expected_message,
        )
