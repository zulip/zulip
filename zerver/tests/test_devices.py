from zerver.lib.test_classes import ZulipTestCase
from zerver.models.devices import Device


class TestDeviceRegistration(ZulipTestCase):
    def test_register_device(self) -> None:
        user = self.example_user("hamlet")

        self.assertEqual(Device.objects.count(), 0)

        result = self.api_post(user, "/api/v1/register_client_device")
        data = self.assert_json_success(result)
        self.assertIn("device_id", data)

        device = Device.objects.get(id=data["device_id"])
        self.assertEqual(device.user_id, user.id)
