from zerver.lib.test_classes import ZulipTestCase
from zerver.models import UserProfile


class ZcommandTest(ZulipTestCase):
    def test_invalid_zcommand(self) -> None:
        self.login("hamlet")

        payload = dict(command="/boil-ocean")
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_error(result, "No such command: boil-ocean")

        payload = dict(command="boil-ocean")
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_error(result, "There should be a leading slash in the zcommand.")

    def test_ping_zcommand(self) -> None:
        self.login("hamlet")

        payload = dict(command="/ping")
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)

    def test_night_zcommand(self) -> None:
        self.login("hamlet")
        user = self.example_user("hamlet")
        user.color_scheme = UserProfile.COLOR_SCHEME_LIGHT
        user.save()

        payload = dict(command="/dark")
        result = self.client_post("/json/zcommand", payload)
        response_dict = self.assert_json_success(result)
        self.assertIn("Changed to dark theme", response_dict["msg"])

        result = self.client_post("/json/zcommand", payload)
        response_dict = self.assert_json_success(result)
        self.assertIn("still in dark theme", response_dict["msg"])

    def test_day_zcommand(self) -> None:
        self.login("hamlet")
        user = self.example_user("hamlet")
        user.color_scheme = UserProfile.COLOR_SCHEME_DARK
        user.save()

        payload = dict(command="/light")
        result = self.client_post("/json/zcommand", payload)
        response_dict = self.assert_json_success(result)
        self.assertIn("Changed to light theme", response_dict["msg"])

        result = self.client_post("/json/zcommand", payload)
        response_dict = self.assert_json_success(result)
        self.assertIn("still in light theme", response_dict["msg"])

    def test_fluid_zcommand(self) -> None:
        self.login("hamlet")
        user = self.example_user("hamlet")
        user.fluid_layout_width = False
        user.save()

        payload = dict(command="/fluid-width")
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)
        self.assert_in_response("Changed to fluid-width mode!", result)

        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)
        self.assert_in_response("You are still in fluid width mode", result)

    def test_fixed_zcommand(self) -> None:
        self.login("hamlet")
        user = self.example_user("hamlet")
        user.fluid_layout_width = True
        user.save()

        payload = dict(command="/fixed-width")
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)
        self.assert_in_response("Changed to fixed-width mode!", result)

        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)
        self.assert_in_response("You are still in fixed width mode", result)
