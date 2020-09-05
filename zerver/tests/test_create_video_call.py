from unittest import mock

import responses
from django.http import HttpResponseRedirect

from zerver.lib.test_classes import ZulipTestCase


class TestVideoCall(ZulipTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user = self.example_user("hamlet")
        self.login_user(self.user)

    def test_register_video_request_no_settings(self) -> None:
        with self.settings(VIDEO_ZOOM_CLIENT_ID=None):
            response = self.client_get("/calls/zoom/register")
            self.assert_json_error(
                response, "Zoom credentials have not been configured",
            )

    def test_register_video_request(self) -> None:
        response = self.client_get("/calls/zoom/register")
        self.assertEqual(response.status_code, 302)

    @responses.activate
    def test_create_video_request_success(self) -> None:
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

        response = self.client_post("/json/calls/zoom/create")
        self.assertEqual(
            responses.calls[-1].request.url, "https://api.zoom.us/v2/users/me/meetings",
        )
        self.assertEqual(
            responses.calls[-1].request.headers["Authorization"], "Bearer newtoken",
        )
        json = self.assert_json_success(response)
        self.assertEqual(json["url"], "example.com")

        self.logout()
        self.login_user(self.user)

        response = self.client_post("/json/calls/zoom/create")
        self.assert_json_error(response, "Invalid Zoom access token")

    def test_create_video_realm_redirect(self) -> None:
        response = self.client_get(
            "/calls/zoom/complete",
            {"code": "code", "state": '{"realm":"zephyr","sid":"somesid"}'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("http://zephyr.testserver/", response.url)
        self.assertIn("somesid", response.url)

    def test_create_video_sid_error(self) -> None:
        response = self.client_get(
            "/calls/zoom/complete",
            {"code": "code", "state": '{"realm":"zulip","sid":"bad"}'},
        )
        self.assert_json_error(response, "Invalid Zoom session identifier")

    @responses.activate
    def test_create_video_credential_error(self) -> None:
        responses.add(responses.POST, "https://zoom.us/oauth/token", status=400)

        response = self.client_get(
            "/calls/zoom/complete",
            {"code": "code", "state": '{"realm":"zulip","sid":""}'},
        )
        self.assert_json_error(response, "Invalid Zoom credentials")

    @responses.activate
    def test_create_video_refresh_error(self) -> None:
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
    def test_create_video_request_error(self) -> None:
        responses.add(
            responses.POST,
            "https://zoom.us/oauth/token",
            json={"access_token": "token"},
        )

        responses.add(
            responses.POST, "https://api.zoom.us/v2/users/me/meetings", status=400,
        )

        response = self.client_get(
            "/calls/zoom/complete",
            {"code": "code", "state": '{"realm":"zulip","sid":""}'},
        )
        self.assertEqual(response.status_code, 200)

        response = self.client_post("/json/calls/zoom/create")
        self.assert_json_error(response, "Failed to create Zoom call")

        responses.replace(
            responses.POST, "https://api.zoom.us/v2/users/me/meetings", status=401,
        )

        response = self.client_post("/json/calls/zoom/create")
        self.assert_json_error(response, "Invalid Zoom access token")

    @responses.activate
    def test_deauthorize_zoom_user(self) -> None:
        responses.add(responses.POST, "https://api.zoom.us/oauth/data/compliance")

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

    def test_create_bigbluebutton_link(self) -> None:
        with mock.patch('zerver.views.video_calls.random.randint', return_value="1"), mock.patch(
             'secrets.token_bytes', return_value=b"\x00" * 7):
            response = self.client_get("/json/calls/bigbluebutton/create")
            self.assert_json_success(response)
            self.assertEqual(response.json()['url'],
                             "/calls/bigbluebutton/join?meeting_id=%22zulip-1%22&password=%22AAAAAAAAAA%22"
                             "&checksum=%22697939301a52d3a2f0b3c3338895c1a5ab528933%22")

    @responses.activate
    def test_join_bigbluebutton_redirect(self) -> None:
        responses.add(responses.GET, "https://bbb.example.com/bigbluebutton/api/create?meetingID=zulip-1&moderatorPW=a&attendeePW=aa&checksum=check",
                      "<response><returncode>SUCCESS</returncode><messageKey/></response>")
        response = self.client_get("/calls/bigbluebutton/join?meeting_id=%22zulip-1%22&password=%22a%22&checksum=%22check%22")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(isinstance(response, HttpResponseRedirect), True)
        self.assertEqual(response.url, "https://bbb.example.com/bigbluebutton/api/join?meetingID=zulip-1&password=a"
                                       "&fullName=King%20Hamlet&checksum=7ddbb4e7e5aa57cb8c58db12003f3b5b040ff530")

    @responses.activate
    def test_join_bigbluebutton_redirect_wrong_check(self) -> None:
        responses.add(responses.GET,
                      "https://bbb.example.com/bigbluebutton/api/create?meetingID=zulip-1&moderatorPW=a&attendeePW=aa&checksum=check",
                      "<response><returncode>FAILED</returncode><messageKey>checksumError</messageKey>"
                      "<message>You did not pass the checksum security check</message></response>")
        response = self.client_get("/calls/bigbluebutton/join?meeting_id=%22zulip-1%22&password=%22a%22&checksum=%22check%22")
        self.assert_json_error(response, "Error authenticating to the Big Blue Button server.")

    @responses.activate
    def test_join_bigbluebutton_redirect_server_error(self) -> None:
        # Simulate bbb server error
        responses.add(responses.GET,
                      "https://bbb.example.com/bigbluebutton/api/create?meetingID=zulip-1&moderatorPW=a&attendeePW=aa&checksum=check", "", status=500)
        response = self.client_get(
            "/calls/bigbluebutton/join?meeting_id=%22zulip-1%22&password=%22a%22&checksum=%22check%22")
        self.assert_json_error(response, "Error connecting to the Big Blue Button server.")

    @responses.activate
    def test_join_bigbluebutton_redirect_error_by_server(self) -> None:
        # Simulate bbb server error
        responses.add(responses.GET,
                      "https://bbb.example.com/bigbluebutton/api/create?meetingID=zulip-1&moderatorPW=a&attendeePW=aa&checksum=check",
                      "<response><returncode>FAILURE</returncode><messageKey>otherFailure</messageKey></response>")
        response = self.client_get(
            "/calls/bigbluebutton/join?meeting_id=%22zulip-1%22&password=%22a%22&checksum=%22check%22")
        self.assert_json_error(response, "Big Blue Button server returned an unexpected error.")

    def test_join_bigbluebutton_redirect_not_configured(self) -> None:
        with self.settings(BIG_BLUE_BUTTON_SECRET=None,
                           BIG_BLUE_BUTTON_URL=None):
            response = self.client_get(
                "/calls/bigbluebutton/join?meeting_id=%22zulip-1%22&password=%22a%22&checksum=%22check%22")
            self.assert_json_error(response, "Big Blue Button is not configured.")
