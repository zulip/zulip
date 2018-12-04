
from zerver.lib.test_classes import ZulipTestCase
from zerver.views.compatibility import find_mobile_os, version_lt

class VersionTest(ZulipTestCase):
    data = [case.split() for case in '''
        1.2.3    <  1.2.4
        1.2.3    =  1.2.3
        1.4.1    >  1.2.3
        1.002a   =  1.2a
        1.2      <  1.2.3
        1.2.3    ?  1.2-dev
        1.2-dev  ?  1.2a
        1.2a     ?  1.2rc3
        1.2rc3   ?  1.2
        1.2      ?  1.2-g0f1e2d3c4
        10.1     >  1.2
        0.17.18  <  16.2.96
        9.10.11  <  16.2.96
        15.1.95  <  16.2.96
        16.2.96  =  16.2.96
        20.0.103 >  16.2.96
    '''.strip().split('\n')] + [
        ['', '?', '1'],
        ['', '?', 'a'],
    ]

    def test_version_lt(self) -> None:
        for ver1, cmp, ver2 in self.data:
            msg = 'expected {} {} {}'.format(ver1, cmp, ver2)
            if cmp == '<':
                self.assertTrue(version_lt(ver1, ver2), msg=msg)
                self.assertFalse(version_lt(ver2, ver1), msg=msg)
            elif cmp == '=':
                self.assertFalse(version_lt(ver1, ver2), msg=msg)
                self.assertFalse(version_lt(ver2, ver1), msg=msg)
            elif cmp == '>':
                self.assertFalse(version_lt(ver1, ver2), msg=msg)
                self.assertTrue(version_lt(ver2, ver1), msg=msg)
            elif cmp == '?':
                self.assertIsNone(version_lt(ver1, ver2), msg=msg)
                self.assertIsNone(version_lt(ver2, ver1), msg=msg)
            else:
                assert False  # nocoverage

    mobile_os_data = [case.split(None, 1) for case in '''
      android ZulipMobile/1.2.3 (Android 4.5)
      ios     ZulipMobile/1.2.3 (iPhone OS 2.1)
      ios     ZulipMobile/1.2.3 (iOS 6)
      None    ZulipMobile/1.2.3 (Windows 8)
    '''.strip().split('\n')]

    def test_find_mobile_os(self) -> None:
        for expected_, user_agent in self.mobile_os_data:
            expected = None if expected_ == 'None' else expected_
            self.assertEqual(find_mobile_os(user_agent), expected,
                             msg=user_agent)


class CompatibilityTest(ZulipTestCase):
    def test_compatibility(self) -> None:
        result = self.client_get("/compatibility", HTTP_USER_AGENT='ZulipMobile/5.0')
        self.assert_json_success(result)
        result = self.client_get("/compatibility", HTTP_USER_AGENT='ZulipInvalid/5.0')
        self.assert_json_error(result, "Client is too old")
