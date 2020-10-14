import logging
import re
import sys
from types import TracebackType
from typing import Iterable, Optional, Type, cast


class ExtraConsoleOutputInTestException(Exception):
    pass

class ExtraConsoleOutputFinder:
    def __init__(self) -> None:
        self.latest_test_name = ""
        valid_line_patterns = [
            # Example: Running zerver.tests.test_attachments.AttachmentsTests.test_delete_unauthenticated
            "^Running ",

            # Example: ** Test is TOO slow: analytics.tests.test_counts.TestRealmActiveHumans.test_end_to_end (0.581 s)
            "^\\*\\* Test is TOO slow: ",
            "^----------------------------------------------------------------------",

            # Example: INFO: URL coverage report is in var/url_coverage.txt
            "^INFO: URL coverage report is in",

            # Example: INFO: Try running: ./tools/create-test-api-docs
            "^INFO: Try running:",

            # Example: -- Running tests in parallel mode with 4 processes
            "^-- Running tests in",
            "^OK",

            # Example: Ran 2139 tests in 115.659s
            "^Ran [0-9]+ tests in",

            # Destroying test database for alias 'default'...
            "^Destroying test database for alias ",
            "^Using existing clone",
            "^\\*\\* Skipping ",
        ]
        self.compiled_line_patterns = []
        for pattern in valid_line_patterns:
            self.compiled_line_patterns.append(re.compile(pattern))
        self.full_extra_output = ""

    def find_extra_output(self, data: str) -> None:
        lines = data.split('\n')
        for line in lines:
            if not line:
                continue
            found_extra_output = True
            for compiled_pattern in self.compiled_line_patterns:
                if compiled_pattern.match(line):
                    found_extra_output = False
                    break
            if found_extra_output:
                self.full_extra_output += f'{line}\n'

class TeeStderrAndFindExtraConsoleOutput():
    def __init__(self, extra_output_finder: ExtraConsoleOutputFinder) -> None:
        self.stderr_stream = sys.stderr

        # get shared console handler instance from any logger that have it
        self.console_log_handler = cast(logging.StreamHandler, logging.getLogger('django.server').handlers[0])

        assert isinstance(self.console_log_handler, logging.StreamHandler)
        assert self.console_log_handler.stream == sys.stderr
        self.extra_output_finder = extra_output_finder

    def __enter__(self) -> None:
        sys.stderr = self  # type: ignore[assignment] # Doing tee by swapping stderr stream with custom file like class
        self.console_log_handler.stream = self  # type: ignore[assignment] # Doing tee by swapping stderr stream with custom file like class

    def __exit__(self, exc_type: Optional[Type[BaseException]],
                 exc_value: Optional[BaseException],
                 traceback: Optional[TracebackType]) -> None:
        sys.stderr = self.stderr_stream
        self.console_log_handler.stream = sys.stderr

    def write(self, data: str) -> None:
        self.stderr_stream.write(data)
        self.extra_output_finder.find_extra_output(data)

    def writelines(self, data: Iterable[str]) -> None:
        self.stderr_stream.writelines(data)
        lines = "".join(data)
        self.extra_output_finder.find_extra_output(lines)

    def flush(self) -> None:
        self.stderr_stream.flush()

class TeeStdoutAndFindExtraConsoleOutput():
    def __init__(self, extra_output_finder: ExtraConsoleOutputFinder) -> None:
        self.stdout_stream = sys.stdout
        self.extra_output_finder = extra_output_finder

    def __enter__(self) -> None:
        sys.stdout = self  # type: ignore[assignment] # Doing tee by swapping stderr stream with custom file like class

    def __exit__(self, exc_type: Optional[Type[BaseException]],
                 exc_value: Optional[BaseException],
                 traceback: Optional[TracebackType]) -> None:
        sys.stdout = self.stdout_stream

    def write(self, data: str) -> None:
        self.stdout_stream.write(data)
        self.extra_output_finder.find_extra_output(data)

    def writelines(self, data: Iterable[str]) -> None:
        self.stdout_stream.writelines(data)
        lines = "".join(data)
        self.extra_output_finder.find_extra_output(lines)

    def flush(self) -> None:
        self.stdout_stream.flush()
