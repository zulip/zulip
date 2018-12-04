
from zerver.lib.test_classes import ZulipTestCase
from zerver.views.compatibility import version_lt

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
    '''.strip().split('\n')]

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

class CompatibilityTest(ZulipTestCase):
    def test_compatibility(self) -> None:
        result = self.client_get("/compatibility", HTTP_USER_AGENT='ZulipMobile/5.0')
        self.assert_json_success(result)
        result = self.client_get("/compatibility", HTTP_USER_AGENT='ZulipInvalid/5.0')
        self.assert_json_error(result, "Client is too old")
