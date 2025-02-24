from unittest import mock

import orjson
import responses
from django.core.signing import Signer
from django.http import HttpResponseRedirect
from django.test import override_settings
from typing_extensions import override

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.url_encoding import append_url_query_string


@override_settings(VIDEO_ZOOM_SERVER_TO_SERVER_ACCOUNT_ID=None)
class ZoomVideoCallTestUserAuth(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.user = self.example_user("hamlet")
        self.login_user(self.user)

    def test_register_zoom_request_no_settings(self) -> None:
        with self.settings(VIDEO_ZOOM_CLIENT_ID=None):
            response = self.client_get("/calls/zoom/register")
            self.assert_json_error(
                response,
                "Zoom credentials have not been configured",
            )

    def test_register_zoom_request(self) -> None:
        response = self.client_get("/calls/zoom/register")
        self.assertEqual(response.status_code, 302)

    @responses.activate
    def test_create_zoom_video_and_audio_links(self) -> None:
        responses.add(
            responses.POST,
            "https://zoom.us/oauth/token",
            json={"access_token": "oldtoken", "expires_in": -60},
        )

        response = self.client_get(
            "/calls/zoom/complete",
            {"code": "code", "state": '{"realm":"zulip","sid":""}'},
        )
        self.assertEqual(response.status_code, 200)

        # Test creating a video link
        responses.replace(
            responses.POST,
            "https://zoom.us/oauth/token",
            json={"access_token": "newtoken", "expires_in": 60},
        )

        responses.add(
            responses.POST,
            "https://api.zoom.us/v2/users/me/meetings",
            json={"join_url": "example.com"},
        )

        response = self.client_post("/json/calls/zoom/create", {"is_video_call": "true"})
        self.assertEqual(
            responses.calls[-1].request.url,
            "https://api.zoom.us/v2/users/me/meetings",
        )
        assert responses.calls[-1].request.body is not None
        self.assertEqual(
            orjson.loads(responses.calls[-1].request.body),
            {
                "settings": {
                    "host_video": True,
                    "participant_video": True,
                },
                "default_password": True,
            },
        )
        self.assertEqual(
            responses.calls[-1].request.headers["Authorization"],
            "Bearer newtoken",
        )
        json = self.assert_json_success(response)
        self.assertEqual(json["url"], "example.com")

        # Test creating an audio link
        responses.replace(
            responses.POST,
            "https://zoom.us/oauth/token",
            json={"access_token": "newtoken", "expires_in": 60},
        )

        responses.add(
            responses.POST,
            "https://api.zoom.us/v2/users/me/meetings",
            json={"join_url": "example.com"},
        )

        response = self.client_post("/json/calls/zoom/create", {"is_video_call": "false"})
        self.assertEqual(
            responses.calls[-1].request.url,
            "https://api.zoom.us/v2/users/me/meetings",
        )
        assert responses.calls[-1].request.body is not None
        self.assertEqual(
            orjson.loads(responses.calls[-1].request.body),
            {
                "settings": {
                    "host_video": False,
                    "participant_video": False,
                },
                "default_password": True,
            },
        )
        self.assertEqual(
            responses.calls[-1].request.headers["Authorization"],
            "Bearer newtoken",
        )
        json = self.assert_json_success(response)
        self.assertEqual(json["url"], "example.com")

        # Test for authentication error
        self.logout()
        self.login_user(self.user)

        response = self.client_post("/json/calls/zoom/create")
        self.assert_json_error(response, "Invalid Zoom access token")

    def test_create_zoom_realm_redirect(self) -> None:
        response = self.client_get(
            "/calls/zoom/complete",
            {"code": "code", "state": '{"realm":"zephyr","sid":"somesid"}'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("http://zephyr.testserver/", response["Location"])
        self.assertIn("somesid", response["Location"])

    def test_create_zoom_sid_error(self) -> None:
        response = self.client_get(
            "/calls/zoom/complete",
            {"code": "code", "state": '{"realm":"zulip","sid":"bad"}'},
        )
        self.assert_json_error(response, "Invalid Zoom session identifier")

    @responses.activate
    def test_create_zoom_credential_error(self) -> None:
        responses.add(responses.POST, "https://zoom.us/oauth/token", status=400)

        response = self.client_get(
            "/calls/zoom/complete",
            {"code": "code", "state": '{"realm":"zulip","sid":""}'},
        )
        self.assert_json_error(response, "Invalid Zoom credentials")

    @responses.activate
    def test_create_zoom_refresh_error(self) -> None:
        responses.add(
            responses.POST,
            "https://zoom.us/oauth/token",
            json={"access_token": "token", "expires_in": -60},
        )

        response = self.client_get(
            "/calls/zoom/complete",
            {"code": "code", "state": '{"realm":"zulip","sid":""}'},
        )
        self.assertEqual(response.status_code, 200)

        responses.replace(responses.POST, "https://zoom.us/oauth/token", status=400)

        response = self.client_post("/json/calls/zoom/create")
        self.assert_json_error(response, "Invalid Zoom access token")

    @responses.activate
    def test_create_zoom_request_error(self) -> None:
        responses.add(
            responses.POST,
            "https://zoom.us/oauth/token",
            json={"access_token": "token"},
        )

        responses.add(
            responses.POST,
            "https://api.zoom.us/v2/users/me/meetings",
            status=400,
        )

        response = self.client_get(
            "/calls/zoom/complete",
            {"code": "code", "state": '{"realm":"zulip","sid":""}'},
        )
        self.assertEqual(response.status_code, 200)

        response = self.client_post("/json/calls/zoom/create")
        self.assert_json_error(response, "Failed to create Zoom call")

        responses.replace(
            responses.POST,
            "https://api.zoom.us/v2/users/me/meetings",
            status=401,
        )

        response = self.client_post("/json/calls/zoom/create")
        self.assert_json_error(response, "Invalid Zoom access token")

    @responses.activate
    def test_deauthorize_zoom_user(self) -> None:
        response = self.client_post(
            "/calls/zoom/deauthorize",
            """\
{
  "event": "app_deauthorized",
  "payload": {
    "user_data_retention": "false",
    "account_id": "EabCDEFghiLHMA",
    "user_id": "z9jkdsfsdfjhdkfjQ",
    "signature": "827edc3452044f0bc86bdd5684afb7d1e6becfa1a767f24df1b287853cf73000",
    "deauthorization_time": "2019-06-17T13:52:28.632Z",
    "client_id": "ADZ9k9bTWmGUoUbECUKU_a"
  }
}
""",
            content_type="application/json",
        )
        self.assert_json_success(response)


class ZoomVideoCallTestServerAuth(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.user = self.example_user("hamlet")
        self.login_user(self.user)
        self.user_zoom_meeting_url = (
            f"https://api.zoom.us/v2/users/{self.user.delivery_email}/meetings"
        )

    @responses.activate
    def test_zoom_invalid_settings(self) -> None:
        with self.settings(VIDEO_ZOOM_CLIENT_ID=None):
            response = self.client_post("/json/calls/zoom/create")
            self.assert_json_error(
                response,
                "Zoom credentials have not been configured",
            )

        responses.add(responses.POST, "https://zoom.us/oauth/token", status=400)
        response = self.client_post("/json/calls/zoom/create")
        self.assert_json_error(response, "Invalid Zoom credentials")

    @responses.activate
    def test_zoom_invalid_access_token_error(self) -> None:
        responses.add(
            responses.POST,
            "https://zoom.us/oauth/token",
            json={"access_token": "token"},
        )

        responses.add(
            responses.POST,
            self.user_zoom_meeting_url,
            status=400,
            json={"code": 124, "message": "API key expired"},
        )
        with self.assertLogs(level="ERROR") as error_log:
            response = self.client_post("/json/calls/zoom/create")
            self.assertEqual(
                error_log.output[0],
                "ERROR:root:Unexpected Zoom error 124: API key expired",
            )
        self.assert_json_error(response, "Failed to create Zoom call")

    @responses.activate
    def test_zoom_unknown_email_error(self) -> None:
        responses.add(
            responses.POST,
            "https://zoom.us/oauth/token",
            json={"access_token": "token"},
        )

        responses.add(responses.POST, self.user_zoom_meeting_url, status=400, json={"code": 1001})
        response = self.client_post("/json/calls/zoom/create")
        self.assert_json_error(response, "Unknown Zoom user email")

    @responses.activate
    def test_zoom_error_api_response_code_unknown(self) -> None:
        responses.add(
            responses.POST,
            "https://zoom.us/oauth/token",
            json={"access_token": "token"},
        )

        responses.add(responses.POST, self.user_zoom_meeting_url, status=400, json={"code": 300})
        response = self.client_post("/json/calls/zoom/create")
        self.assert_json_error(response, "Failed to create Zoom call")

    @responses.activate
    def test_zoom_create_video_call(self) -> None:
        responses.add(
            responses.POST,
            "https://zoom.us/oauth/token",
            json={"access_token": "token", "expires_in": 3599},
        )

        responses.add(
            responses.POST,
            self.user_zoom_meeting_url,
            json={"join_url": "example.com"},
        )

        response = self.client_post("/json/calls/zoom/create", {"is_video_call": "true"})
        self.assertEqual(
            responses.calls[-1].request.url,
            self.user_zoom_meeting_url,
        )
        assert responses.calls[-1].request.body is not None
        self.assertEqual(
            orjson.loads(responses.calls[-1].request.body),
            {
                "settings": {
                    "host_video": True,
                    "participant_video": True,
                },
                "default_password": True,
            },
        )
        self.assertEqual(
            responses.calls[-1].request.headers["Authorization"],
            "Bearer token",
        )
        json = self.assert_json_success(response)
        self.assertEqual(json["url"], "example.com")

    @responses.activate
    def test_zoom_create_audio_call(self) -> None:
        responses.add(
            responses.POST,
            "https://zoom.us/oauth/token",
            json={"access_token": "token", "expires_in": 3599},
        )

        responses.add(
            responses.POST,
            self.user_zoom_meeting_url,
            json={"join_url": "example.com"},
        )

        response = self.client_post("/json/calls/zoom/create", {"is_video_call": "false"})
        self.assertEqual(
            responses.calls[-1].request.url,
            self.user_zoom_meeting_url,
        )
        assert responses.calls[-1].request.body is not None
        self.assertEqual(
            orjson.loads(responses.calls[-1].request.body),
            {
                "settings": {
                    "host_video": False,
                    "participant_video": False,
                },
                "default_password": True,
            },
        )
        self.assertEqual(
            responses.calls[-1].request.headers["Authorization"],
            "Bearer token",
        )
        json = self.assert_json_success(response)
        self.assertEqual(json["url"], "example.com")


class BigBlueButtonVideoCallTest(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.user = self.example_user("hamlet")
        self.login_user(self.user)
        self.signer = Signer()
        self.signed_bbb_a_object = self.signer.sign_object(
            {
                "meeting_id": "a",
                "name": "a",
                "lock_settings_disable_cam": True,
                "moderator": self.user.id,
            }
        )
        # For testing viewer role (different creator / moderator from self)
        self.signed_bbb_a_object_different_creator = self.signer.sign_object(
            {
                "meeting_id": "a",
                "name": "a",
                "lock_settings_disable_cam": True,
                "moderator": self.example_user("cordelia").id,
            }
        )

    def test_create_bigbluebutton_link(self) -> None:
        with (
            mock.patch("zerver.views.video_calls.random.randint", return_value="1"),
            mock.patch("secrets.token_bytes", return_value=b"\x00" * 20),
        ):
            with mock.patch("zerver.views.video_calls.random.randint", return_value="1"):
                response = self.client_get(
                    "/json/calls/bigbluebutton/create?meeting_name=general > meeting&voice_only=false"
                )
            response_dict = self.assert_json_success(response)
            self.assertEqual(
                response_dict["url"],
                append_url_query_string(
                    "/calls/bigbluebutton/join",
                    "bigbluebutton="
                    + self.signer.sign_object(
                        {
                            "meeting_id": "zulip-1",
                            "name": "general > meeting",
                            "lock_settings_disable_cam": False,
                            "moderator": self.user.id,
                        }
                    ),
                ),
            )

            # Testing for audio call
            response = self.client_get(
                "/json/calls/bigbluebutton/create?meeting_name=general > meeting&voice_only=true"
            )
            response_dict = self.assert_json_success(response)
            self.assertEqual(
                response_dict["url"],
                append_url_query_string(
                    "/calls/bigbluebutton/join",
                    "bigbluebutton="
                    + self.signer.sign_object(
                        {
                            "meeting_id": "zulip-1",
                            "name": "general > meeting",
                            "lock_settings_disable_cam": True,
                            "moderator": self.user.id,
                        }
                    ),
                ),
            )

    @responses.activate
    def test_join_bigbluebutton_redirect(self) -> None:
        responses.add(
            responses.GET,
            "https://bbb.example.com/bigbluebutton/api/create?meetingID=a&name=a&lockSettingsDisableCam=True"
            "&checksum=33349e6374ca9b2d15a0c6e51a42bc3e8f770de13f88660815c6449859856e20",
            "<response><returncode>SUCCESS</returncode><messageKey/><createTime>0</createTime></response>",
        )
        response = self.client_get(
            "/calls/bigbluebutton/join", {"bigbluebutton": self.signed_bbb_a_object}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(isinstance(response, HttpResponseRedirect), True)
        self.assertEqual(
            response["Location"],
            "https://bbb.example.com/bigbluebutton/api/join?meetingID=a&"
            "role=MODERATOR&fullName=King%20Hamlet&createTime=0&checksum=54259b884a7c20ddcd7b280a1b62e59d7990568fe4f22001812bc4bcfd161a46",
        )
        # Testing for viewer role
        response = self.client_get(
            "/calls/bigbluebutton/join",
            {"bigbluebutton": self.signed_bbb_a_object_different_creator},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(isinstance(response, HttpResponseRedirect), True)
        self.assertEqual(
            response["Location"],
            "https://bbb.example.com/bigbluebutton/api/join?meetingID=a&"
            "role=VIEWER&fullName=King%20Hamlet&createTime=0&checksum=52efaf64109ca4ec5a20a1d295f315af53f9e6ec30b50ed3707fd2909ac6bd94",
        )

    @responses.activate
    def test_join_bigbluebutton_invalid_signature(self) -> None:
        responses.add(
            responses.GET,
            "https://bbb.example.com/bigbluebutton/api/create?meetingID=a&name=a&lockSettingsDisableCam=True"
            "&checksum=33349e6374ca9b2d15a0c6e51a42bc3e8f770de13f88660815c6449859856e20",
            "<response><returncode>SUCCESS</returncode><messageKey/><createTime>0</createTime></response>",
        )
        response = self.client_get(
            "/calls/bigbluebutton/join", {"bigbluebutton": self.signed_bbb_a_object + "zoo"}
        )
        self.assert_json_error(response, "Invalid signature.")

    @responses.activate
    def test_join_bigbluebutton_redirect_wrong_big_blue_button_checksum(self) -> None:
        responses.add(
            responses.GET,
            "https://bbb.example.com/bigbluebutton/api/create?meetingID=a&name=a&lockSettingsDisableCam=True&checksum=33349e6374ca9b2d15a0c6e51a42bc3e8f770de13f88660815c6449859856e20",
            "<response><returncode>FAILED</returncode><messageKey>checksumError</messageKey>"
            "<message>You did not pass the checksum security check</message></response>",
        )
        response = self.client_get(
            "/calls/bigbluebutton/join",
            {"bigbluebutton": self.signed_bbb_a_object},
        )
        self.assert_json_error(response, "Error authenticating to the BigBlueButton server.")

    @responses.activate
    def test_join_bigbluebutton_redirect_server_error(self) -> None:
        # Simulate bbb server error
        responses.add(
            responses.GET,
            "https://bbb.example.com/bigbluebutton/api/create?meetingID=a&name=a&lockSettingsDisableCam=True&checksum=33349e6374ca9b2d15a0c6e51a42bc3e8f770de13f88660815c6449859856e20",
            "",
            status=500,
        )
        response = self.client_get(
            "/calls/bigbluebutton/join",
            {"bigbluebutton": self.signed_bbb_a_object},
        )
        self.assert_json_error(response, "Error connecting to the BigBlueButton server.")

    @responses.activate
    def test_join_bigbluebutton_redirect_error_by_server(self) -> None:
        # Simulate bbb server error
        responses.add(
            responses.GET,
            "https://bbb.example.com/bigbluebutton/api/create?meetingID=a&name=a&lockSettingsDisableCam=True&checksum=33349e6374ca9b2d15a0c6e51a42bc3e8f770de13f88660815c6449859856e20",
            "<response><returncode>FAILURE</returncode><messageKey>otherFailure</messageKey></response>",
        )
        response = self.client_get(
            "/calls/bigbluebutton/join",
            {"bigbluebutton": self.signed_bbb_a_object},
        )
        self.assert_json_error(response, "BigBlueButton server returned an unexpected error.")

    def test_join_bigbluebutton_redirect_not_configured(self) -> None:
        with self.settings(BIG_BLUE_BUTTON_SECRET=None, BIG_BLUE_BUTTON_URL=None):
            response = self.client_get(
                "/calls/bigbluebutton/join",
                {"bigbluebutton": self.signed_bbb_a_object},
            )
            self.assert_json_error(response, "BigBlueButton is not configured.")
