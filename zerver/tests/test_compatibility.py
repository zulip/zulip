
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
    data = [case.split(None, 1) for case in '''
      old ZulipInvalid/5.0
      ok  ZulipMobile/5.0
      ok  ZulipMobile/5.0 (iOS 11)
      ok  ZulipMobile/5.0 (Androidish 9)
      old ZulipMobile/5.0 (Android 9)
      old ZulipMobile/15.1.95 (Android 9)
      old ZulipMobile/16.1.94 (Android 9)
      ok  ZulipMobile/16.2.96 (Android 9)
      ok  ZulipMobile/20.0.103 (Android 9)

      ok  ZulipMobile/0.7.1.1 (iOS 11.4)
      old ZulipMobile/1.0.13 (Android 9)
      ok  ZulipMobile/17.1.98 (iOS 12.0)
      ok  ZulipMobile/19.2.102 (Android 6.0)
      ok  ZulipMobile/1 CFNetwork/974.2.1 Darwin/18.0.0
      ok  ZulipMobile/20.0.103 (Android 6.0.1)
      ok  ZulipMobile/20.0.103 (iOS 12.1)
    '''.strip().split('\n') if case]

    def test_compatibility_without_user_agent(self) -> None:
        result = self.client_get("/compatibility")
        self.assert_json_error(result, 'User-Agent header missing from request')

    def test_compatibility(self) -> None:
        for expected, user_agent in self.data:
            result = self.client_get("/compatibility",
                                     HTTP_USER_AGENT=user_agent)
            if expected == 'ok':
                self.assert_json_success(result)
            elif expected == 'old':
                self.assert_json_error(result, "Client is too old")
            else:
                assert False  # nocoverage
