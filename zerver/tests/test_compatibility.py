
from zerver.lib.test_classes import ZulipTestCase

class CompatibilityTest(ZulipTestCase):
    def test_compatibility(self) -> None:
        result = self.client_get("/compatibility", HTTP_USER_AGENT='ZulipMobile/5.0')
        self.assert_json_success(result)
        result = self.client_get("/compatibility", HTTP_USER_AGENT='ZulipInvalid/5.0')
        self.assert_json_error(result, "Client is too old")
