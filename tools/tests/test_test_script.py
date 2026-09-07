import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from tools.lib.test_script import write_junit_report


class WriteJUnitReportTest(unittest.TestCase):
    def test_writes_testcases_and_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report_path = Path(directory) / "junit.xml"
            write_junit_report(
                [("/tests/passing.test.ts", 0, 0.125), ("/tests/failing.test.ts", 1, 0.25)],
                str(report_path),
            )

            suite = ET.parse(report_path).getroot()
            self.assertEqual(suite.attrib["tests"], "2")
            self.assertEqual(suite.attrib["failures"], "1")
            testcases = suite.findall("testcase")
            self.assertEqual(
                [testcase.attrib["name"] for testcase in testcases],
                ["passing.test.ts", "failing.test.ts"],
            )
            failure = testcases[1].find("failure")
            self.assertIsNotNone(failure)
            self.assertEqual(failure.attrib["message"], "exit code 1")


if __name__ == "__main__":
    unittest.main()
