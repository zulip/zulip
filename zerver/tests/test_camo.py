# -*- coding: utf-8 -*-
from zerver.lib.test_classes import ZulipTestCase

class CamoURLTest(ZulipTestCase):
    def test_legacy_camo_url(self) -> None:
        # Test with valid hex and url pair
        result = self.client_get("/external_content/0f50f0bda30b6e65e9442c83ddb4076c74e75f96/687474703a2f2f7777772e72616e646f6d2e736974652f696d616765732f666f6f6261722e6a706567")
        self.assertEqual(result.status_code, 302, result)
        self.assertIn('/filters:no_upscale():quality(100)/aHR0cDovL3d3dy5yYW5kb20uc2l0ZS9pbWFnZXMvZm9vYmFyLmpwZWc=/source_type/external', result.url)

        # Test with invalid hex and url pair
        result = self.client_get("/external_content/074c5e6c9c6d4ce97db1c740d79dc561cf7eb379/687474703a2f2f7777772e72616e646f6d2e736974652f696d616765732f666f6f6261722e6a706567")
        self.assertEqual(result.status_code, 403, result)
        self.assert_in_response("Not a valid URL.", result)

    def test_with_thumbor_disabled(self) -> None:
        with self.settings(THUMBOR_SERVES_CAMO=False):
            result = self.client_get("/external_content/074c5e6c9c6d4ce97db1c740d79dc561cf7eb379/687474703a2f2f7777772e72616e646f6d2e736974652f696d616765732f666f6f6261722e6a706567")
            self.assertEqual(result.status_code, 404, result)
